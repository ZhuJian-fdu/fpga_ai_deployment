"""Extract the three reviewed model files, verifying against the source audit."""
from pathlib import Path
import argparse
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads((ROOT / "reports/source_update_20261125.json").read_text(encoding="utf-8"))
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != audit["source_files"]["no-fft.tar.gz"]["sha256"]:
        raise ValueError("Archive changed; review source before executing new model code")
    out = ROOT / "build/model_source"
    out.mkdir(parents=True, exist_ok=True)
    members = {"no-fft/psf_zernike_model_fcas_vit.py": "psf_zernike_model_fcas_vit.py",
               "no-fft/vit_model.py": "vit_model.py",
               "no-fft/result/fcas_cbam_vit-ca-5psf-7x6-nofft-small/model_best.pth": "model_best.pth"}
    with tarfile.open(args.archive) as archive:
        for member, name in members.items():
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != audit["archive_members"][member]["sha256"]:
                raise ValueError(f"Source hash mismatch: {member}")
            (out / name).write_bytes(data)
    print(f"PASS: reviewed model code and weights prepared in {out}")


if __name__ == "__main__":
    main()
