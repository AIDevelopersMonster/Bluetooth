#!/usr/bin/env python3
"""BT18-T transparent BLE-UART software echo using the existing USB-UART COM port.

Phone writes FFE2 -> BT18 UART TX -> PC COM RX -> PC COM TX -> BT18 UART RX
-> phone FFE1 notifications. The script does not use the PC Bluetooth adapter,
change the module configuration, or send AT commands.
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Missing pyserial. Install using the repository requirements.txt", file=sys.stderr)
    raise SystemExit(2)


def show(payload: bytes) -> str:
    return payload.decode("utf-8", errors="backslashreplace").replace("\r", "\\r").replace("\n", "\\n")


def echo_frame(port: serial.Serial, frame: bytes, prefix: bytes, number: int) -> None:
    reply = prefix + frame
    print(f"RX #{number}: {len(frame)} bytes, text={show(frame)!r}, hex={frame.hex(' ')}", flush=True)
    port.write(reply)
    port.flush()
    print(f"TX #{number}: {len(reply)} bytes, text={show(reply)!r}, hex={reply.hex(' ')}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM4", help="CH340 serial port (default: COM4)")
    parser.add_argument("--baud", type=int, default=9600, help="UART baud (default: 9600)")
    parser.add_argument("--prefix", default="PC:", help="reply prefix in ASCII (default: PC:)")
    parser.add_argument("--gap-ms", type=int, default=120,
                        help="inactivity gap separating messages, 20..1000 ms (default: 120)")
    parser.add_argument("--seconds", type=float, default=0,
                        help="automatic stop in seconds; 0 means Ctrl+C (default: 0)")
    parser.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    args = parser.parse_args()

    if args.list_ports:
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        for item in ports:
            print(f"{item.device}: {item.description}")
        if not ports:
            print("No serial ports detected.")
        return 0
    if args.baud <= 0 or not 20 <= args.gap_ms <= 1000 or args.seconds < 0:
        parser.error("expected baud > 0, gap-ms 20..1000 and seconds >= 0")
    try:
        prefix = args.prefix.encode("ascii")
    except UnicodeEncodeError:
        parser.error("--prefix must contain ASCII characters")

    print(f"BT18-T Software Echo | {args.port} {args.baud} 8N1", flush=True)
    print("Phone: enable FFE1 NOTIFY and WRITE 'hello4' to FFE2.", flush=True)
    print("Expected phone reply: 'PC:hello4'. Ctrl+C to exit.", flush=True)
    print("No AT commands, wiring changes, or PC BLE connection.", flush=True)

    count = 0
    pending = bytearray()
    last_data = time.monotonic()
    started = time.monotonic()
    try:
        with serial.Serial(args.port, args.baud, timeout=0.03, write_timeout=1) as uart:
            # Only data arriving after opening this port is considered test traffic.
            uart.reset_input_buffer()
            while args.seconds == 0 or time.monotonic() - started < args.seconds:
                part = uart.read(min(max(uart.in_waiting, 1), 512))
                now = time.monotonic()
                if part:
                    pending.extend(part)
                    last_data = now
                if pending and (len(pending) >= 512 or
                                now - last_data >= args.gap_ms / 1000):
                    count += 1
                    echo_frame(uart, bytes(pending), prefix, count)
                    pending.clear()
            if pending:
                count += 1
                echo_frame(uart, bytes(pending), prefix, count)
    except KeyboardInterrupt:
        print("\nStopped by user.", flush=True)
    except (serial.SerialException, OSError) as exc:
        print(f"COM ERROR: {exc}", file=sys.stderr)
        print("Close other serial monitors and verify the existing port; do not rewire.", file=sys.stderr)
        return 2

    print(f"Done. Echoed frames: {count}. Physical BLE-UART PASS requires seeing the return on the phone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
