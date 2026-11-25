"""Send held-out images to the FPGA and compare every score, not just labels."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import serial
from sklearn.datasets import load_digits
from image_protocol import encode_request, decode_response

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='Verified board UART port, e.g. COM11')
    parser.add_argument('--count', type=int, default=10, help='1..450 test images, default 10')
    args = parser.parse_args()
    model_path = ROOT/'build/model/model.npz'
    if not model_path.exists():
        raise SystemExit('Run train_export.py and rebuild the AI bitstream first.')
    model = np.load(model_path)
    ids = model['test_ids']
    if not 1 <= args.count <= len(ids):
        parser.error(f'--count must be 1..{len(ids)}')
    data = load_digits()
    pixels = data.data[ids[:args.count]].astype(np.int64)
    labels = data.target[ids[:args.count]]
    golden = pixels @ model['weights'].astype(np.int64).T + model['biases'].astype(np.int64)
    records = []
    try:
        with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=2,
                           bytesize=8, parity='N', stopbits=1,
                           xonxoff=False, rtscts=False, dsrdtr=False) as port:
            time.sleep(0.2)  # exceeds FPGA partial-frame timeout
            port.reset_input_buffer()
            for i, image in enumerate(pixels):
                seq = i & 255
                request = encode_request(seq, image)
                begin = time.monotonic()
                if port.write(request) != len(request):
                    raise ValueError('Incomplete write')
                reply = bytearray()
                while len(reply)<46 and time.monotonic()-begin<2:
                    reply.extend(port.read(46-len(reply)))
                pred, scores = decode_response(bytes(reply), seq)
                if tuple(golden[i]) != scores or pred != int(np.argmax(golden[i])):
                    raise ValueError(f'FPGA/Python mismatch at sample {i}: pred={pred}, scores={scores}, golden={golden[i].tolist()}')
                records.append({'test_index':i,'dataset_index':int(ids[i]),'label':int(labels[i]),
                                'prediction':pred,'scores':list(scores),
                                'roundtrip_ms':(time.monotonic()-begin)*1000})
                if i<10 or (i+1)%50==0:
                    print(f'{i+1}/{args.count}: label={labels[i]} FPGA={pred} Python={np.argmax(golden[i])} scores=MATCH')
            if port.read(1):
                raise ValueError('Unexpected extra bytes after reply')
    except (serial.SerialException, ValueError) as exc:
        raise SystemExit(f'FAIL: {exc}') from exc
    result = {'port':args.port,'images':args.count,'score_comparisons':args.count*10,
              'all_scores_match':True,'accuracy':sum(r['label']==r['prediction'] for r in records)/len(records),
              'model_npz_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
              'latency_note':'PC serial round-trip, not FPGA compute latency', 'records':records}
    out = ROOT/'build'/f'board_inference_{args.count}.json'
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f"PASS: {args.count} images, {args.count*10} exact scores, accuracy={result['accuracy']:.2%}")
    print(f'Report: {out}')


if __name__ == '__main__':
    main()
