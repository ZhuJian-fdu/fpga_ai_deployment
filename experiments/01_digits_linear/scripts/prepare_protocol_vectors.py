"""Build byte-level golden frames from the already exported integer test vectors."""
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from image_protocol import crc8,encode_request,decode_response


def main():
    assert crc8(b'123456789')==0xf4  # standard CRC-8/SMBUS check value
    out=ROOT/'build/model'
    read=lambda name: [int(s,16) for s in (out/name).read_text().split()]
    images=read('images.mem'); scores=read('scores.mem'); preds=read('predictions.mem')
    requests=[]; responses=[]
    for i,pred in enumerate(preds):
        requests.extend(encode_request(i&255,images[i*64:i*64+64]))
        signed=[s if s<2**31 else s-2**32 for s in scores[i*10:i*10+10]]
        body=bytes([i&255,0,pred])+struct.pack('<10i',*signed)
        frame=b'\x5a\xa5'+body+bytes([crc8(body)])
        assert decode_response(frame,i&255)==(pred,tuple(signed))
        responses.extend(frame)
    # Invalid pixel with a correct CRC: must fail semantic validation, not CRC only.
    invalid=bytearray(requests[:69]); invalid[4]=17; invalid[-1]=crc8(invalid[2:-1])
    for name,values in [('requests.mem',requests),('responses.mem',responses),('invalid_pixel.mem',invalid)]:
        (out/name).write_text(''.join(f'{v:02x}\n' for v in values),encoding='ascii')
    for bad in [[],[0]*63,[0]*65,[17]*64,[-1]*64,[0.5]*64]:
        try: encode_request(0,bad)
        except ValueError: pass
        else: raise AssertionError('Invalid pixels accepted')
    first=bytes(responses[:46])
    for bad in [first[:-1],bytes([0])+first[1:],first[:-1]+bytes([first[-1]^1])]:
        try: decode_response(bad,0)
        except ValueError: pass
        else: raise AssertionError('Invalid response accepted')
    print(f'PASS: {len(preds)} protocol vectors; CRC standard check and codec rejection checks.')


if __name__=='__main__': main()
