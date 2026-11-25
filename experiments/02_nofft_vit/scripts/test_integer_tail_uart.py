from pathlib import Path
import hashlib
import json
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from tail_protocol import request,response,decode,crc16


def main():
    out=ROOT/'build/integer_tail'
    assert crc16(b'123456789')==0x29b1
    requests=[];responses=[]
    with np.load(out/'reference.npz',allow_pickle=False) as d:
        for index,sample in enumerate([0,999,10,500,1]):
            seq=0x1200+index
            packet=bytearray(request(seq,d['inputs'][sample]))
            if index==2:
                packet[-1]^=1
                reply=response(seq,[0]*42,[0]*42,[False]*42,status=1)
            else:reply=response(seq,d['accumulators'][sample],d['outputs'][sample],d['saturated'][sample])
            status,decoded=decode(reply,seq,allow_error=True)
            assert status==(1 if index==2 else 0)
            if not status:
                for j,(acc,y,sat,err) in enumerate(decoded):
                    assert acc==int(d['accumulators'][sample,j]) and y==int(d['outputs'][sample,j]) and sat==bool(d['saturated'][sample,j]) and not err
            for corrupted in [reply[:-1],reply[:50]+bytes([reply[50]^1])+reply[51:]]:
                try:decode(corrupted,seq)
                except ValueError:pass
                else:raise AssertionError('Malformed reply accepted')
            requests.extend(packet);responses.extend(reply)
    for name,data in [('uart_requests.mem',requests),('uart_responses.mem',responses)]:
        (out/name).write_text(''.join(f'{v:02x}\n' for v in data))
    source=[ROOT/'rtl/int16_dot_requant.v',ROOT/'rtl/integer_dense_engine.v',ROOT/'rtl/integer_tail_engine.v',ROOT/'rtl/integer_tail_uart.v',
            ROOT.parent/'01_digits_linear/rtl/uart_rx.v',ROOT.parent/'01_digits_linear/rtl/uart_tx.v',ROOT/'sim/tb_integer_tail_uart.sv']
    exe=out/'integer_tail_uart.vvp'
    subprocess.run(['iverilog','-g2012','-s','tb_integer_tail_uart','-o',str(exe)]+list(map(str,source)),check=True)
    r=subprocess.run(['vvp',str(exe)],cwd=out,capture_output=True,text=True,check=True)
    if 'PASS:' not in r.stdout or 'ERROR:' in r.stdout or 'WARNING:' in r.stdout:raise RuntimeError(r.stdout+r.stderr)
    print(r.stdout)
    (ROOT/'reports/integer_tail_uart_simulation.txt').write_text(r.stdout+r.stderr)
    (ROOT/'reports/integer_tail_uart_simulation.json').write_text(json.dumps({'date':'2026-11-25','passed':True,
        'transactions':5,'reply_bytes_compared':1925,'checks':['actual_serial_lines','runtime_input_replacement','CRC_reject','timeout_recovery','reset','host_decoder'],
        'source_sha256':{str(f.relative_to(ROOT.parent)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source}},indent=2)+'\n')


if __name__=='__main__':main()
