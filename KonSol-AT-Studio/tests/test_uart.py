from pathlib import Path
import queue
import tempfile
import time
import unittest

from konat.profiles import parse_profile
from konat.serial_io import AtTransport
from konat.ui import SerialWorker

ROOT = Path(__file__).resolve().parents[1]


class FakeSerial:
    def __init__(self, replies):
        self.replies = list(replies)
        self.input = bytearray()
        self.writes = []
        self.is_open = True
        self.port = "COM4"
        self.baudrate = 9600

    @property
    def in_waiting(self):
        return len(self.input)

    def reset_input_buffer(self):
        self.input.clear()

    def write(self, data):
        self.writes.append(bytes(data))
        if self.replies:
            self.input.extend(self.replies.pop(0))
        return len(data)

    def flush(self):
        pass

    def read(self, size):
        data = bytes(self.input[:size])
        del self.input[:size]
        if not data:
            time.sleep(.005)
        return data

    def close(self):
        self.is_open = False


class UartTests(unittest.TestCase):
    def test_uart_read_byte_exact(self):
        raw = b"\r\n+NAME=BT18-T\r\nOK\r\n"
        fake = FakeSerial([raw])
        reply = AtTransport(fake).exchange("AT+NAME?", b"\r\n", .20)
        self.assertEqual(reply, raw)
        self.assertEqual(fake.writes, [b"AT+NAME?\r\n"])

    def test_reject_newline_injected_at_command(self):
        fake = FakeSerial([])
        with self.assertRaises(ValueError):
            AtTransport(fake).exchange("AT+NAME?\r\nAT+BAUD=5", b"\r\n", .1)
        self.assertEqual(fake.writes, [])

    def _worker(self, fake, root):
        commands, events = queue.Queue(), queue.Queue()
        w = SerialWorker(commands, events, root)
        profile = parse_profile(ROOT / "modules" / "bt18_dual")
        w.port, w.connected_profile = fake, profile.key
        w.start()
        return w, commands, events, profile

    def test_write_reads_before_and_after(self):
        fake = FakeSerial([
            b"+NAME=BT18-T\r\nOK\r\n",
            b"+NAME=KON-BT18\r\nOK\r\n",
            b"+NAME=KON-BT18\r\nOK\r\n",
        ])
        with tempfile.TemporaryDirectory() as temp:
            w, commands, events, profile = self._worker(fake, Path(temp))
            commands.put(("write", profile, {"qid":"name","value":"KON-BT18"}))
            seen = []
            while True:
                kind, info = events.get(timeout=3)
                seen.append((kind, info))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            w.join(timeout=2)
        self.assertEqual(fake.writes, [b"AT+NAME?\r\n", b"AT+NAME=KON-BT18\r\n", b"AT+NAME?\r\n"])
        self.assertTrue(any(e == "change" and d["status"] == "verified" for e,d in seen))

    def test_failed_preread_blocks_write(self):
        fake = FakeSerial([b"ERR\r\n"])
        with tempfile.TemporaryDirectory() as temp:
            w, commands, events, profile = self._worker(fake, Path(temp))
            commands.put(("write", profile, {"qid":"name","value":"KON-BT18"}))
            seen = []
            while True:
                kind, info = events.get(timeout=3)
                seen.append((kind, info))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            w.join(timeout=2)
        self.assertEqual(fake.writes, [b"AT+NAME?\r\n"])
        self.assertTrue(any(e == "error" for e,d in seen))

    def test_no_factory_command_on_real_profile(self):
        fake = FakeSerial([])
        with tempfile.TemporaryDirectory() as temp:
            w, commands, events, profile = self._worker(fake, Path(temp))
            commands.put(("factory", profile, {}))
            errors = []
            while True:
                kind, info = events.get(timeout=3)
                if kind == "error":
                    errors.append(info["message"])
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            w.join(timeout=2)
        self.assertEqual(fake.writes, [])
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
