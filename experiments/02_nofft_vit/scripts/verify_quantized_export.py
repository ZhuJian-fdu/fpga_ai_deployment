"""Check exported binary layout and conservative integer accumulator bounds."""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT/'reports/quantization_results.json').read_text(encoding='utf-8'))
    artifact = ROOT/report['export']['directory']
    for name, record in report['export']['files'].items():
        path = artifact/name
        if path.stat().st_size != record['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError(f'Export artifact changed: {name}')
    fmt = json.loads((artifact/'format.json').read_text())
    offset, weights, largest_bits = 0, 0, 0
    layers = {}
    with np.load(artifact/'quantized_tensors.npz', allow_pickle=False) as tensors, (artifact/'weights.bin').open('rb') as binary:
        for entry in fmt['weight_layout']:
            name = entry['name'].removesuffix('.weight')
            layer = fmt['layers'][name]
            q = tensors[name+'.weight_int']
            if entry['offset_bytes'] != offset or entry['shape'] != list(q.shape):
                raise ValueError('Noncontiguous or mismatched layout')
            raw = binary.read(entry['bytes'])
            decoded = np.frombuffer(raw,dtype='<i1' if layer['weight_bits']==8 else '<i2').reshape(q.shape)
            np.testing.assert_array_equal(decoded,q)
            limit = (1 << (layer['weight_bits']-1))-1
            if not np.issubdtype(q.dtype,np.signedinteger) or int(q.min()) < -limit or int(q.max()) > limit:
                raise ValueError('Weight integer format mismatch')
            scale = tensors[name+'.weight_scale']
            if scale.shape != (q.shape[0],) or not np.isfinite(scale).all() or (scale<=0).any():
                raise ValueError('Invalid weight scales')
            amax = (1 << (layer['input_bits']-1))-1
            b = tensors[name+'.bias_int'] if name+'.bias_int' in tensors.files else np.zeros(q.shape[0],dtype=np.int64)
            if name+'.bias_int' in tensors.files:
                if b.dtype != np.dtype('int64'):
                    raise ValueError('Expected int64 bias storage')
                np.testing.assert_array_equal(tensors[name+'.bias_scale'],scale.astype(np.float64)*layer['input_scale'])
            # Each channel's extremal dot product uses x_i=sign(w_i)*amax.
            max_dot = np.abs(q.astype(np.int64)).reshape(q.shape[0],-1).sum(axis=1)*amax
            actual_bound = int((max_dot+np.abs(b)).max())
            theoretical = q[0].size*limit*amax+int(np.abs(b).max())
            if theoretical != layer['accumulator_abs_bound'] or actual_bound > theoretical:
                raise ValueError('Accumulator bound mismatch')
            required = theoretical.bit_length()+1
            if required != layer['accumulator_signed_bits']:
                raise ValueError('Accumulator width mismatch')
            largest_bits = max(largest_bits,required)
            layers[name] = {'actual_weight_extreme_abs_bound':actual_bound,
                            'conservative_abs_bound':theoretical,'signed_bits':required}
            offset += len(raw);weights += q.size
        if binary.read(1):
            raise ValueError('Unexpected trailing weight bytes')
    bits = report['configurations'][report['export']['config']]['activation_bits']
    # Supplied ViT-Small uses 384/6=64 head dimension and 49 patches + class token.
    amax=(1<<(bits-1))-1;pmax=(1<<bits)-1
    attention={'qk_terms':64,'qk_abs_bound':64*amax*amax,
               'qk_signed_bits':(64*amax*amax).bit_length()+1,
               'pv_terms':50,'pv_abs_bound':50*pmax*amax,
               'pv_signed_bits':(50*pmax*amax).bit_length()+1}
    with np.load(artifact/'remaining_state.npz',allow_pickle=False) as remaining:
        remaining_bytes=sum(remaining[k].nbytes for k in remaining.files)
        remaining_tensors=len(remaining.files)
    result={'date':report['date'],'config':report['export']['config'],'layers':len(layers),
            'integer_weight_elements':weights,'weight_bytes':offset,'weight_mib':offset/2**20,
            'remaining_state_tensors':remaining_tensors,'remaining_state_raw_bytes':remaining_bytes,
            'largest_conv_linear_signed_accumulator_bits':largest_bits,'attention_bounds':attention,
            'binary_npz_exact_match':True,'all_export_hashes_match':True,
            'layer_bounds':layers,
            'limit':'Bounds only: full-network MACs still simulated in float32; not a bit-exact integer network'}
    (ROOT/'reports/quantization_export_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='layer_bounds'},indent=2))


if __name__=='__main__':
    main()
