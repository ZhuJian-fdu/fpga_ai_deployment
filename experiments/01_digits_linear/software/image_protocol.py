"""Protocol v1: raw pixels (not PNG/JPEG), CRC-8/SMBUS, 10 int32 LE scores."""
import struct


def crc8(data):
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 0xff
    return crc


def encode_request(seq, pixels):
    values = list(pixels)
    if len(values) != 64 or any(int(x) != x or not 0 <= x <= 16 for x in values):
        raise ValueError('Expected exactly 64 integer pixels in range 0..16')
    if not 0 <= seq <= 255:
        raise ValueError('Sequence must be 0..255')
    body = bytes([seq, 64]) + bytes(int(x) for x in values)
    return b'\xa5\x5a' + body + bytes([crc8(body)])


def decode_response(frame, seq):
    if len(frame) != 46 or frame[:2] != b'\x5a\xa5':
        raise ValueError(f'Expected 46-byte AI reply, received {len(frame)} bytes; check AI bitstream')
    if frame[2] != seq or frame[3] != 0 or frame[4] > 9:
        raise ValueError('Unexpected sequence, status or class')
    if crc8(frame[2:-1]) != frame[-1]:
        raise ValueError('Reply CRC mismatch')
    return frame[4], struct.unpack('<10i', frame[5:45])
