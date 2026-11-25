"""Build real int48 MAC/int16 output reference for the final 96->42 layer.

Earlier layers remain the selected floating Q/DQ model. Output scale is derived
only from calibration outputs; evaluate only the development split.
"""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import sys
import numpy as np
import torch
import timm
from audit_dataset import load_sample
from quantization_core import Activations, attach_activations, load_export, quantize
from integer_math import multiplier_shift, requantize

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/integer_head'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write_hex(path, values, bits):
    path.write_text(''.join(f'{int(v)&((1<<bits)-1):0{(bits+3)//4}x}\n' for v in np.asarray(values).reshape(-1)))


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    report=json.loads((ROOT/'reports/quantization_results.json').read_text())
    artifact=ROOT/report['export']['directory']
    for name,record in report['export']['files'].items():
        if sha(artifact/name)!=record['sha256']: raise ValueError('Export changed')
    fmt=json.loads((artifact/'format.json').read_text())
    if report['export']['config']!='W16A16_M125': raise ValueError('Review new configuration first')
    with np.load(artifact/'quantized_tensors.npz',allow_pickle=False) as a: tensors={k:a[k] for k in a.files}
    with np.load(artifact/'remaining_state.npz',allow_pickle=False) as a: remaining={k:a[k] for k in a.files}
    torch.set_num_threads(4);torch.manual_seed(0);torch.use_deterministic_algorithms(True);timm.layers.set_fused_attn(False)
    model_dir=ROOT/'build/model_source'
    source=json.loads((ROOT/'reports/source_update_20261125.json').read_text(encoding='utf-8'))
    for name in ['vit_model.py','psf_zernike_model_fcas_vit.py']:
        if sha(model_dir/name)!=source['archive_members']['no-fft/'+name]['sha256']: raise ValueError('Model code changed')
    sys.path.insert(0,str(model_dir))
    from psf_zernike_model_fcas_vit import create_model
    model=create_model(patch_size=8,pretrained=False,dropout=0.).eval()
    load_export(model,tensors,remaining)
    captured=[]
    sx=fmt['activation_scales']['head.7.input']['scale']
    # Capture before the Q/DQ pre-hook, using exactly its integer conversion.
    def capture(_module,inputs):
        captured.append(quantize(inputs[0],sx,16)[0].to(torch.int16).numpy().copy())
    model.head[7].register_forward_pre_hook(capture)
    attach_activations(model,Activations('quantize',bits=16,fixed_scales=fmt['activation_scales']))
    manifest_path=ROOT/'build/dataset/manifest.json'
    if sha(manifest_path)!=report['dataset_manifest_sha256']: raise ValueError('Split changed')
    manifest=json.loads(manifest_path.read_text());records={r['file']:r for r in manifest['records']}
    def run(names,label):
        captured.clear();predictions=[]
        with torch.inference_mode():
            for i in range(0,len(names),8):
                xs=[]
                for name in names[i:i+8]:
                    data=(args.source/name).read_bytes()
                    if hashlib.sha256(data).hexdigest()!=records[name]['file_sha256']: raise ValueError('Sample changed')
                    xs.append(load_sample(data)[2])
                predictions.append(model(torch.from_numpy(np.stack(xs))).numpy().copy())
                if i==0 or (i+len(xs))%200==0: print(f'{label}: {i+len(xs)}/{len(names)}',flush=True)
        return np.concatenate(predictions),np.concatenate(captured)
    cal,_=run(manifest['splits']['calibration'],'Output calibration')
    sy=float(np.max(np.abs(cal)))*1.25/32767
    if sy==0: sy=1.
    names=manifest['splits']['development']
    pred,xq=run(names,'Integer head inputs')
    with np.load(ROOT/'build/quantization/W16A16_M125_predictions.npz',allow_pickle=False) as a:
        if not np.array_equal(a['predictions'],pred): raise ValueError('Candidate reference changed')
    w=tensors['head.7.weight_int'];b=tensors['head.7.bias_int']
    if w.shape!=(42,96) or xq.shape!=(1000,96): raise ValueError('Unexpected layer shape')
    scale_acc=tensors['head.7.bias_scale']
    ratios=scale_acc/sy
    multipliers,shifts=map(np.array,zip(*(multiplier_shift(float(r)) for r in ratios)))
    acc=xq.astype(np.int64)@w.astype(np.int64).T+b
    bound=96*32767*32767+int(np.abs(b).max())
    if bound >= 1<<47 or (np.abs(acc)>=1<<47).any(): raise ValueError('int48 overflow')
    y=np.empty_like(acc,dtype=np.int16);sat=np.zeros_like(acc,dtype=bool);ideal=np.empty_like(y)
    for i in range(len(xq)):
        for j in range(42):
            y[i,j],sat[i,j]=requantize(int(acc[i,j]),int(multipliers[j]),int(shifts[j]))
            # Independent exact-rational oracle, using the original FP64 scale ratio.
            value=round(Fraction(int(acc[i,j]))*Fraction.from_float(float(ratios[j])))
            ideal[i,j]=min(32767,max(-32767,value))
    dequant=y.astype(np.float64)*sy
    mask=np.ones(42,dtype=bool);mask[36:39]=False
    with np.load(ROOT/'build/reference/development_fp32.npz',allow_pickle=False) as a:
        fp32,gt=a['predictions'],a['targets']
    # Include ordinary inputs plus the largest output-error cases.
    errors=np.max(np.abs(dequant-pred),axis=1)
    selected=list(range(8))
    for i in np.argsort(-errors):
        if int(i) not in selected: selected.append(int(i))
        if len(selected)==16: break
    np.savez_compressed(OUT/'reference.npz',names=np.array(names),inputs=xq,weights=w,biases=b,
                        accumulators=acc,outputs=y,saturated=sat,multipliers=multipliers,shifts=shifts,
                        output_scale=sy,selected=np.array(selected))
    write_hex(OUT/'weights.mem',w,16);write_hex(OUT/'biases.mem',b,48)
    write_hex(OUT/'inputs.mem',xq[selected],16);write_hex(OUT/'expected_acc.mem',acc[selected],48)
    write_hex(OUT/'expected_out.mem',y[selected],16);write_hex(OUT/'expected_sat.mem',sat[selected],1)
    write_hex(OUT/'multipliers.mem',multipliers,32);write_hex(OUT/'shifts.mem',shifts,7)
    result={'date':report['date'],'layer':'head.7','shape':[42,96],'calibration_samples':len(cal),
            'development_samples':len(names),'holdout_used':False,'output_scale':sy,'output_scale_margin':1.25,
            'input_scale':sx,'accumulator_bits':48,'conservative_accumulator_bound':bound,
            'actual_max_abs_accumulator':int(np.abs(acc).max()),'bias_int48_safe':bool((np.abs(b)<1<<47).all()),
            'multiplier_bits':31,'shift_min':int(shifts.min()),'shift_max':int(shifts.max()),
            'requant_code_mismatches_vs_exact_ratio':int((y!=ideal).sum()),
            'requant_max_code_error_vs_exact_ratio':int(np.abs(y.astype(np.int32)-ideal).max()),
            'output_saturations':int(sat.sum()),
            'head_mac_dequant_max_abs_vs_qdq':float(np.abs(acc*scale_acc-pred).max()),
            'head_int16_max_abs_vs_qdq':float(np.abs(dequant-pred).max()),
            'head_int16_rmse_vs_qdq':float(np.sqrt(np.mean((dequant[:,mask]-pred[:,mask])**2))),
            'masked_rmse_vs_fp32':float(np.sqrt(np.mean((dequant[:,mask]-fp32[:,mask])**2))),
            'masked_rmse_vs_labels':float(np.sqrt(np.mean((dequant[:,mask]-gt[:,mask])**2))),
            'board_vector_samples':[names[i] for i in selected],'board_vector_dot_products':len(selected)*42,
            'files':{f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(OUT.glob('*.mem'))+[OUT/'reference.npz']},
            'scope':'Only final Linear uses actual integer MAC/requant; preceding network remains floating Q/DQ',
            'hardware_status':'not_yet_tested'}
    (ROOT/'reports/integer_head_reference.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__': main()
