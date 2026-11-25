"""Run the original network on the frozen development split, leaving holdout unused."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import sys
import time
import numpy as np
from audit_dataset import load_sample

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    manifest_bytes = (ROOT / "build/dataset/manifest.json").read_bytes()
    audit = json.loads((ROOT / "reports/dataset_audit.json").read_text(encoding="utf-8"))
    if hashlib.sha256(manifest_bytes).hexdigest() != audit["manifest_sha256"]:
        raise ValueError("Dataset manifest changed")
    manifest = json.loads(manifest_bytes)
    records = {r["file"]: r for r in manifest["records"]}
    names = manifest["splits"]["development"]
    model_dir = ROOT / "build/model_source"
    source_audit = json.loads((ROOT / "reports/source_update_20261125.json").read_text(encoding="utf-8"))
    for member, expected in source_audit["archive_members"].items():
        name = Path(member).name
        if name in ("vit_model.py", "psf_zernike_model_fcas_vit.py", "model_best.pth"):
            if hashlib.sha256((model_dir / name).read_bytes()).hexdigest() != expected["sha256"]:
                raise ValueError(f"Model source changed: {name}")
    import torch
    import timm
    torch.set_num_threads(4)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    # Explicit attention operations provide an inspectable future RTL reference.
    timm.layers.set_fused_attn(False)
    sys.path.insert(0, str(model_dir))
    from psf_zernike_model_fcas_vit import create_model
    model = create_model(patch_size=8, pretrained=False, dropout=0.0)
    state = torch.load(model_dir / "model_best.pth", map_location="cpu", weights_only=True)
    state = {k.removeprefix("module."): v for k, v in state.items()}
    model.load_state_dict(state, strict=True)
    model.eval()
    assert sum(p.numel() for p in model.parameters()) == 21902619
    assert tuple(model.backbone.patch_embed.proj.weight.shape) == (384, 5, 16, 16)
    predictions, targets = [], []
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(names), args.batch_size):
            xs, ys = [], []
            for name in names[start:start + args.batch_size]:
                data = (args.source / name).read_bytes()
                if hashlib.sha256(data).hexdigest() != records[name]["file_sha256"]:
                    raise ValueError(f"Sample changed: {name}")
                _, _, x, y = load_sample(data)
                xs.append(x); ys.append(y[:, :6].reshape(42))
            pred = model(torch.from_numpy(np.stack(xs))).numpy()
            if pred.shape != (len(xs), 42) or not np.isfinite(pred).all():
                raise ValueError("Invalid model output")
            predictions.append(pred.copy()); targets.append(np.stack(ys))
            if start == 0 or (start + len(xs)) % 100 == 0:
                print(f"FP32 {start + len(xs)}/{len(names)}", flush=True)
    pred, target = np.concatenate(predictions), np.concatenate(targets)
    mask = np.ones(42, dtype=bool); mask[36:39] = False
    error = pred[:, mask].astype(np.float64) - target[:, mask].astype(np.float64)
    out = ROOT / "build/reference"
    out.mkdir(parents=True, exist_ok=True)
    output = out / "development_fp32.npz"
    np.savez_compressed(output, names=np.array(names), predictions=pred, targets=target, mask=mask)
    # Batch-size sensitivity check, separate from ground-truth accuracy.
    sample_bytes = (args.source / names[0]).read_bytes()
    x = load_sample(sample_bytes)[2]
    with torch.inference_mode():
        single = model(torch.from_numpy(x[None])).numpy()[0]
    batch_delta = float(np.max(np.abs(single - pred[0])))
    batch_consistent = bool(np.allclose(single, pred[0], rtol=1e-5, atol=1e-6))
    report = {"date": "2026-11-25", "device": "cpu", "python": platform.python_version(),
              "torch": torch.__version__, "timm": timm.__version__, "numpy": np.__version__,
              "attention": "explicit; fused attention disabled", "strict_checkpoint_load": True,
              "parameters": 21902619, "patch_size_actual": 16,
              "samples": len(names), "split": "development", "reserved_holdout_inference": False,
              "masked_positions": 39, "excluded_flat_positions": [36, 37, 38],
              "masked_pooled_rmse": float(np.sqrt(np.mean(error**2))),
              "masked_mae": float(np.mean(np.abs(error))),
              "masked_max_abs_error": float(np.max(np.abs(error))),
              "batch_consistency": {"passed": batch_consistent, "max_abs_difference": batch_delta,
                                    "rtol": 1e-5, "atol": 1e-6},
              "elapsed_seconds_including_io": time.perf_counter() - started,
              "dataset_manifest_sha256": audit["manifest_sha256"],
              "checkpoint_sha256": source_audit["checkpoint"]["sha256"],
              "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "scope": "FP32 software baseline only; not quantized or FPGA inference; units unconfirmed"}
    (ROOT / "reports/fp32_reference.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not batch_consistent:
        raise SystemExit("Batch comparison exceeded diagnostic tolerance; inspect before quantization")


if __name__ == "__main__":
    main()
