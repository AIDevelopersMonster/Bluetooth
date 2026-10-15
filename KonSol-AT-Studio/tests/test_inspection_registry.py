import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from konat.inspection_registry import (
    add_inspection, normalize_mac, get_inspection, query_inspections,
    db_status, registry_summary, export_json, export_csv, generate_report,
    backup_database,
)
from konat.inspection_capture import examine_queries
from konat.profiles import discover_profiles


class InspectionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "inspection.sqlite3"
        self.args = dict(
            mac="02:A1:B2:C3:D4:E5", profile="bt18_dual", test_code="AT_READ_ALL_V1",
            result="PASS", tested_on="2026-10-12", evidence_source="historical_screenshot",
            tested_at_utc=None, payload={"checks": [{"qid": "pin", "value": "9876",
                                                      "response_hex": "2B50494E3D31323334"}],
                                         "other": "fine"}, db_path=self.db,
        )

    def test_no_file_until_first_insert(self):
        self.assertFalse(db_status(self.db)["exists"])

    def test_new_module_and_append_only_history(self):
        a = add_inspection(**self.args)
        b = add_inspection(**{**self.args, "mac": "02a1b2c3d4e5", "test_code": "AT_WRITE_READBACK_V1"})
        self.assertEqual(a["module_code"], b["module_code"])
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(db_status(self.db)["modules"], 1)
        self.assertEqual(db_status(self.db)["inspections"], 2)
        self.assertEqual(query_inspections(mac="02-A1-B2-C3-D4-E5", db_path=self.db)[0]["id"], b["id"])
        self.assertEqual(registry_summary(self.db)["results"], {"PASS": 2})
        row = get_inspection(a["id"], self.db)
        self.assertIsNone(row["tested_at_utc"])
        self.assertEqual(row["payload"]["checks"][0]["value"], "[REDACTED]")
        self.assertEqual(row["payload"]["checks"][0]["response_hex"], "[REDACTED]")
        self.assertEqual(row["acceptance_status"], "NOT_EVALUATED")

    def test_distinct_addresses_get_distinct_codes(self):
        a = add_inspection(**self.args)
        b = add_inspection(**{**self.args, "mac": "AB:CD:EF:01:23:45"})
        self.assertEqual(a["module_code"], "BT-2026-00001")
        self.assertEqual(b["module_code"], "BT-2026-00002")
        self.assertEqual(db_status(self.db)["modules"], 2)

    def test_reject_invalid_identity_timestamp_status(self):
        for bad in ("27EE", "000000000000", "FFFFFFFFFFFF", "not a mac", "27:EE:0:AA", "02a1b2c3d4e5x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_mac(bad)
        with self.assertRaises(ValueError):
            add_inspection(**{**self.args, "tested_on": "2026-02-30"})
        with self.assertRaises(ValueError):
            add_inspection(**{**self.args, "tested_at_utc": "2026-10-12T19:00:00"})
        with self.assertRaises(ValueError):
            add_inspection(**{**self.args, "result": "APPROVED"})
        self.assertFalse(self.db.exists())

    def test_uid_duplicate_is_rejected_not_silently_updated(self):
        k = "fixed-screenshot-record-uid"
        add_inspection(**{**self.args, "inspection_uid": k})
        with self.assertRaises(ValueError):
            add_inspection(**{**self.args, "inspection_uid": k})
        self.assertEqual(db_status(self.db)["inspections"], 1)

    def test_export_formats_and_backup(self):
        add_inspection(**self.args)
        tmp = Path(self.temp.name)
        j = export_json(tmp / "out.json", self.db)
        payload = json.loads(j.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "kon-incoming-inspection/v1")
        self.assertEqual(payload["records"][0]["identity_source"], "AT+ADSS?")
        self.assertEqual(payload["records"][0]["incoming_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("9876", j.read_text(encoding="utf-8"))
        self.assertIn("reported_mac", export_csv(tmp / "out.csv", self.db).read_text(encoding="utf-8-sig"))
        self.assertIn("incoming inspection", generate_report(tmp / "out.html", self.db).read_text(encoding="utf-8"))
        backup = backup_database(tmp / "copy.sqlite3", self.db)
        self.assertEqual(db_status(backup)["inspections"], 1)


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.profiles, cls.errors = discover_profiles(root / "modules")
        cls.profile = next(x for x in cls.profiles if x.key == "bt18_dual")

    def test_all_eight(self):
        replies = {
            "test": b"OK\r\n", "version": b"+VERS=V3.01\r\nOK\r\n",
            "address": b"+ADSS=02a1b2c3d4e5\r\nOK\r\n",
            "name": b"+NAME=BT18-T\r\nOK\r\n",
            "baud": b"+BAUD=1\r\nOK\r\n",
            "pin": b"+PIN=9876\r\nOK\r\n",
            "uuid": b"+UUID=ffe0,ffe1,ffe2\r\nOK\r\n",
            "flow": b"+FLOW=0\r\nOK\r\n",
        }
        outcome = examine_queries(self.profile, replies)
        self.assertEqual((outcome["passed"], outcome["total"]), (8, 8))
        self.assertEqual(outcome["result"], "PASS")
        self.assertEqual(outcome["mac"], "02A1B2C3D4E5")
        self.assertEqual(outcome["firmware"], "V3.01")
        self.assertEqual(outcome["checks"][5]["response_hex"], "[REDACTED]")
        self.assertEqual(outcome["checks"][5]["value"], "[REDACTED]")

    def test_jdy31_without_trailing_ok(self):
        profile = next(x for x in self.profiles if x.key == "jdy31")
        replies = {
            "version": b"+VERSION=JDY-31-V1.2,Bluetooth V3.0\r\n",
            "address": b"+LADDR=02A1B2C3D4E5\r\n",
            "name": b"+NAME=JDY-31-SPP\r\n",
            "baud": b"+BAUD=4\r\n",
            "pin": b"+PIN=1234\r\n",
        }
        result = examine_queries(profile, replies)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual((result["passed"], result["total"]), (4, 4))
        self.assertEqual(result["mac"], "02A1B2C3D4E5")
        self.assertNotIn("1234", str(result["checks"]))

    def test_jdy31a_real_name_unknown_and_probes_excluded(self):
        profile = next(x for x in self.profiles if x.key == "jdy31")
        replies = {
            "version": b"+VERSION=JDY-31A-V2.241,Bluetooth V3.0+BLE\r\n",
            "address": b"+LADDR=02A1B2C3D4E5\r\n",
            "name": b"+NAME=?\r\n",
            "baud": b"+BAUD=4\r\n",
            "pin": b"+PIN=1234\r\n",
        }
        result = examine_queries(profile, replies)
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["passed"], 4)
        self.assertEqual(result["result"], "PASS")
        self.assertFalse(any(c["qid"] == "name" for c in result["checks"]))
        self.assertEqual(result["firmware"], "JDY-31A-V2.241,Bluetooth V3.0+BLE")
        self.assertEqual(len([q for q in profile.queries if q.get("probe_only")]), 12)
        self.assertNotIn("1234", str(result["checks"]))

    def test_timeout_is_incomplete(self):
        outcome = examine_queries(self.profile, {"address": b"+ADSS=02a1b2c3d4e5\r\nOK\r\n"})
        self.assertEqual(outcome["result"], "INCOMPLETE")
        self.assertEqual(outcome["passed"], 1)

    def test_address_never_guessed(self):
        outcome = examine_queries(self.profile, {"address": b"+ADSS=Bad\r\nOK\r\n"})
        self.assertIsNone(outcome["mac"])
        self.assertEqual(outcome["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
