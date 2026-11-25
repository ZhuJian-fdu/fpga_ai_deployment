"""Calibrate on 300 samples and compare explicit PTQ simulations on development data.

Never evaluates the reserved holdout. Does not claim integer-only inference.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone, timedelta
import numpy as np
import torch
import timm
from audit_dataset import load_sample
from quantization_core import Activations, attach_activations, apply_weights, load_export

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/quantization'
CONFIGS = {'W8_FP32': (8, None, 1.), 'W8A8': (8, 8, 1.), 'W8A12': (8, 12, 1.),
           'W8A16': (8, 16, 1.), 'W16A16': (16, 16, 1.),
           'W16A16_M125': (16, 16, 1.25), 'W16A16_M200': (16, 16, 2.)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--export', choices=['auto'] + [n for n in CONFIGS if n != 'W8_FP32'], default='auto')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    timm.layers.set_fused_attn(False)
    date = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    source = json.loads((ROOT / 'reports/source_update_20261125.json').read_text(encoding='utf-8'))
    model_dir = ROOT / 'build/model_source'
    for member, record in source['archive_members'].items():
        name = Path(member).name
        if name in ('vit_model.py', 'psf_zernike_model_fcas_vit.py', 'model_best.pth'):
            if sha(model_dir / name) != record['sha256']:
                raise ValueError(f'Model source/weights changed: {name}')
    sys.path.insert(0, str(model_dir))
    from psf_zernike_model_fcas_vit import create_model
    state = torch.load(model_dir / 'model_best.pth', map_location='cpu', weights_only=True)
    state = {k.removeprefix('module.'): v for k, v in state.items()}

    def new_model(weights=True):
        model = create_model(patch_size=8, pretrained=False, dropout=0.0).eval()
        if weights:
            model.load_state_dict(state, strict=True)
        return model

    data_report = json.loads((ROOT / 'reports/dataset_audit.json').read_text(encoding='utf-8'))
    ref_report = json.loads((ROOT / 'reports/fp32_reference.json').read_text())
    manifest_path = ROOT / 'build/dataset/manifest.json'
    if sha(manifest_path) != data_report['manifest_sha256'] or sha(manifest_path) != ref_report['dataset_manifest_sha256']:
        raise ValueError('Dataset split changed')
    if source['checkpoint']['sha256'] != ref_report['checkpoint_sha256']:
        raise ValueError('FP32 reference used different weights')
    manifest = json.loads(manifest_path.read_text())
    records = {r['file']: r for r in manifest['records']}
    cal_names, dev_names = manifest['splits']['calibration'], manifest['splits']['development']
    if set(cal_names) & set(dev_names):
        raise ValueError('Calibration and development overlap')
    reference_path = ROOT / 'build/reference/development_fp32.npz'
    if sha(reference_path) != ref_report['output_sha256']:
        raise ValueError('FP32 prediction artifact changed')
    with np.load(reference_path, allow_pickle=False) as ref:
        baseline, targets, mask = ref['predictions'], ref['targets'], ref['mask']
        if dev_names != ref['names'].tolist():
            raise ValueError('Reference sample order mismatch')

    def inputs(names):
        values = []
        for name in names:
            data = (args.source / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != records[name]['file_sha256']:
                raise ValueError(f'Data changed: {name}')
            values.append(load_sample(data)[2])
        return torch.from_numpy(np.stack(values))

    calibration_x, development_x = inputs(cal_names), inputs(dev_names)

    def evaluate(model, x, tag):
        predictions = []
        started = time.perf_counter()
        with torch.inference_mode():
            for i in range(0, len(x), 8):
                y = model(x[i:i+8]).numpy()
                if not np.isfinite(y).all():
                    raise ValueError(f'Nonfinite prediction: {tag}')
                predictions.append(y.copy())
                if i == 0 or (i + len(y)) % 200 == 0:
                    print(f'{tag}: {i+len(y)}/{len(x)}', flush=True)
        return np.concatenate(predictions), time.perf_counter() - started

    # Validate our Attention adapter/hook placement without any quantization.
    control = Activations('bypass')
    model = new_model(); attach_activations(model, control)
    identity, _ = evaluate(model, development_x, 'FP32 adapter check')
    bypass_delta = float(np.abs(identity - baseline).max())
    if not np.allclose(identity, baseline, rtol=1e-5, atol=1e-6):
        raise ValueError(f'Attention adapter changed baseline: {bypass_delta}')
    del model
    observer = Activations('observe')
    model = new_model(); attach_activations(model, observer)
    evaluate(model, calibration_x, 'Calibration')
    ranges = observer.ranges
    write_json(ROOT / 'reports/quantization_calibration.json', {
        'date': date, 'samples': len(cal_names), 'split': 'calibration',
        'dataset_manifest_sha256': data_report['manifest_sha256'], 'sites': ranges,
        'method': 'FP32 min/max, per site; fixed [0,1] for softmax probabilities',
        'development_used_for_ranges': False, 'holdout_used': False})
    del model
    metrics, artifacts = {}, {}
    fp_error = baseline[:, mask].astype(np.float64) - targets[:, mask]
    fp_rmse = float(np.sqrt(np.mean(fp_error**2)))
    for config, (wbits, abits, margin) in CONFIGS.items():
        controller = Activations('quantize', ranges, abits, margin)
        model = new_model()
        tensors, layers = apply_weights(model, wbits, controller)
        attach_activations(model, controller)
        pred, elapsed = evaluate(model, development_x, config)
        diff = pred[:, mask].astype(np.float64) - baseline[:, mask]
        task = pred[:, mask].astype(np.float64) - targets[:, mask]
        task_rmse = float(np.sqrt(np.mean(task**2)))
        stats = controller.stats
        elements = sum(s['elements'] for s in stats.values())
        clips = sum(s['clipped'] for s in stats.values())
        signed_bits = [v['accumulator_signed_bits'] for v in layers.values() if 'accumulator_signed_bits' in v]
        metrics[config] = {
            'weight_bits': wbits, 'activation_bits': abits, 'range_margin': margin, 'samples': len(dev_names),
            'task_masked_rmse': task_rmse, 'task_rmse_change_pct': 100*(task_rmse/fp_rmse - 1),
            'quantization_masked_rmse_vs_fp32': float(np.sqrt(np.mean(diff**2))),
            'quantization_masked_mae_vs_fp32': float(np.mean(np.abs(diff))),
            'quantization_masked_max_abs_vs_fp32': float(np.max(np.abs(diff))),
            'quantization_all42_max_abs_vs_fp32': float(np.max(np.abs(pred.astype(np.float64)-baseline))),
            'per_sample_quant_rmse_p95': float(np.percentile(np.sqrt(np.mean(diff**2, axis=1)),95)),
            'activation_elements': elements, 'activation_clipped': clips,
            'activation_clipping_fraction': clips/elements if elements else 0,
            'largest_required_signed_accumulator_bits': max(signed_bits) if signed_bits else None,
            'weight_payload_bytes': sum(v.nbytes for k,v in tensors.items() if k.endswith('.weight_int')),
            'elapsed_seconds': elapsed,
        }
        np.savez_compressed(OUT / (config + '_predictions.npz'), names=np.array(dev_names), predictions=pred)
        write_json(OUT / (config + '_layers.json'), {'layers': layers, 'clipping': stats})
        del model, tensors
        print(config + ': ' + json.dumps(metrics[config]), flush=True)

    # Selection uses development errors, never holdout. It is a candidate,
    # not an acceptance threshold or an independently validated accuracy claim.
    if args.export == 'auto':
        candidates = [n for n in CONFIGS if n.startswith('W16A16')]
        config = min(candidates, key=lambda n: metrics[n]['quantization_masked_max_abs_vs_fp32'])
    else:
        config = args.export
    wbits, abits, margin = CONFIGS[config]
    controller = Activations('quantize', ranges, abits, margin)
    model = new_model()
    tensors, layers = apply_weights(model, wbits, controller)
    directory = OUT / config
    directory.mkdir(exist_ok=True)
    quant_keys = {n + '.weight' for n in layers}
    quant_keys |= {n + '.bias' for n in layers if n + '.bias_int' in tensors}
    remaining = {k: v.cpu().numpy().copy() for k,v in model.state_dict().items() if k not in quant_keys}
    np.savez_compressed(directory / 'quantized_tensors.npz', **tensors)
    np.savez_compressed(directory / 'remaining_state.npz', **remaining)
    offset, layout = 0, []
    with (directory / 'weights.bin').open('wb') as binary:
        for name in layers:
            value = tensors[name + '.weight_int'].astype('<i1' if wbits==8 else '<i2')
            data = value.tobytes(order='C'); binary.write(data)
            layout.append({'name': name+'.weight', 'offset_bytes': offset, 'bytes': len(data),
                           'shape': list(value.shape), 'dtype': str(value.dtype), 'order': 'C'})
            offset += len(data)
    activation_scales = {n: {'scale': controller.scale(n, r['unsigned']),
                             'unsigned': r['unsigned'], 'bits': abits} for n,r in ranges.items()}
    write_json(directory / 'format.json', {
        'version': 1, 'config': config, 'range_margin': margin, 'rounding': 'nearest ties to even, evaluated in float32',
        'signed_range': [-((1<<(abits-1))-1), (1<<(abits-1))-1],
        'weight_axis': 0, 'weight_layout': layout, 'layers': layers,
        'activation_scales': activation_scales,
        'floating_operations': ['MAC accumulation/dequantization in this simulator', 'BatchNorm',
            'LayerNorm', 'Softmax', 'GELU', 'Sigmoid', 'HSwish', 'pooling',
            'residual additions', 'CA/CBAM elementwise products', 'position/class token additions'],
        'scope': 'PTQ Q/DQ candidate; not all-integer deployable network or cycle/bit-exact RTL'})
    artifacts = {'config': config, 'directory': str(directory.relative_to(ROOT)),
                 'files': {f.name: {'bytes': f.stat().st_size, 'sha256': sha(f)} for f in directory.iterdir() if f.is_file()}}
    del model

    # Verify exported payloads rather than simply trusting the in-memory model.
    directory = OUT / config
    with np.load(directory / 'quantized_tensors.npz', allow_pickle=False) as saved:
        tensors = {k: saved[k] for k in saved.files}
    with np.load(directory / 'remaining_state.npz', allow_pickle=False) as saved:
        remaining = {k: saved[k] for k in saved.files}
    model = new_model(weights=False)
    load_export(model, tensors, remaining)
    saved_format = json.loads((directory / 'format.json').read_text())
    attach_activations(model, Activations('quantize', bits=abits, fixed_scales=saved_format['activation_scales']))
    reloaded, _ = evaluate(model, development_x, 'Export reload')
    with np.load(OUT / (config + '_predictions.npz'), allow_pickle=False) as saved:
        identical = bool(np.array_equal(reloaded, saved['predictions']))
        reload_delta = float(np.max(np.abs(reloaded-saved['predictions'])))
    if not identical:
        raise ValueError(f'Export roundtrip changed results: {reload_delta}')
    result = {'date': date, 'torch': torch.__version__, 'timm': timm.__version__,
              'calibration_samples': len(cal_names), 'development_samples': len(dev_names),
              'reserved_holdout_inference': False, 'calibration_sites': len(ranges),
              'fp32_task_masked_rmse': fp_rmse, 'adapter_max_abs_vs_fp32': bypass_delta,
              'configurations': metrics, 'export': artifacts,
              'export_roundtrip': {'bitwise_equal_fp32_predictions': identical, 'max_abs_difference': reload_delta},
              'dataset_manifest_sha256': sha(manifest_path),
              'checkpoint_sha256': source['checkpoint']['sha256'],
              'user_accuracy_threshold': None,
              'candidate_selection': 'min development max output deviation among W16A16 margin 1, 1.25, 2; not final acceptance',
              'scope': 'Software PTQ simulation and integer weight export; nonlinearities and accumulation still float; no FPGA inference',
              'script_sha256': {n: sha(ROOT/'scripts'/n) for n in ['quantization_core.py','run_quantization.py']}}
    write_json(ROOT / 'reports/quantization_results.json', result)
    print('PASS: comparisons and export roundtrip complete', flush=True)


if __name__ == '__main__':
    main()
