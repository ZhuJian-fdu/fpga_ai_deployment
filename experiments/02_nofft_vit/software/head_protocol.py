"""Fixed-length integer-head UART protocol, little endian, CRC-16/CCITT-FALSE."""
import binascii
import struct

REQUEST_BYTES=198
RESPONSE_BYTES=385


def crc16(data):return binascii.crc_hqx(data,0xffff)


def request(sequence,values):
    if len(values)!=96:raise ValueError('Expected 96 int16 inputs')
    body=struct.pack('<H96h',sequence,*map(int,values))
    return b'\xa5\x5a'+body+struct.pack('<H',crc16(body))


def response(sequence,accumulators,outputs,saturated,status=0,errors=None):
    """Reference packet generator for simulation; never used as board output."""
    if errors is None:errors=[False]*42
    if not all(len(v)==42 for v in [accumulators,outputs,saturated,errors]):raise ValueError('Expected 42 outputs')
    body=bytearray(struct.pack('<HB',sequence,status))
    for acc,y,sat,error in zip(accumulators,outputs,saturated,errors):
        body+=int(acc).to_bytes(6,'little',signed=True)+struct.pack('<hB',int(y),int(bool(sat))|int(bool(error))*2)
    return b'\x5a\xa5'+body+struct.pack('<H',crc16(body))


def decode(packet,sequence,allow_error=False):
    if len(packet)!=RESPONSE_BYTES or packet[:2]!=b'\x5a\xa5':raise ValueError('Response length/header mismatch; check downloaded bitstream')
    body=packet[2:-2]
    if crc16(body)!=int.from_bytes(packet[-2:],'little'):raise ValueError('Response CRC mismatch')
    seq,status=struct.unpack_from('<HB',body)
    if seq!=sequence:raise ValueError('Response sequence mismatch')
    if status and not allow_error:raise ValueError(f'Board error status {status}')
    values=[]
    for i in range(42):
        offset=3+9*i;acc=int.from_bytes(body[offset:offset+6],'little',signed=True)
        y,flags=struct.unpack_from('<hB',body,offset+6)
        if flags&~3:raise ValueError('Unknown output flags')
        values.append((acc,y,bool(flags&1),bool(flags&2)))
    return status,values
