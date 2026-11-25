"""Restore the board-tested model without retraining; regenerate simulation inputs."""
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from sklearn.datasets import load_digits

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "baseline"
    out = ROOT / "build" / "model"
    manifest = json.loads((ROOT / "reports/ai_build_manifest.json").read_text(encoding="utf-8"))
    names = ["model.npz", "weights.mem", "biases.mem"]
    for name in names:
        actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if actual != manifest["sha256"][f"build/model/{name}"]:
            raise SystemExit(f"Baseline checksum mismatch: {name}")

    with np.load(source / "model.npz", allow_pickle=False) as model:
        weights = model["weights"].astype(np.int64)
        biases = model["biases"].astype(np.int64)
        ids = model["test_ids"]
    dataset = load_digits()
    pixels = dataset.data[ids].astype(np.int64)
    scores = pixels @ weights.T + biases
    archived = json.loads((ROOT / "reports/board_inference_450.json").read_text(encoding="utf-8"))
    if (not np.array_equal(scores, [r["scores"] for r in archived["records"]])
            or not np.array_equal(ids, [r["dataset_index"] for r in archived["records"]])
            or not np.array_equal(dataset.target[ids], [r["label"] for r in archived["records"]])):
        raise SystemExit("Installed dataset/model does not reproduce the archived board results")

    edge_cases = np.stack([
        np.zeros(64, dtype=np.int64), np.full(64, 16, dtype=np.int64),
        (np.arange(64) % 2) * 16, np.eye(8, dtype=np.int64).ravel() * 16,
    ])
    vectors = np.concatenate([pixels, edge_cases])
    golden = vectors @ weights.T + biases
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(source / name, out / name)
    # Match the original Windows export bytes, including CRLF, on every OS.
    for name, values, bits in [
        ("images.mem", vectors, 8), ("scores.mem", golden, 32),
        ("predictions.mem", np.argmax(golden, axis=1), 8),
    ]:
        mask = (1 << bits) - 1
        content = "".join(f"{int(v) & mask:0{bits // 4}x}\r\n" for v in np.ravel(values))
        (out / name).write_bytes(content.encode("ascii"))
    (out / "sim_config.vh").write_bytes(f"`define NUM_CASES {len(vectors)}\r\n".encode("ascii"))
    shutil.copyfile(ROOT / "reports/baseline_metrics.json", out / "metrics.json")
    print("PASS: baseline checksums and all 450 archived image scores match")
    print(f"Restored model and {len(vectors)} simulation vectors to {out}")


if __name__ == "__main__":
    main()
