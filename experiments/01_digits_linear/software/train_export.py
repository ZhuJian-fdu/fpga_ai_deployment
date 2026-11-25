"""Train on the PC, export integer inference data, and record held-out results."""
import hashlib
import json
from pathlib import Path

import numpy as np
import sklearn
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "model"


def write_hex(name, values, bits):
    mask = (1 << bits) - 1
    text = "".join(f"{int(v) & mask:0{bits // 4}x}\n" for v in np.ravel(values))
    (OUT / name).write_text(text, encoding="ascii")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dataset = load_digits()
    pixels = dataset.data.astype(np.int64)
    train_ids, test_ids = train_test_split(
        np.arange(len(pixels)), test_size=0.25, random_state=42,
        stratify=dataset.target,
    )
    model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000, tol=1e-8)
    model.fit(pixels[train_ids] / 16.0, dataset.target[train_ids])
    if model.n_iter_.max() >= model.max_iter:
        raise RuntimeError("Training did not converge; inspect before exporting.")
    assert np.array_equal(model.classes_, np.arange(10))

    # Training used x/16. Fold that division into W so RTL consumes raw 0..16 pixels.
    effective_w = model.coef_ / 16.0
    scale = float(np.max(np.abs(effective_w)) / 127.0)
    weights = np.clip(np.rint(effective_w / scale), -127, 127).astype(np.int64)
    biases = np.rint(model.intercept_ / scale).astype(np.int64)
    bound = int(np.max(np.abs(biases) + 16 * np.sum(np.abs(weights), axis=1)))
    if bound >= 2**31:
        raise RuntimeError("Integer scores can overflow signed int32.")

    x_test = pixels[test_ids]
    labels = dataset.target[test_ids]
    scores = x_test @ weights.T + biases
    prediction = np.argmax(scores, axis=1)  # first/smallest class wins ties
    float_prediction = model.predict(x_test / 16.0)

    # These synthetic cases check arithmetic, not recognition accuracy.
    edge_cases = np.stack([
        np.zeros(64, dtype=np.int64), np.full(64, 16, dtype=np.int64),
        (np.arange(64) % 2) * 16, np.eye(8, dtype=np.int64).ravel() * 16,
    ])
    vectors = np.concatenate([x_test, edge_cases])
    golden_scores = vectors @ weights.T + biases
    golden_prediction = np.argmax(golden_scores, axis=1)
    write_hex("weights.mem", weights, 8)  # class-major, 10 rows x 64 features
    write_hex("biases.mem", biases, 32)
    write_hex("images.mem", vectors, 8)
    write_hex("scores.mem", golden_scores, 32)
    write_hex("predictions.mem", golden_prediction, 8)
    (OUT / "sim_config.vh").write_text(
        f"`define NUM_CASES {len(vectors)}\n", encoding="ascii"
    )
    np.savez(OUT / "model.npz", weights=weights.astype(np.int8),
             biases=biases.astype(np.int32), scale=scale,
             train_ids=train_ids, test_ids=test_ids,
             float_weights=model.coef_, float_biases=model.intercept_)
    metrics = {
        "dataset": "sklearn load_digits (8x8), not MNIST",
        "numpy_version": np.__version__, "sklearn_version": sklearn.__version__,
        "split_seed": 42, "train_samples": len(train_ids), "test_samples": len(test_ids),
        "float_accuracy": float(np.mean(float_prediction == labels)),
        "integer_accuracy": float(np.mean(prediction == labels)),
        "float_integer_agreement": float(np.mean(prediction == float_prediction)),
        "weight_scale": scale, "score_abs_bound": bound,
        "weight_bytes": 640, "bias_bytes": 40,
        "rtl_test_vectors": len(vectors),
        "weights_sha256": hashlib.sha256((OUT / "weights.mem").read_bytes()).hexdigest(),
        "biases_sha256": hashlib.sha256((OUT / "biases.mem").read_bytes()).hexdigest(),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Exported model and simulation vectors to: {OUT}")
    sample = x_test[0].reshape(8, 8)
    palette = " .:-=+*#%@"
    print("First held-out image:")
    for row in sample:
        print("".join(palette[int(v) * 9 // 16] * 2 for v in row))
    print(f"Label={labels[0]}, integer prediction={prediction[0]}")


if __name__ == "__main__":
    main()
