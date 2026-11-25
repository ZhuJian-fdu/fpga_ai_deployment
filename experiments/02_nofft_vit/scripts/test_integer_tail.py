"""Check both layers, intermediate GELU codes, backpressure and reset recovery."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'build/integer_tail'
    with np.load(out/'reference.npz',allow_pickle=False) as d:
        selected=list(range(8))
        for i in np.argsort(-np.max(np.abs(d['pre_acc']),axis=1)):
            if int(i) not in selected:selected.append(int(i))
            if len(selected)==16:break
        for name,key,bits in [('inputs','inputs',16),('pre_acc','pre_acc',48),('pre_codes','pre_codes',16),
                              ('gelu_codes','gelu_codes',16),('acc','accumulators',48),('outputs','outputs',16)]:
            (out/f'test_{name}.mem').write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n' for v in d[key][selected].reshape(-1)))
    sources=[ROOT/'rtl'/f for f in ['int16_dot_requant.v','integer_dense_engine.v','integer_tail_engine.v']]+[ROOT/'sim/tb_integer_tail_engine.sv']
    exe=out/'integer_tail.vvp'
    subprocess.run(['iverilog','-g2012','-s','tb_integer_tail_engine','-o',str(exe)]+list(map(str,sources)),check=True)
    run=subprocess.run(['vvp',str(exe)],cwd=out,capture_output=True,text=True)
    log=run.stdout+run.stderr;print(log)
    if run.returncode or 'PASS:' not in log or 'ERROR:' in log or 'WARNING:' in log:raise RuntimeError(log)
    (ROOT/'reports/integer_tail_simulation.txt').write_text(log)
    report={'date':'2026-11-25','passed':True,'selected_development_indices':selected,'intermediate_values':1536,'final_records':672,
        'checks':['pre_accumulators','pre_requant','GELU_codes','final_accumulators','final_requant','runtime_input_replacement','backpressure_stability','reset_abort_recovery'],
        'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (ROOT/'reports/integer_tail_simulation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
