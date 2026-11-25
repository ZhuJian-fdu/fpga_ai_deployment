"""Read supplied NumPy object samples, audit data and freeze disjoint splits.

Only NumPy array reconstruction is allowed during unpickling. Sources remain
unchanged; detailed hashes/splits stay in ignored build/, compact summary in reports/.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import pickle
from collections import Counter
from datetime import datetime, timezone, timedelta
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class ArrayUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {("numpy", "ndarray"): np.ndarray, ("numpy", "dtype"): np.dtype}
        for prefix in ("numpy.core.multiarray", "numpy._core.multiarray"):
            allowed[(prefix, "_reconstruct")] = np.core.multiarray._reconstruct
            allowed[(prefix, "scalar")] = np.core.multiarray.scalar
        if (module, name) not in allowed:
            raise ValueError(f"Unsupported pickle global: {module}.{name}")
        return allowed[(module, name)]


def load_sample(data):
    stream = io.BytesIO(data)
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
    elif version == (2, 0):
        shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
    else:
        raise ValueError(f"Unsupported NPY version: {version}")
    if shape != (2,) or dtype != np.dtype(object):
        raise ValueError(f"Expected object array (2,), got {shape}, {dtype}")
    sample = ArrayUnpickler(stream).load()
    if not isinstance(sample, np.ndarray) or sample.shape != (2,):
        raise ValueError("Unexpected sample container")
    images, labels = sample
    if not isinstance(labels, dict) or "gt_a" not in labels:
        raise ValueError("Missing gt_a")
    labels = labels["gt_a"]
    for value, expected in ((images, (5, 112, 112)), (labels, (7, 30))):
        if not isinstance(value, np.ndarray) or value.shape != expected or value.dtype.kind != "f":
            raise ValueError(f"Unexpected numeric array: {getattr(value, 'shape', None)}")
        if not np.isfinite(value).all():
            raise ValueError("Nonfinite values")
    x, y = images.astype(np.float32), labels.astype(np.float32)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Overflow after float32 conversion")
    return images, labels, x, y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--calibration", type=int, default=300)
    parser.add_argument("--development", type=int, default=1000)
    parser.add_argument("--independent-confirmed", action="store_true",
                        help="Only use when the data owner confirmed no training/model-selection use")
    args = parser.parse_args()
    if args.calibration < 1 or args.development < 1:
        raise ValueError("Split sizes must be positive")
    files = sorted(args.source.glob("*.npy"), key=lambda p: p.name)
    if len(files) <= args.calibration + args.development:
        raise ValueError("Insufficient samples for reserved holdout")
    records, problems, seen, duplicates = [], [], {}, []
    input_types, label_types = Counter(), Counter()
    minima, maxima = np.full(5, np.inf), np.full(5, -np.inf)
    label_min, label_max = np.inf, -np.inf
    outside = 0
    for i, file in enumerate(files, 1):
        try:
            data = file.read_bytes()
            images, labels, x, y = load_sample(data)
            digest = hashlib.sha256(x.tobytes(order="C")).hexdigest()
            if digest in seen:
                duplicates.append([seen[digest], file.name])
            else:
                seen[digest] = file.name
            records.append({"file": file.name, "file_sha256": hashlib.sha256(data).hexdigest(),
                            "input_fp32_sha256": digest})
            input_types[str(images.dtype)] += 1
            label_types[str(labels.dtype)] += 1
            minima = np.minimum(minima, images.min(axis=(1, 2)))
            maxima = np.maximum(maxima, images.max(axis=(1, 2)))
            label_min, label_max = min(label_min, float(y.min())), max(label_max, float(y.max()))
            outside += int((images < 0).any() or (images > 1).any())
        except Exception as exc:
            problems.append({"file": file.name, "error": str(exc)})
        if i % 1000 == 0:
            print(f"Audited {i}/{len(files)}; invalid={len(problems)}; duplicate_inputs={len(duplicates)}", flush=True)
    out = ROOT / "build/dataset"
    out.mkdir(parents=True, exist_ok=True)
    # Do not silently create potentially leaking splits if inputs repeat.
    ok = not problems and not duplicates
    payload = {"source": str(args.source.resolve()), "records": records,
               "invalid": problems, "duplicate_input_pairs": duplicates}
    if ok:
        ordered = sorted(records, key=lambda r: hashlib.sha256(
            ("nofft-deployment-split-v1:" + r["input_fp32_sha256"]).encode()).hexdigest())
        a, b = args.calibration, args.calibration + args.development
        payload["splits"] = {"calibration": [r["file"] for r in ordered[:a]],
                             "development": [r["file"] for r in ordered[a:b]],
                             "reserved_holdout": [r["file"] for r in ordered[b:]]}
    encoded = (json.dumps(payload, indent=2) + "\n").encode()
    (out / "manifest.json").write_bytes(encoded)
    summary = {"date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
               "source": str(args.source.resolve()),
               "provenance": {"basis": "user_confirmation" if args.independent_confirmed else "unknown",
                              "user_statement": "完全独立，未用于训练或选模" if args.independent_confirmed else None,
                              "independently_verified": False},
               "files": len(files), "valid_files": len(records), "invalid_files": len(problems),
               "duplicate_fp32_inputs": len(duplicates), "input_dtypes": dict(input_types),
               "label_dtypes": dict(label_types), "input_shape": [5, 112, 112],
               "label_shape": [7, 30], "channel_min": minima.tolist(), "channel_max": maxima.tolist(),
               "label_min": label_min, "label_max": label_max, "samples_outside_0_1": outside,
               "split_status": "frozen" if ok else "blocked_by_audit",
               "split_sizes": {k: len(v) for k, v in payload.get("splits", {}).items()},
               "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
               "normalization": "none; cast to float32 only; raw preprocessing semantics still required"}
    (ROOT / "reports/dataset_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit("Audit failed; inspect build/dataset/manifest.json; no splits generated")


if __name__ == "__main__":
    main()
