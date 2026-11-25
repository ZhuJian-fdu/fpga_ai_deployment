"""Run behavioral AXI master regressions with Icarus; no board required."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CASES = ["normal_with_stalls", "corrupt_read_data", "address_alias",
         "write_error_response", "read_error_response", "early_rlast",
         "aw_timeout", "unexpected_bid", "reset_during_write",
         "highest_address_boundary", "b_timeout", "missing_rlast",
         "aw_timeout_then_recovery", "r_timeout_then_recovery",
         "slave_waits_for_wvalid", "write_data_before_address"]


def main():
    out = ROOT / "build/sim"
    out.mkdir(parents=True, exist_ok=True)
    log = ["Icarus behavioral AXI tests; not a MIG/DDR PHY simulation.\n"]
    for case, name in enumerate(CASES):
        exe = out / f"ddr_full_{case}.vvp"
        subprocess.run(["iverilog", "-g2012", "-s", "tb_ddr_full_sweep",
                        f"-Ptb_ddr_full_sweep.CASE={case}", "-o", str(exe),
                        "rtl/ddr_full_sweep.v", "sim/tb_ddr_full_sweep.sv"],
                       cwd=ROOT, check=True)
        result = subprocess.run(["vvp", str(exe)], cwd=ROOT, check=True,
                                capture_output=True, text=True)
        if f"PASS CASE={case} " not in result.stdout:
            raise RuntimeError(f"Missing completion: {name}")
        print(name + ": " + result.stdout.splitlines()[0])
        log.append(f"\n{name}\n{result.stdout}{result.stderr}")
    (ROOT / "reports/ddr_full_simulation.txt").write_text("".join(log), encoding="utf-8")


if __name__ == "__main__":
    main()
