#!/usr/bin/env python3
"""KonSol-SPPM serial echo server for a Bluetooth Classic SPP UART module.

Path: Android KonSol-SPPM -> Bluetooth SPP -> BT18-T UART -> PC COM port
      -> exact byte-for-byte echo via PC UART -> BT18-T -> Android RX.

This program does not send AT commands, change the module configuration,
use the PC Bluetooth adapter, or add a prefix, newline, or terminator.
No firmware or wiring changes are required for an existing working UART link.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


def printable(data: bytes) -> str:
    """Readable diagnostic text. Never used for the actual echo payload."""
    s = data.decode("utf-8", errors="backslashreplace")
    return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def available_ports():
    return sorted(list_ports.comports(), key=lambda p: p.device.upper())


def choose_port(requested: str | None) -> str:
    if requested:
        return requested
    ports = available_ports()
    if not ports:
        raise RuntimeError("No COM ports found. Use --port COM4 if the port is known.")
    print("Available COM ports:")
    for index, port in enumerate(ports, 1):
        print(f"  {index}. {port.device}  {port.description}")
    if len(ports) == 1:
        print(f"Selected automatically: {ports[0].device}")
        return ports[0].device
    while True:
        response = input(f"Choose a COM port [1-{len(ports)}] (or Q): ").strip()
        if response.lower() in ("q", "quit"):
            raise KeyboardInterrupt
        try:
            number = int(response)
        except ValueError:
            number = -1
        if 1 <= number <= len(ports):
            return ports[number - 1].device
        print("Invalid selection.")


def echo_bytes(uart, data: bytes) -> int:
    """Write all exact input bytes; handle partial writes without mutation."""
    sent = 0
    while sent < len(data):
        n = uart.write(data[sent:])
        if n is None or n <= 0:
            raise OSError("COM write returned no progress")
        sent += n
    uart.flush()
    return sent


def log_frame(direction: str, index: int, payload: bytes) -> None:
    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{stamp}] {direction} #{index:04d} [{len(payload)} B] "
          f"TEXT={printable(payload)!r} HEX={payload.hex(' ').upper()}", flush=True)


def run_echo(uart, seconds: float = 0, quiet: bool = False) -> tuple[int, int]:
    """Receive on the COM port and immediately echo each received byte chunk."""
    count = 0
    total = 0
    started = time.monotonic()
    while seconds == 0 or time.monotonic() - started < seconds:
        length = min(max(uart.in_waiting, 1), 4096)
        data = uart.read(length)
        if not data:
            continue
        count += 1
        if not quiet:
            log_frame("RX  ", count, data)
        echoed = echo_bytes(uart, data)
        total += echoed
        if not quiet:
            log_frame("ECHO", count, data)
    return count, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Echo all bytes received from a Bluetooth SPP module on a selected COM port."
    )
    parser.add_argument("--port", help="COM port, e.g. COM4 (omit for menu)")
    parser.add_argument("--baud", type=int, default=9600, help="UART baud rate (default: 9600)")
    parser.add_argument("--list-ports", action="store_true", help="Show COM ports and exit")
    parser.add_argument("--seconds", type=float, default=0,
                        help="Stop after N seconds; 0 means Ctrl+C (default: 0)")
    parser.add_argument("--quiet", action="store_true", help="Hide per-chunk RX/ECHO diagnostics")
    args = parser.parse_args(argv)

    if args.baud <= 0 or args.seconds < 0:
        parser.error("--baud must be positive and --seconds must not be negative")
    if serial is None:
        print("Missing pyserial. Install: py -m pip install pyserial", file=sys.stderr)
        return 2

    if args.list_ports:
        for p in available_ports():
            print(f"{p.device}: {p.description}")
        return 0

    try:
        port = choose_port(args.port)
        print(f"KonSol-SPPM SPP ECHO | {port} | {args.baud} 8N1")
        print("Exact byte echo: no prefix, no CR/LF insertion, no AT commands.")
        print("Send a TEXT or HEX command from the Android terminal; watch its RX log.")
        print("Stop: Ctrl+C" if args.seconds == 0 else f"Stop: after {args.seconds:g} seconds or Ctrl+C")
        with serial.Serial(
            port=port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.10,
            write_timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        ) as uart:
            frames, bytes_echoed = run_echo(uart, seconds=args.seconds, quiet=args.quiet)
        print(f"Finished. RX chunks: {frames}; echoed bytes: {bytes_echoed}")
        return 0
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 0
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f"COM ERROR: {exc}", file=sys.stderr)
        print("Make sure the COM port is not open in another serial program.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
