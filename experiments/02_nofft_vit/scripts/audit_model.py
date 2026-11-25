"""Read supplied files, inspect ONNX, and compare CPU inference with saved references."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference

ROOT = Path(__file__).resolve().parents[1]


def one(paths):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one matching file, got {paths}")
    return paths[0]


def shape(value):
    return [d.dim_value if d.HasField('dim_value') else d.dim_param or None
            for d in value.type.tensor_type.shape.dim]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/model_audit.json')
    args = parser.parse_args()
    source = args.source.resolve()
    model_path = one(source.rglob('*.onnx'))
    checkpoint = one(source.rglob('*.pth'))
    supplied = json.loads(one(source.rglob('summary.json')).read_text(encoding='utf-8'))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(checkpoint) != supplied['checkpoint_sha256']:
        raise ValueError('Checkpoint hash does not match supplied reference summary')
    model = onnx.load(model_path)
    onnx.checker.check_model(model, full_check=True)
    inferred = SymbolicShapeInference.infer_shapes(model, auto_merge=True)
    dims = {v.name: shape(v) for v in [*inferred.graph.input, *inferred.graph.value_info, *inferred.graph.output]}
    initializers = []
    for tensor in model.graph.initializer:
        array = numpy_helper.to_array(tensor)
        dims[tensor.name] = list(array.shape)
        initializers.append({'name': tensor.name, 'shape': list(array.shape),
                             'dtype': str(array.dtype), 'elements': int(array.size), 'bytes': array.nbytes})
    macs = 0
    unresolved = []
    for node in inferred.graph.node:
        if node.op_type not in ['Conv', 'MatMul', 'Gemm']:
            continue
        try:
            out = dims[node.output[0]]
            left = dims[node.input[0]]
            right = dims[node.input[1]]
            if not all(isinstance(x, int) and x > 0 for x in out+left+right):
                raise ValueError('dynamic shape')
            if node.op_type == 'Conv':
                count = math.prod(out)*math.prod(right[1:])
            elif node.op_type == 'Gemm':
                trans_a = next((a.i for a in node.attribute if a.name == 'transA'), 0)
                count = math.prod(out)*left[0 if trans_a else -1]
            else:
                count = math.prod(out)*left[-1]
            macs += count
        except (KeyError, ValueError, IndexError):
            unresolved.append(node.name)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=['CPUExecutionProvider'])
    optimized_options = ort.SessionOptions()
    optimized_options.intra_op_num_threads = 4
    optimized_options.inter_op_num_threads = 1
    optimized_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    optimized_session = ort.InferenceSession(str(model_path), sess_options=optimized_options, providers=['CPUExecutionProvider'])
    if len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1:
        raise ValueError('Expected one input and one output')
    cases = []
    for path in sorted(source.rglob('*.npz')):
        if path.stem.endswith('_prediction'):
            continue
        ref_path = one(source.rglob(path.stem+'_prediction.npz'))
        with np.load(path, allow_pickle=False) as data, np.load(ref_path, allow_pickle=False) as ref:
            images = data['images'].astype(np.float32)
            gt = data['gt_a'].astype(np.float32)
            reference = ref['pred_7x6']
            mask = ref['valid_mask_7x6']
            if images.shape != (5,112,112) or gt.shape != (7,30) or not np.isfinite(images).all():
                raise ValueError(f'Unexpected input: {path}')
            if mask.shape != (7,6) or mask.dtype != bool or mask.sum() != 39:
                raise ValueError('Unexpected reference mask')
            if not np.array_equal(gt, ref['gt_a']):
                raise ValueError('Input/reference labels differ')
            prediction = session.run(None, {session.get_inputs()[0].name: images[None]})[0].reshape(7,6)
            optimized = optimized_session.run(None, {session.get_inputs()[0].name: images[None]})[0].reshape(7,6)
            delta = prediction-reference
            cases.append({'sample': path.name, 'input_keys': list(data.files),
                          'input_shape': list(images.shape), 'input_dtype': str(data['images'].dtype),
                          'input_min': float(images.min()), 'input_max': float(images.max()),
                          'channel_min': images.min(axis=(1,2)).tolist(),
                          'channel_max': images.max(axis=(1,2)).tolist(),
                          'reference_max_abs': float(np.max(np.abs(delta))),
                          'reference_rmse': float(np.sqrt(np.mean(delta**2))),
                          'allclose_rtol1e-5_atol1e-6': bool(np.allclose(prediction,reference,rtol=1e-5,atol=1e-6)),
                          'optimized_reference_max_abs': float(np.max(np.abs(optimized-reference))),
                          'optimized_allclose_same_tolerance': bool(np.allclose(optimized,reference,rtol=1e-5,atol=1e-6)),
                          'masked_mse_39': float(np.mean(((prediction-gt[:,:6])[mask])**2))})
    if len(cases) != supplied['sample_count']:
        raise ValueError('Reference sample count differs')
    report = {'date': '2026-11-25', 'timezone': 'Asia/Shanghai',
              'versions': {'numpy': np.__version__, 'onnx': onnx.__version__, 'onnxruntime': ort.__version__},
              'source_files': {p.relative_to(source).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                               for p in sorted(source.rglob('*')) if p.is_file()},
              'checkpoint_hash_matches_supplied_summary': True,
              'pytorch_parameter_count_from_supplied_summary': supplied['parameter_count'],
              'onnx_checker': 'PASS', 'ir_version': model.ir_version,
              'baseline_graph_optimization': 'ORT_DISABLE_ALL',
              'comparison_tolerance_note': 'rtol=1e-5, atol=1e-6 is a provisional FP32 cross-runtime diagnostic, not an approved FPGA quantization tolerance. Optimized execution is reported separately without loosening it.',
              'opsets': {o.domain or 'ai.onnx': o.version for o in model.opset_import},
              'inputs': [{'name':v.name,'shape':shape(v)} for v in model.graph.input],
              'outputs': [{'name':v.name,'shape':shape(v)} for v in model.graph.output],
              'operators': dict(sorted(Counter(n.op_type for n in model.graph.node).items())),
              'initializers': initializers, 'initializer_bytes':sum(x['bytes'] for x in initializers),
              'conv_matmul_gemm_macs': macs, 'mac_nodes_unresolved': unresolved,
              'mac_note': 'Shape-derived Conv/MatMul/Gemm MACs only; excludes other operators, memory/transfer overhead and FPGA scheduling.',
              'cases': cases,
              'pooled_masked_rmse_39': float(np.sqrt(np.mean([c['masked_mse_39'] for c in cases]))),
              'all_reference_comparisons_pass': all(c['allclose_rtol1e-5_atol1e-6'] for c in cases),
              'boundary': 'ONNX CPU evaluation versus supplied PyTorch reference files. PyTorch was not independently rerun; no quantization or FPGA build has been performed.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_files','initializers']},ensure_ascii=True,indent=2))
    if not report['all_reference_comparisons_pass']:
        raise SystemExit('FAIL: ONNX/reference mismatch; inspect report')


if __name__ == '__main__':
    main()
