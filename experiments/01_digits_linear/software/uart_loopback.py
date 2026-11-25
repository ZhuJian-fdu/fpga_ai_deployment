"""Verify raw 115200 8N1 FPGA echoes. Listing ports never opens them."""
import argparse
import json
from pathlib import Path
import random
import time

import serial
from serial.tools import list_ports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="Board CH340 serial port, e.g. COM5")
    parser.add_argument("--list", action="store_true", help="Only list available ports")
    args = parser.parse_args()
    if args.list or not args.port:
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        for port in ports:
            print(f"{port.device}: {port.description} [{port.hwid}]")
        if not ports:
            print("No serial ports found. Check the board UART USB connection and driver.")
        if not args.list:
            print("Select the board port explicitly: --port COM5 (replace COM5).")
        return
    rng = random.Random(42)
    cases = [b"FPGA UART echo\r\n", bytes(range(256)),
             bytes(rng.randrange(256) for _ in range(1024))]
    total = 0
    try:
        with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=2,
                           bytesize=8, parity='N', stopbits=1,
                           xonxoff=False, rtscts=False, dsrdtr=False) as port:
            time.sleep(0.2)
            port.reset_input_buffer()
            for case in cases:
                # Bounded bursts; stop-and-wait avoids unlimited FIFO drift accumulation.
                for offset in range(0, len(case), 64):
                    block = case[offset:offset+64]
                    if port.write(block) != len(block):
                        raise RuntimeError("Incomplete serial write")
                    reply = bytearray()
                    deadline = time.monotonic()+2
                    while len(reply)<len(block) and time.monotonic()<deadline:
                        reply.extend(port.read(len(block)-len(reply)))
                    if reply != block:
                        raise RuntimeError(f"Mismatch at byte {total}: sent={block.hex()} received={reply.hex()}")
                    total += len(block)
                print(f"PASS: {len(case)} bytes matched")
            time.sleep(0.05)
            if port.read(1):
                raise RuntimeError("Unexpected extra bytes received")
    except (serial.SerialException, RuntimeError) as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    result = {"port": args.port, "baud":115200, "format":"8N1", "bytes_checked":total,
              "result":"PASS", "scope":"UART echo only; confirm LED2 is off"}
    out = Path(__file__).resolve().parents[1]/"build"/"uart_loopback_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"PASS: all {total} bytes match. Confirm LED2 stays OFF. Report: {out}")


if __name__ == '__main__':
    main()
