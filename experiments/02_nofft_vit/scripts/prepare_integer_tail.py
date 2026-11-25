"""Integer head.4 -> GELU lookup -> head.7; earlier network stays CPU Q/DQ."""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import json
import math
import sys
import numpy as np
import torch
import timm
from audit_dataset import load_sample
from quantization_core import Activations, attach_activations, load_export, quantize
from integer_math import multiplier_shift, requantize
from prepare_integer_head import write_hex

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/integer_tail'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def dense(x,w,b,scale,output_scale):
    ratios=scale/output_scale
    mult,shift=map(np.array,zip(*(multiplier_shift(float(r)) for r in ratios)))
    bound=x.shape[1]*32768*32768+int(np.abs(b).max())
    assert bound<1<<47
    acc=x.astype(np.int64)@w.astype(np.int64).T+b
    y=np.empty(acc.shape,np.int16);sat=np.zeros(acc.shape,bool);differences=0;max_error=0
    for i in range(len(x)):
        for j in range(len(w)):
            y[i,j],sat[i,j]=requantize(int(acc[i,j]),int(mult[j]),int(shift[j]))
            ideal=max(-32767,min(32767,round(Fraction(int(acc[i,j]))*Fraction.from_float(float(ratios[j])))))
            err=abs(int(y[i,j])-ideal);differences+=bool(err);max_error=max(max_error,err)
    return acc,y,sat,mult,shift,{'conservative_abs_bound':bound,'actual_abs_max':int(np.abs(acc).max()),
        'exact_ratio_code_mismatches':differences,'exact_ratio_max_code_error':max_error,'saturations':int(sat.sum())}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    report=json.loads((ROOT/'reports/quantization_results.json').read_text())
    assert report['export']['config']=='W16A16_M125'
    artifact=ROOT/report['export']['directory']
    for n,r in report['export']['files'].items():assert sha(artifact/n)==r['sha256'],n
    fmt=json.loads((artifact/'format.json').read_text())
    with np.load(artifact/'quantized_tensors.npz',allow_pickle=False) as d:t={k:d[k] for k in d.files}
    with np.load(artifact/'remaining_state.npz',allow_pickle=False) as d:remaining={k:d[k] for k in d.files}
    old_report=json.loads((ROOT/'reports/integer_head_reference.json').read_text())
    old_reference=ROOT/'build/integer_head/reference.npz'
    assert sha(old_reference)==old_report['files']['reference.npz']['sha256']
    with np.load(old_reference,allow_pickle=False) as d:
        final_scale=float(d['output_scale']);old_y=d['outputs'].copy();old_names=d['names'].copy()
    torch.set_num_threads(4);torch.manual_seed(0);torch.use_deterministic_algorithms(True);timm.layers.set_fused_attn(False)
    model_dir=ROOT/'build/model_source'
    source=json.loads((ROOT/'reports/source_update_20261125.json').read_text(encoding='utf-8'))
    for n in ['vit_model.py','psf_zernike_model_fcas_vit.py']:assert sha(model_dir/n)==source['archive_members']['no-fft/'+n]['sha256']
    sys.path.insert(0,str(model_dir))
    from psf_zernike_model_fcas_vit import create_model
    model=create_model(patch_size=8,pretrained=False,dropout=0.).eval();load_export(model,t,remaining)
    sx=fmt['activation_scales']['head.4.input']['scale'];sg=fmt['activation_scales']['head.7.input']['scale']
    captured=[];pre_gelu=[]
    model.head[4].register_forward_pre_hook(lambda m,x:captured.append(quantize(x[0],sx,16)[0].to(torch.int16).numpy().copy()))
    model.head[4].register_forward_hook(lambda m,x,y:pre_gelu.append(y.numpy().copy()))
    attach_activations(model,Activations('quantize',bits=16,fixed_scales=fmt['activation_scales']))
    manifest_path=ROOT/'build/dataset/manifest.json';assert sha(manifest_path)==report['dataset_manifest_sha256']
    manifest=json.loads(manifest_path.read_text());records={r['file']:r for r in manifest['records']}
    def run(names,label):
        captured.clear();pre_gelu.clear();pred=[]
        with torch.inference_mode():
            for i in range(0,len(names),8):
                xs=[]
                for n in names[i:i+8]:
                    data=(args.source/n).read_bytes();assert hashlib.sha256(data).hexdigest()==records[n]['file_sha256'],n
                    xs.append(load_sample(data)[2])
                pred.append(model(torch.from_numpy(np.stack(xs))).numpy().copy())
                if i==0 or (i+len(xs))%200==0:print(f'{label}: {i+len(xs)}/{len(names)}',flush=True)
        return np.concatenate(pred),np.concatenate(captured),np.concatenate(pre_gelu)
    _,_,cal=run(manifest['splits']['calibration'],'GELU input calibration')
    sz=float(np.abs(cal).max())*1.25/32767 or 1.
    names=manifest['splits']['development'];pred,x,z_float=run(names,'Two-layer inputs')
    assert np.array_equal(names,old_names) and x.shape==(1000,192)
    with np.load(ROOT/'build/quantization/W16A16_M125_predictions.npz',allow_pickle=False) as d:assert np.array_equal(d['predictions'],pred)
    # Full address space: address is the 16-bit two's-complement code, not a clipped domain.
    codes=np.arange(65536,dtype=np.uint16).view(np.int16).astype(np.float64)
    real=codes*sz
    exact=np.array([.5*v*(1+math.erf(v/math.sqrt(2))) for v in real])
    lut=np.clip(np.rint(exact/sg),-32767,32767).astype(np.int16)
    with torch.inference_mode():tg=torch.nn.functional.gelu(torch.from_numpy(real),approximate='none').numpy()
    oracle=np.clip(np.rint(tg/sg),-32767,32767).astype(np.int16)
    assert np.array_equal(lut,oracle),'GELU table oracle mismatch'
    a,z,zsat,m,s,stats4=dense(x,t['head.4.weight_int'],t['head.4.bias_int'],t['head.4.bias_scale'],sz)
    g=lut[z.astype(np.uint16)]
    gelu_clipped=(np.rint(exact/sg)<-32767)|(np.rint(exact/sg)>32767)
    development_gelu_clipped=int(gelu_clipped[z.astype(np.uint16)].sum())
    acc,y,sat,m7,s7,stats7=dense(g,t['head.7.weight_int'],t['head.7.bias_int'],t['head.7.bias_scale'],final_scale)
    assert stats4['exact_ratio_max_code_error']<=1 and stats7['exact_ratio_max_code_error']<=1
    result=y.astype(np.float64)*final_scale;mask=np.ones(42,bool);mask[36:39]=False
    with np.load(ROOT/'build/reference/development_fp32.npz',allow_pickle=False) as d:fp32,gt=d['predictions'],d['targets']
    np.savez_compressed(OUT/'reference.npz',names=np.array(names),inputs=x,pre_acc=a,pre_codes=z,gelu_codes=g,
        pre_saturated=zsat,accumulators=acc,outputs=y,saturated=sat,output_scale=final_scale)
    for prefix,key,mul,shift in [('pre','head.4',m,s),('final','head.7',m7,s7)]:
        for n,v,bits in [('weights',t[key+'.weight_int'],16),('biases',t[key+'.bias_int'],48),('multipliers',mul,32),('shifts',shift,7)]:write_hex(OUT/f'{prefix}_{n}.mem',v,bits)
    write_hex(OUT/'gelu.mem',lut,16)
    rms=lambda d:float(np.sqrt(np.mean(d[:,mask]**2)))
    data={'date':'2026-11-25','scope':'head.4 integer Linear 192->96, full INT16 GELU table, head.7 integer Linear 96->42; earlier layers CPU Q/DQ',
        'calibration_samples':len(cal),'development_samples':len(x),'holdout_used':False,'input_scale':sx,'pre_gelu_scale':sz,'gelu_output_scale':sg,
        'output_scale':final_scale,'pre_gelu_margin':1.25,'head4':stats4,'head7':stats7,'gelu_table_entries':65536,
        'gelu_table_code_mismatches_vs_torch_float64':int((lut!=oracle).sum()),'gelu_table_max_abs_error':float(np.abs(lut.astype(float)*sg-exact).max()),
        'gelu_table_clipped_addresses':int(gelu_clipped.sum()),'development_gelu_saturations':development_gelu_clipped,
        'gelu_table_max_abs_error_vs_clipped_function':float(np.abs(lut.astype(float)*sg-np.clip(exact,-32767*sg,32767*sg)).max()),
        'pre_gelu_mac_max_abs_vs_qdq':float(np.abs(a*t['head.4.bias_scale']-z_float).max()),
        'rmse_vs_qdq':rms(result-pred),'max_abs_vs_qdq':float(np.abs(result-pred).max()),
        'rmse_vs_previous_integer_head':rms(result-old_y.astype(float)*final_scale),
        'masked_rmse_vs_fp32':rms(result-fp32),'masked_rmse_vs_labels':rms(result-gt),
        'dataset_manifest_sha256':sha(manifest_path),'previous_reference_sha256':sha(old_reference),'hardware_status':'pending',
        'files':{n:{'sha256':sha(OUT/n),'bytes':(OUT/n).stat().st_size} for n in
            [f'{prefix}_{kind}.mem' for prefix in ['pre','final'] for kind in ['weights','biases','multipliers','shifts']]+['gelu.mem','reference.npz']}}
    (ROOT/'reports/integer_tail_reference.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k!='files'},indent=2),flush=True)

if __name__=='__main__':main()
