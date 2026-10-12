"""Serial AT transactions: same 9600/8N1/CRLF protocol as bt18_probe.py."""
from __future__ import annotations

import time


class AtError(IOError):
    pass


class AtTransport:
    def __init__(self, serial_port):
        self.serial_port = serial_port

    def exchange(self, command: str, ending: bytes, timeout: float) -> bytes:
        if not command.isascii() or "\n" in command or "\r" in command:
            raise ValueError("Unsafe AT command")
        port = self.serial_port
        port.reset_input_buffer()
        payload = command.encode("ascii") + ending
        written = port.write(payload)
        if written != len(payload):
            raise AtError("Short UART write")
        port.flush()
        end = time.monotonic() + timeout
        last_rx = None
        result = bytearray()
        while time.monotonic() < end:
            chunk = port.read(min(max(port.in_waiting, 1), 512))
            if chunk:
                result.extend(chunk)
                last_rx = time.monotonic()
                if len(result) > 8192:
                    raise AtError("Reply too large (>8192 bytes)")
                upper = result.upper().replace(b"\r", b"\n")
                if b"\nOK\n" in upper or b"\nERR\n" in upper or b"\nERROR\n" in upper:
                    break
                if upper.strip() in (b"OK", b"ERR", b"ERROR") and last_rx:
                    # Wait briefly in case more of the reply follows.
                    pass
            elif last_rx is not None and time.monotonic() - last_rx >= 0.12:
                break
        return bytes(result)
