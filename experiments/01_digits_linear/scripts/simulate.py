"""Run Icarus with explicit paths and cwd; no shell activation is required."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["heartbeat", "classifier", "board", "uart", "protocol", "ai_uart", "ai_reset"])
    args = parser.parse_args()
    for tool in ["iverilog", "vvp"]:
        if shutil.which(tool) is None:
            raise SystemExit(f"Missing {tool}; add Icarus Verilog bin to PATH.")
    out = ROOT / "build" / "sim"
    out.mkdir(parents=True, exist_ok=True)
    if args.target in ["classifier", "protocol", "ai_uart", "ai_reset"]:
        work = ROOT / "build" / "model"
        required = ["weights.mem", "biases.mem", "images.mem", "scores.mem",
                    "predictions.mem", "sim_config.vh"]
        if any(not (work / name).is_file() for name in required):
            raise SystemExit("Run software/train_export.py first.")
        if args.target in ["protocol", "ai_uart"]:
            subprocess.run([sys.executable, str(ROOT/'scripts'/'prepare_protocol_vectors.py')], check=True)
        module = {"classifier":"digit_classifier", "protocol":"digit_protocol", "ai_uart":"digit_uart", "ai_reset":"ai_reset"}[args.target]
        top = f"tb_{module}"
        rtl = ROOT / "rtl" / f"{module}.sv"
        if args.target == "ai_reset":
            rtl = ROOT / "board" / "acx720_v3_ai_top.v"
    elif args.target == "uart":
        work = out
        top = "tb_uart_echo"
        rtl = ROOT / "rtl" / "uart_echo.v"
    elif args.target == "board":
        work = out
        top = "tb_acx720_v3_heartbeat"
        rtl = ROOT / "board" / "acx720_v3_heartbeat_top.v"
    else:
        work = out
        top = "tb_heartbeat"
        rtl = ROOT / "rtl" / "heartbeat.v"
    binary = out / f"{top}.vvp"
    sources = [str(rtl), str(ROOT / "sim" / f"{top}.sv")]
    if args.target == "board":
        sources.append(str(ROOT / "rtl" / "heartbeat.v"))
    if args.target == "uart":
        sources.extend(str(ROOT / "rtl" / f"uart_{name}.v") for name in ["rx", "tx"])
    if args.target in ["protocol", "ai_uart", "ai_reset"]:
        sources.append(str(ROOT / "rtl" / "digit_classifier.sv"))
    if args.target in ["ai_uart", "ai_reset"]:
        sources.extend(str(ROOT / "rtl" / name) for name in ["digit_protocol.sv","uart_rx.v","uart_tx.v"])
    if args.target == "ai_reset":
        sources.extend(str(ROOT / "rtl" / name) for name in ["heartbeat.v","digit_uart.sv"])
    subprocess.run(["iverilog", "-g2012", "-Wall", "-s", top, "-I", str(work),
                    "-o", str(binary), *sources],
                   cwd=work, check=True)
    subprocess.run(["vvp", str(binary)], cwd=work, check=True)


if __name__ == "__main__":
    main()
