"""Generate independent Python-integer RTL oracles and run Icarus regressions."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import random
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/integer_head'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(72035)
    cases=[]
    for value in [-65535,-65533,-32768,-7,-5,-3,-1,0,1,3,5,7,32768,65533,65535]:
        for shift in [0,1,16,79]: cases.append((value,1,shift,[(0,0)]))
    cases += [((1<<47)-1,0x7fffffff,48,[(1,1),(-1,1)]),
              (-(1<<47),0xffffffff,79,[(-1,1)]),
              (0,0,0,[(-32768,-32768)]),
              (0,0xffffffff,47,[(-32768,32767),(32767,32767)])]
    for length in [1,2,17,96,1536]:
        for _ in range(12):
            cases.append((rng.randrange(-(1<<40),1<<40),rng.randrange(1,1<<32),rng.randrange(0,80),
                          [(rng.randrange(-32768,32768),rng.randrange(-32768,32768)) for _ in range(length)]))
    lines=[str(len(cases))]
    for bias,multiplier,shift,terms in cases:
        acc=bias;overflow=False
        for x,w in terms:
            value=acc+x*w;overflow |= not -(1<<47)<=value<(1<<47)
            acc=((value+(1<<47))%(1<<48))-(1<<47)
        # Independent Fraction rounding, not the implementation's round_shift_even.
        rounded=round(Fraction(acc*multiplier,1<<shift))
        saturated=not -32767<=rounded<=32767
        y=min(32767,max(-32767,rounded))
        lines.append(f'{bias&((1<<48)-1):012x} {multiplier:08x} {shift:02x} {len(terms)} {acc&((1<<48)-1):012x} {y&65535:04x} {int(saturated)} {int(overflow)}')
        lines.extend(f'{x&65535:04x} {w&65535:04x}' for x,w in terms)
    (OUT/'dot_vectors.txt').write_text('\n'.join(lines)+'\n')
    logs=[]
    def run(top,sources,case=None):
        exe=OUT/(top+('' if case is None else str(case))+'.vvp')
        cmd=['iverilog','-g2012','-s',top,'-o',str(exe)]
        if case is not None:cmd.append(f'-P{top}.CASE={case}')
        subprocess.run(cmd+[str(ROOT/s) for s in sources],check=True)
        r=subprocess.run(['vvp',str(exe)],cwd=OUT,capture_output=True,text=True,check=True)
        if 'PASS:' not in r.stdout or 'ERROR:' in r.stdout or 'WARNING:' in r.stdout:
            raise RuntimeError(r.stdout+r.stderr)
        print(r.stdout,end='');logs.append(r.stdout+r.stderr)
    run('tb_int16_dot_requant',['rtl/int16_dot_requant.v','sim/tb_int16_dot_requant.sv'])
    for case in [0,1,2]:
        run('tb_integer_head_selftest',['rtl/int16_dot_requant.v','rtl/integer_head_selftest.v','sim/tb_integer_head_selftest.sv'],case)
    (ROOT/'reports/integer_head_simulation.txt').write_text(''.join(logs))
    report={'date':'2026-11-25','directed_random_dot_cases':len(cases),'real_vector_dot_products':672,
            'wrapper_cases':['normal','corrupted_expected_output_detected','reset_during_test'],
            'passed':True,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ['rtl/int16_dot_requant.v','rtl/integer_head_selftest.v','sim/tb_int16_dot_requant.sv','sim/tb_integer_head_selftest.sv']}}
    (ROOT/'reports/integer_head_simulation.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
