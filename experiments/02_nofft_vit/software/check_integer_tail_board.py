"""Send runtime hidden vectors and compare returned integers. Never programs FPGA."""
from pathlib import Path
import argparse
import hashlib
import json
import time
from datetime import datetime,timezone,timedelta
import numpy as np
import serial
from tail_protocol import request,decode,RESPONSE_BYTES

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',required=True)
    parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    reference=ROOT/'build/integer_tail/reference.npz'
    report=json.loads((ROOT/'reports/integer_tail_reference.json').read_text())
    if hashlib.sha256(reference.read_bytes()).hexdigest()!=report['files']['reference.npz']['sha256']:
        raise ValueError('Reference changed')
    with np.load(reference,allow_pickle=False) as data:
        if not 1<=args.limit<=len(data['names']):raise ValueError('Invalid limit')
        checked=0;failures=[];started=time.monotonic()
        try:
            with serial.Serial(args.port,115200,timeout=.2,write_timeout=2) as port:
                port.reset_input_buffer()
                for i in range(args.limit):
                    packet=request(i,data['inputs'][i]);written=port.write(packet)
                    if written!=len(packet):raise RuntimeError('Partial request write')
                    port.flush();received=bytearray();deadline=time.monotonic()+3
                    while len(received)<RESPONSE_BYTES and time.monotonic()<deadline:
                        received+=port.read(RESPONSE_BYTES-len(received))
                    _,values=decode(received,i)
                    for j,(acc,y,sat,error) in enumerate(values):
                        expected=(int(data['accumulators'][i,j]),int(data['outputs'][i,j]),bool(data['saturated'][i,j]),False)
                        if (acc,y,sat,error)!=expected:
                            failures.append({'sample':str(data['names'][i]),'output':j,'actual':[acc,y,sat,error],'expected':expected})
                    checked+=1
                    if failures:break
                    if checked%100==0 or checked==args.limit:print(f'Board exact match {checked}/{args.limit}',flush=True)
        except Exception as exc:
            failures.append({'error':str(exc)})
        result={'date':datetime.now(timezone(timedelta(hours=8))).isoformat(),'port':args.port,'baud':115200,
                'source':'automated_UART_readback','requested_samples':args.limit,'checked_samples':checked,
                'compared_outputs':checked*42,'passed':not failures and checked==args.limit,'failures':failures,
                'elapsed_seconds':time.monotonic()-started,'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
                'scope':'head.4 -> GELU -> head.7; earlier network CPU Q/DQ',
                'holdout_used':False}
    (ROOT/'reports/integer_tail_uart_hardware.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
