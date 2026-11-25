"""Extract the reviewed 35T MIG config and example traffic generator locally."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    archive = ROOT / "board/vendor/ch37_acx720_ddr_test.rar"
    prefix = "ch37_acx720_ddr_test/mig_7series_0_ex/"
    config_member = prefix + "mig_7series_0_ex.srcs/sources_1/ip/mig_7series_0/mig_b.prj"
    names = ["example_top.v", "mig_7series_v4_2_axi4_tg.v",
             "mig_7series_v4_2_axi4_wrapper.v", "mig_7series_v4_2_cmd_prbs_gen_axi.v",
             "mig_7series_v4_2_data_gen_chk.v", "mig_7series_v4_2_tg.v"]
    out = ROOT / "build/ddr_sources"
    out.mkdir(parents=True, exist_ok=True)
    records = {}

    def read(member):
        data = subprocess.check_output(["tar", "-xOf", str(archive), member])
        records[member] = hashlib.sha256(data).hexdigest()
        return data

    config = read(config_member)
    tree = ET.fromstring(config)
    if tree.findtext("TargetFPGA") != "xc7a35t-fgg484/-2":
        raise ValueError("Not the reviewed XC7A35T MIG config")
    for key, value in {"SystemClock": "No Buffer", "ReferenceClock": "Use System Clock",
                       "SysResetPolarity": "ACTIVE LOW"}.items():
        if tree.findtext(key) != value:
            raise ValueError(f"Unexpected MIG {key}")
    controller = tree.find("Controller")
    expected = {"MemoryDevice": "DDR3_SDRAM/Components/MT41J128M16XX-125",
                "TimePeriod": "2500", "InputClkFreq": "200", "DataWidth": "16",
                "MemoryVoltage": "1.5V", "PortInterface": "AXI", "PHYRatio": "4:1",
                "RowAddress": "14", "ColAddress": "10", "BankAddress": "3"}
    for key, value in expected.items():
        if controller.findtext(key) != value:
            raise ValueError(f"Unexpected MIG {key}")
    for key, value in {"C0_S_AXI_ADDR_WIDTH": "28", "C0_S_AXI_DATA_WIDTH": "128",
                       "C0_S_AXI_ID_WIDTH": "4", "C0_S_AXI_SUPPORTS_NARROW_BURST": "0"}.items():
        if controller.findtext("AXIParameters/" + key) != value:
            raise ValueError(f"Unexpected MIG {key}")
    pins = {p.attrib["name"]: p.attrib["PADName"] for p in controller.findall("PinSelection/Pin")}
    # Independent V3 pin source already obtained for experiment 01.
    ref_dir = ROOT.parent / "01_digits_linear/board/vendor"
    refs = list(ref_dir.rglob("ddr3_pin_.ucf"))
    if len(refs) != 1:
        raise ValueError("Provide the V3 DDR pin UCF in experiment 01 board/vendor")
    ucf = refs[0].read_text()
    reference = dict(re.findall(r'NET\s+"([^"]+)"\s+LOC\s*=\s*"([^"]+)"', ucf))
    if len(pins) != 48 or pins != reference:
        raise ValueError("MIG DDR pin assignment differs from the verified V3 pin source")
    (out / "mig_35t.prj").write_bytes(config)
    for name in names:
        data = read(prefix + "imports/" + name)
        if name == "example_top.v":
            text = data.decode("utf-8-sig")
            anchor = "   output                                       tg_compare_error,"
            if text.count(anchor) != 1 or text.count("endmodule") != 1:
                raise ValueError("Unexpected vendor example; review before adapting")
            text = text.replace(anchor, "   output monitor_read_activity,\n"
                                "   output reg monitor_error_sticky,\n" + anchor)
            monitor = """
  // Local observation only; do not change the vendor AXI traffic generator.
  reg [22:0] read_beat_counter;
  assign monitor_read_activity = read_beat_counter[22];
  always @(posedge clk) begin
    if (rst) begin
      read_beat_counter <= 0;
      monitor_error_sticky <= 0;
    end else begin
      if (s_axi_rvalid && s_axi_rready)
        read_beat_counter <= read_beat_counter + 1'b1;
      if (tg_compare_error) monitor_error_sticky <= 1;
    end
  end
"""
            data = text.replace("endmodule", monitor + "\nendmodule").encode("utf-8")
        (out / name).write_bytes(data)
    report = {"date": "2026-11-25", "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "source_member_sha256": records, "v3_pin_reference_sha256": hashlib.sha256(refs[0].read_bytes()).hexdigest(),
              "all_48_ddr_pins_match": True, "part": "xc7a35tfgg484-2",
              "mig_settings": expected, "pins": pins,
              "test_address_window": "0x00000000..0x00ffffff (16 MiB), vendor traffic generator",
              "physical_validation": "pending"}
    report["provided_archives"] = {
        p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted((ROOT / "board/vendor").glob("*.rar"))
    }
    (ROOT / "reports/ddr_source_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: 35T config, all 48 V3 DDR pins; example sources prepared in {out}")


if __name__ == "__main__":
    main()
