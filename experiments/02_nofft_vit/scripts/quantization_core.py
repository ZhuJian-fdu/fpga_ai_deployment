"""Explicit PTQ numerical model; floating MACs/nonlinearities, not integer RTL.

Weights: symmetric per-output-channel; activations: static per-site scale.
Signed range [-qmax,qmax] deliberately excludes the most negative two's
complement code. Rounding is nearest, ties to even; saturation follows rounding.
"""
import math
import types
import torch
from torch import nn
from timm.models.vision_transformer import Attention


def quantize(x, scale, bits, unsigned=False):
    qmax = (1 << (bits if unsigned else bits - 1)) - 1
    qmin = 0 if unsigned else -qmax
    rounded = torch.round(x / scale)
    clipped = (rounded < qmin) | (rounded > qmax)
    return rounded.clamp(qmin, qmax), clipped


def quantize_weight(weight, bits):
    qmax = (1 << (bits - 1)) - 1
    maximum = weight.abs().flatten(1).amax(1)
    scale = torch.where(maximum == 0, torch.ones_like(maximum), maximum / qmax)
    view = scale.reshape((-1,) + (1,) * (weight.ndim - 1))
    q, _ = quantize(weight, view, bits)
    return q.to(torch.int8 if bits == 8 else torch.int16), scale


class Activations:
    def __init__(self, mode, ranges=None, bits=None, margin=1.0, fixed_scales=None):
        self.mode, self.ranges, self.bits = mode, ranges if ranges is not None else {}, bits
        if margin < 1.0:
            raise ValueError('Calibration range margin must be >= 1')
        self.margin, self.fixed_scales = margin, fixed_scales
        self.stats = {}

    def scale(self, name, unsigned=False):
        if self.fixed_scales is not None:
            return self.fixed_scales[name]['scale']
        if unsigned:
            return 1.0 / ((1 << self.bits) - 1)  # softmax has known [0,1] range
        r = self.ranges[name]
        maximum = self.margin * max(abs(r['min']), abs(r['max']))
        return maximum / ((1 << (self.bits - 1)) - 1) if maximum else 1.0

    def apply(self, name, x, unsigned=False):
        if self.mode == 'observe':
            lo, hi = float(x.min()), float(x.max())
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise ValueError(f'Nonfinite calibration activation: {name}')
            r = self.ranges.setdefault(name, {'min': lo, 'max': hi, 'elements': 0,
                                               'unsigned': unsigned})
            r['min'], r['max'] = min(r['min'], lo), max(r['max'], hi)
            r['elements'] += x.numel()
            return x
        if self.bits is None:
            return x
        scale = self.scale(name, unsigned)
        q, clipped = quantize(x, scale, self.bits, unsigned)
        s = self.stats.setdefault(name, {'elements': 0, 'clipped': 0})
        s['elements'] += x.numel()
        s['clipped'] += int(clipped.sum())
        return q * scale


def attach_activations(model, controller):
    """Preserve timm 1.0.15 explicit Attention order; validate bypass against FP32."""
    for name, module in model.named_modules():
        if isinstance(module, (nn.Linear, nn.Conv2d)):
            def pre_hook(_module, inputs, site=name + '.input'):
                return (controller.apply(site, inputs[0]),) + inputs[1:]
            module.register_forward_pre_hook(pre_hook)
        if isinstance(module, Attention):
            def forward(self, x, site=name):
                batch, tokens, channels = x.shape
                qkv = self.qkv(x).reshape(batch, tokens, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
                q, k, v = qkv.unbind(0)
                q, k = self.q_norm(q), self.k_norm(k)
                q = controller.apply(site + '.q_scaled', q * self.scale)
                k = controller.apply(site + '.k', k)
                v = controller.apply(site + '.v', v)
                prob = (q @ k.transpose(-2, -1)).softmax(dim=-1)
                prob = controller.apply(site + '.prob', self.attn_drop(prob), unsigned=True)
                x = (prob @ v).transpose(1, 2).reshape(batch, tokens, channels)
                return self.proj_drop(self.proj(x))
            module.forward = types.MethodType(forward, module)


def apply_weights(model, bits, controller):
    """Return exportable integer tensors and conservative accumulator bounds."""
    tensors, layers = {}, {}
    with torch.no_grad():
        for name, module in model.named_modules():
            if not isinstance(module, (nn.Linear, nn.Conv2d)):
                continue
            q, scale = quantize_weight(module.weight, bits)
            shape = (-1,) + (1,) * (module.weight.ndim - 1)
            module.weight.copy_(q.float() * scale.reshape(shape))
            tensors[name + '.weight_int'] = q.numpy().copy()
            tensors[name + '.weight_scale'] = scale.numpy().copy()
            fanin = module.weight[0].numel()
            layer = {'weight_bits': bits, 'shape': list(q.shape), 'dot_product_terms': fanin}
            if controller.bits is not None:
                input_scale = controller.scale(name + '.input')
                bmax = 0
                if module.bias is not None:
                    bias_scale = scale.double() * input_scale
                    rounded = torch.round(module.bias.double() / bias_scale)
                    if not torch.isfinite(rounded).all() or (rounded.abs() >= 2**62).any():
                        raise ValueError(f'Bias cannot fit signed int64: {name}')
                    bq = rounded.to(torch.int64)
                    module.bias.copy_((bq.double() * bias_scale).float())
                    tensors[name + '.bias_int'] = bq.numpy().copy()
                    tensors[name + '.bias_scale'] = bias_scale.numpy().copy()
                    bmax = int(bq.abs().max())
                bound = fanin * ((1 << (bits - 1)) - 1) * ((1 << (controller.bits - 1)) - 1) + bmax
                layer.update(input_bits=controller.bits, input_scale=input_scale,
                             accumulator_abs_bound=bound, accumulator_signed_bits=bound.bit_length() + 1)
            layers[name] = layer
    return tensors, layers


def load_export(model, tensors, remaining):
    """Reload payloads using only saved integer tensors/scales and residual state."""
    state = model.state_dict()
    covered = set(remaining)
    for name, module in model.named_modules():
        if isinstance(module, (nn.Linear, nn.Conv2d)):
            covered.add(name + '.weight')
            if module.bias is not None:
                covered.add(name + '.bias')
    if covered != set(state):
        raise ValueError('Export does not cover exactly the complete model state')
    for name, value in remaining.items():
        state[name] = torch.from_numpy(value.copy())
    for name, module in model.named_modules():
        if not isinstance(module, (nn.Linear, nn.Conv2d)):
            continue
        q = torch.from_numpy(tensors[name + '.weight_int'].copy())
        scale = torch.from_numpy(tensors[name + '.weight_scale'].copy())
        state[name + '.weight'] = q.float() * scale.reshape((-1,) + (1,) * (q.ndim - 1))
        if module.bias is not None:
            bq = torch.from_numpy(tensors[name + '.bias_int'].copy())
            bs = torch.from_numpy(tensors[name + '.bias_scale'].copy())
            state[name + '.bias'] = (bq.double() * bs).float()
    model.load_state_dict(state, strict=True)
