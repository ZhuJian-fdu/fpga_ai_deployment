"""Integer contract shared by reference generation (RTL has independent code)."""
import math


def multiplier_shift(ratio):
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError('Scale ratio must be positive and finite')
    fraction, exponent = math.frexp(ratio)
    multiplier = round(fraction * (1 << 31))
    shift = 31 - exponent
    if multiplier == 1 << 31:
        multiplier >>= 1
        shift -= 1
    if not (0 < multiplier < 1 << 31 and 0 <= shift <= 79):
        raise ValueError('Ratio outside current hardware format')
    return multiplier, shift


def round_shift_even(value, shift):
    if not 0 <= shift <= 79:
        raise ValueError('Invalid shift')
    magnitude = abs(int(value))
    quotient, remainder = divmod(magnitude, 1 << shift)
    half = (1 << shift) >> 1
    if shift and (remainder > half or (remainder == half and quotient & 1)):
        quotient += 1
    return -quotient if value < 0 else quotient


def requantize(accumulator, multiplier, shift):
    value = round_shift_even(int(accumulator) * int(multiplier), shift)
    saturated = value < -32767 or value > 32767
    return min(32767, max(-32767, value)), saturated
