#!/usr/bin/env python3
"""Software-only checks for byte-exact UART echo. No hardware needed."""
import unittest
import konsol_spp_echo as echo


class FakePort:
    def __init__(self, maximum=None):
        self.maximum = maximum
        self.out = bytearray()
        self.flush_count = 0

    def write(self, data):
        size = len(data) if self.maximum is None else min(len(data), self.maximum)
        self.out.extend(data[:size])
        return size

    def flush(self):
        self.flush_count += 1


class EchoTests(unittest.TestCase):
    def test_ping_crlf(self):
        port = FakePort(maximum=2)
        packet = b"PING\r\n"
        self.assertEqual(echo.echo_bytes(port, packet), len(packet))
        self.assertEqual(bytes(port.out), packet)
        self.assertEqual(port.flush_count, 1)

    def test_binary_all_octets(self):
        packet = bytes(range(256))
        port = FakePort()
        self.assertEqual(echo.echo_bytes(port, packet), 256)
        self.assertEqual(bytes(port.out), packet)

    def test_utf8(self):
        packet = "Привет!".encode("utf-8")
        port = FakePort(maximum=1)
        echo.echo_bytes(port, packet)
        self.assertEqual(bytes(port.out), packet)

    def test_zero_progress(self):
        class Stalled(FakePort):
            def write(self, data):
                return 0
        with self.assertRaises(OSError):
            echo.echo_bytes(Stalled(), b"X")


if __name__ == "__main__":
    unittest.main()
