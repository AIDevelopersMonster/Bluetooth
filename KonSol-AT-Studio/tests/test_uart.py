from pathlib import Path
import queue
import tempfile
import time
import unittest

from konat.profiles import parse_profile
from konat.serial_io import AtTransport
from konat.ui import SerialWorker
from konat.inspection_registry import db_status, query_inspections, get_inspection

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
        w = SerialWorker(commands, events, root, db_path=root / "test-inspections.sqlite3")
        profile = parse_profile(ROOT / "modules" / "bt18_dual")
        w.port, w.connected_profile = fake, profile.key
        w.start()
        return w, commands, events, profile

    def test_write_reads_before_and_after(self):
        fake = FakeSerial([
            b"+ADSS=02a1b2c3d4e5\r\nOK\r\n",
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
            self.assertEqual(db_status(Path(temp) / "test-inspections.sqlite3")["inspections"], 1)
            saved = query_inspections(db_path=Path(temp) / "test-inspections.sqlite3")[0]
            self.assertEqual(saved["test_code"], "AT_WRITE_READBACK_V1")
            self.assertEqual(saved["result"], "PASS")
        self.assertEqual(fake.writes, [b"AT+ADSS?\r\n", b"AT+NAME?\r\n", b"AT+NAME=KON-BT18\r\n", b"AT+NAME?\r\n"])
        self.assertTrue(any(e == "change" and d["status"] == "verified" for e,d in seen))

    def test_jdy31_name_write_without_equals_and_plus_ok(self):
        fake = FakeSerial([
            b"+VERSION=JDY-31A-V2.241,Bluetooth V3.0+BLE\r\n",
            b"+LADDR=02A1B2C3D4E5\r\n",
            b"+NAME=JDY-31\r\n",
            b"+OK\r\n",
            b"+NAME=KON-BT31\r\n",
        ])
        with tempfile.TemporaryDirectory() as temp:
            commands, events = queue.Queue(), queue.Queue()
            worker = SerialWorker(commands, events, Path(temp),
                                  db_path=Path(temp) / "inspections.sqlite3")
            profile = parse_profile(ROOT / "modules" / "jdy31")
            worker.port, worker.connected_profile = fake, profile.key
            worker.start()
            commands.put(("write", profile, {"qid": "name", "value": "KON-BT31"}))
            seen = []
            while True:
                kind, data = events.get(timeout=5)
                seen.append((kind, data))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            worker.join(timeout=2)
        self.assertEqual(fake.writes, [
            b"AT+VERSION\r\n", b"AT+LADDR\r\n", b"AT+NAME\r\n",
            b"AT+NAMEKON-BT31\r\n", b"AT+NAME\r\n",
        ])
        self.assertTrue(any(kind == "change" and data.get("status") == "verified"
                            for kind, data in seen))
        self.assertFalse(any(kind == "error" for kind, data in seen))

    def test_jdy31_write_blocked_on_wrong_firmware(self):
        fake = FakeSerial([b"+VERSION=JDY-31-V1.0,Bluetooth V3.0\r\n"])
        with tempfile.TemporaryDirectory() as temp:
            commands, events = queue.Queue(), queue.Queue()
            worker = SerialWorker(commands, events, Path(temp),
                                  db_path=Path(temp) / "inspections.sqlite3")
            profile = parse_profile(ROOT / "modules" / "jdy31")
            worker.port, worker.connected_profile = fake, profile.key
            worker.start()
            commands.put(("write", profile, {"qid": "name", "value": "TEST31"}))
            seen = []
            while True:
                kind, data = events.get(timeout=3)
                seen.append((kind, data))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            worker.join(timeout=2)
        self.assertEqual(fake.writes, [b"AT+VERSION\r\n"])
        self.assertTrue(any(kind == "error" for kind, data in seen))

    def test_failed_preread_blocks_write(self):
        fake = FakeSerial([b"+ADSS=02a1b2c3d4e5\r\nOK\r\n", b"ERR\r\n"])
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
        self.assertEqual(fake.writes, [b"AT+ADSS?\r\n", b"AT+NAME?\r\n"])
        self.assertTrue(any(e == "error" for e,d in seen))

    def test_inspect_read_all_creates_fresh_scoped_record(self):
        fake = FakeSerial([
            b"OK\r\n", b"+VERS=V3.01\r\nOK\r\n",
            b"+ADSS=02a1b2c3d4e5\r\nOK\r\n", b"+NAME=BT18-T\r\nOK\r\n",
            b"+BAUD=1\r\nOK\r\n", b"+PIN=9876\r\nOK\r\n",
            b"+UUID=ffe0,ffe1,ffe2\r\nOK\r\n", b"+FLOW=0\r\nOK\r\n",
        ])
        with tempfile.TemporaryDirectory() as temp:
            w, commands, events, profile = self._worker(fake, Path(temp))
            commands.put(("inspect", profile, {}))
            seen = []
            while True:
                kind, info = events.get(timeout=3)
                seen.append((kind, info))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            w.join(timeout=2)
            saved = query_inspections(db_path=Path(temp) / "test-inspections.sqlite3")
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["result"], "PASS")
            self.assertEqual(saved[0]["reported_mac"], "02A1B2C3D4E5")
            details = get_inspection(saved[0]["id"], Path(temp) / "test-inspections.sqlite3")
            self.assertEqual(details["payload"]["passed"], 8)
            self.assertNotIn("9876", str(details["payload"]))
        self.assertEqual(len(fake.writes), 8)
        self.assertTrue(any(kind == "inspection" for kind, data in seen))

    def test_inspect_without_mac_refuses_to_attribute_record(self):
        fake = FakeSerial([b"OK\r\n", b"+VERS=V3.01\r\nOK\r\n"] + [b"" for _ in range(6)])
        with tempfile.TemporaryDirectory() as temp:
            w, commands, events, profile = self._worker(fake, Path(temp))
            commands.put(("inspect", profile, {}))
            seen = []
            while True:
                kind, info = events.get(timeout=7)
                seen.append((kind, info))
                if kind == "done":
                    break
            commands.put(("stop", None, {}))
            w.join(timeout=2)
            self.assertFalse((Path(temp) / "test-inspections.sqlite3").exists())
        self.assertTrue(any(kind == "error" for kind, data in seen))

    def test_jdy_snapshot_saved_in_sqlite_with_redacted_pin(self):
        fake = FakeSerial([
            b"+VERSION=JDY-31A-V2.241,Bluetooth V3.0+BLE\r\n",
            b"+LADDR=02A1B2C3D4E5\r\n",
            b"+NAME=JDY-33-SPP\r\n",
            b"+BAUD=4\r\n",
            b"+PIN=1234\r\n",
        ])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inbox, outbox = queue.Queue(), queue.Queue()
            db = root / "db.sqlite3"
            worker = SerialWorker(inbox, outbox, root, db_path=db)
            profile = parse_profile(ROOT / "modules" / "jdy31")
            worker.port, worker.connected_profile = fake, profile.key
            worker.start()
            inbox.put(("snapshot", profile, {}))
            seen = []
            while True:
                kind, data = outbox.get(timeout=6)
                seen.append((kind, data))
                if kind == "done":
                    break
            inbox.put(("stop", None, {}))
            worker.join(timeout=2)
            saved = [d for k, d in seen if k == "snapshot"][0]
            content = Path(saved["path"]).read_text(encoding="utf-8")
            record = query_inspections(db_path=db)
            self.assertEqual(len(record), 1)
            self.assertEqual(record[0]["test_code"], "AT_CONFIG_SNAPSHOT_V1")
            self.assertEqual(record[0]["result"], "PASS")
            self.assertEqual(saved["record"]["id"], record[0]["id"])
            self.assertNotIn("1234", content)
            self.assertNotIn("1234", str(get_inspection(record[0]["id"], db)))
            self.assertEqual(fake.writes[-1], b"AT+PIN\r\n")

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
