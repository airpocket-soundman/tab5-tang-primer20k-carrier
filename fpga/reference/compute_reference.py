"""Bit-exact proposed INT8 accelerator semantics; no FPGA or speed claims.

Only Python's standard library is required. Arrays are plain integer lists.
"""

INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1


def checked_i32(value):
    if type(value) is not int:
        raise ValueError("INT32 must be an integer")
    if not INT32_MIN <= value <= INT32_MAX:
        raise OverflowError("ACC_OVERFLOW")
    return value


def _int8(values, name):
    if any(type(v) is not int or not -128 <= v <= 127 for v in values):
        raise ValueError(name + " must contain signed INT8")


def requantize(acc, multiplier, shift, zero_point=0, lower=-128, upper=127):
    """round_away_at_tie(acc * multiplier / 2**shift), then clamp.

    multiplier/shift encode the *effective* real scale ratio, per output channel.
    Product is signed INT64; right shift is rounded symmetrically, not truncated.
    """
    checked_i32(acc)
    if type(multiplier) is not int or type(shift) is not int or not 0 <= multiplier <= INT32_MAX or not 0 <= shift <= 62:
        raise ValueError("invalid scale encoding")
    if any(type(v) is not int for v in (lower, upper, zero_point)) or not -128 <= lower <= upper <= 127 or not -128 <= zero_point <= 127:
        raise ValueError("invalid output limits")
    product = acc * multiplier
    magnitude = (abs(product) + ((1 << (shift - 1)) if shift else 0)) >> shift
    rounded = -magnitude if product < 0 else magnitude
    return min(upper, max(lower, rounded + zero_point))


def tiled_gemm(a, b, bias=None, input_zero_point=0, tile=(8, 8, 16)):
    """A[M,K] x symmetric B[K,N] -> INT32[M,N]. Tiles do not alter order."""
    if not a or not b or not a[0] or not b[0]:
        raise ValueError("empty matrix")
    m, k, n = len(a), len(a[0]), len(b[0])
    if len(b) != k or any(len(r) != k for r in a) or any(len(r) != n for r in b):
        raise ValueError("matrix shape mismatch")
    _int8([v for r in a for v in r], "A")
    _int8([v for r in b for v in r], "B")
    _int8([input_zero_point], "zero point")
    if len(tile) != 3 or any(type(v) is not int or v <= 0 for v in tile):
        raise ValueError("invalid tile")
    bias = [0] * n if bias is None else bias
    if len(bias) != n:
        raise ValueError("bias length")
    out = [[checked_i32(bias[j]) for j in range(n)] for _ in range(m)]
    tm, tn, tk = tile
    for mi in range(0, m, tm):
        for nj in range(0, n, tn):
            for kk in range(0, k, tk):
                for i in range(mi, min(mi + tm, m)):
                    for j in range(nj, min(nj + tn, n)):
                        for p in range(kk, min(kk + tk, k)):
                            out[i][j] = checked_i32(out[i][j] + (a[i][p] - input_zero_point) * b[p][j])
    return out


def conv2d(x, weights, shape, weight_shape, bias=None, stride=(1, 1),
           padding=(0, 0, 0, 0), dilation=(1, 1), input_zero_point=0):
    """Flat contiguous NCHW/OIHW; group=1; padding top,left,bottom,right.

    Returns (flat INT32 output, NCHW shape). Padding equals input zero point.
    Reduction order is input channel, kernel row, kernel column.
    """
    if len(shape) != 4 or len(weight_shape) != 4:
        raise ValueError("rank must be four")
    if len(stride) != 2 or len(dilation) != 2 or len(padding) != 4:
        raise ValueError("invalid spatial parameter rank")
    if any(type(v) is not int for v in (*shape, *weight_shape, *stride, *dilation, *padding)):
        raise ValueError("dimensions must be integers")
    batch, channels, height, width = shape
    outputs, wc, kh, kw = weight_shape
    if min(*shape, *weight_shape, *stride, *dilation) <= 0 or min(padding) < 0:
        raise ValueError("invalid dimensions")
    if channels != wc or len(x) != batch * channels * height * width or len(weights) != outputs * wc * kh * kw:
        raise ValueError("tensor shape mismatch")
    _int8(x, "input")
    _int8(weights, "weights")
    _int8([input_zero_point], "zero point")
    pt, pl, pb, pr = padding
    sy, sx = stride
    dy, dx = dilation
    oh = (height + pt + pb - dy * (kh - 1) - 1) // sy + 1
    ow = (width + pl + pr - dx * (kw - 1) - 1) // sx + 1
    if oh <= 0 or ow <= 0:
        raise ValueError("empty output")
    bias = [0] * outputs if bias is None else bias
    if len(bias) != outputs:
        raise ValueError("bias length")
    result = []
    for n in range(batch):
        for o in range(outputs):
            for y in range(oh):
                for z in range(ow):
                    acc = checked_i32(bias[o])
                    for c in range(channels):
                        for ky in range(kh):
                            for kx in range(kw):
                                iy, ix = y * sy - pt + ky * dy, z * sx - pl + kx * dx
                                v = x[((n * channels + c) * height + iy) * width + ix] if 0 <= iy < height and 0 <= ix < width else input_zero_point
                                w = weights[((o * channels + c) * kh + ky) * kw + kx]
                                acc = checked_i32(acc + (v - input_zero_point) * w)
                    result.append(acc)
    return result, (batch, outputs, oh, ow)
