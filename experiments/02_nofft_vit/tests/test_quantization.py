"""Independent NumPy oracles for rounding, saturation and integer dot products."""
import sys
from pathlib import Path
import unittest
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quantization_core import quantize, quantize_weight, Activations, apply_weights, load_export


class QuantizationTests(unittest.TestCase):
    def test_ties_and_saturation(self):
        x = np.array([-200, -127.6, -3.5, -2.5, -.5, .5, 2.5, 3.5, 127.6, 200], dtype=np.float32)
        q, clipped = quantize(torch.from_numpy(x), 1., 8)
        np.testing.assert_array_equal(q.numpy(), np.clip(np.rint(x), -127, 127))
        self.assertEqual(int(clipped.sum()), 4)

    def test_unsigned_probabilities(self):
        x = np.array([-.1, 0, .5, 1, 1.1], dtype=np.float32)
        q, _ = quantize(torch.from_numpy(x), 1/255, 8, True)
        np.testing.assert_array_equal(q.numpy(), [0, 0, 127, 255, 255])
        # Floating 1/255 is not exact: .5/scale is below the half-way tie in float32.

    def test_per_channel_zero_and_nonzero(self):
        w = torch.tensor([[0., 0., 0.], [-2., 1., 2.], [-.02, 0., .01]])
        q, s = quantize_weight(w, 8)
        self.assertEqual(float(s[0]), 1.)
        np.testing.assert_array_equal(q[0].numpy(), [0, 0, 0])
        np.testing.assert_allclose(s[1:].numpy(), [2/127, .02/127], rtol=1e-7)
        self.assertEqual(q.dtype, torch.int8)

    def test_integer_dot_reference(self):
        rng = np.random.default_rng(132)
        for wbits, abits in ((8,8), (8,12), (8,16), (16,16)):
            x = rng.normal(size=(4, 37)).astype(np.float32)
            w = torch.from_numpy(rng.normal(size=(7, 37)).astype(np.float32))
            qw, sw = quantize_weight(w, wbits)
            sx = float(np.max(np.abs(x))) / ((1 << (abits-1))-1)
            qx, _ = quantize(torch.from_numpy(x), sx, abits)
            integer = qx.numpy().astype(np.int64) @ qw.numpy().astype(np.int64).T
            expected = integer.astype(np.float64) * sx * sw.numpy()[None, :]
            fake = (qx*sx) @ (qw.float()*sw[:,None]).T
            np.testing.assert_allclose(fake.numpy(), expected, rtol=2e-5, atol=1e-5)

    def test_margin_and_exported_scales(self):
        ranges = {'x': {'min': -2., 'max': 1.}}
        a = Activations('quantize', ranges, 12, margin=1.25)
        b = Activations('quantize', bits=12, fixed_scales={'x': {'scale': a.scale('x')}})
        self.assertAlmostEqual(a.scale('x'), 2.5/2047)
        x = torch.tensor([-3., -.5, 0., 1., 3.])
        self.assertTrue(torch.equal(a.apply('x',x), b.apply('x',x)))

    def test_export_state_coverage(self):
        a = torch.nn.Sequential(torch.nn.Linear(5,3), torch.nn.LayerNorm(3)).eval()
        controller = Activations('quantize', {'0.input': {'min': -2., 'max': 2.}}, 16)
        tensors, _ = apply_weights(a,16,controller)
        remaining = {k:v.numpy().copy() for k,v in a.state_dict().items() if k not in ('0.weight','0.bias')}
        b = torch.nn.Sequential(torch.nn.Linear(5,3), torch.nn.LayerNorm(3)).eval()
        load_export(b,tensors,remaining)
        for key,value in a.state_dict().items(): self.assertTrue(torch.equal(value,b.state_dict()[key]))
        del remaining['1.weight']
        with self.assertRaises(ValueError): load_export(b,tensors,remaining)


if __name__ == '__main__':
    unittest.main()
