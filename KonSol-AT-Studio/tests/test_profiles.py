from pathlib import Path
import json
import tempfile
import unittest

from konat.profiles import (
    ProfileError, discover_profiles, parse_profile,
    response_value, status_of, validate_setting,
)

BASE = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.dual = parse_profile(BASE / "modules" / "bt18_dual")

    def test_discovery_requires_folder_and_json(self):
        found, errors = discover_profiles(BASE / "modules")
        self.assertFalse(errors)
        self.assertEqual([x.key for x in found], ["bt18_dual", "bt18_le", "jdy31"])
        self.assertEqual(len(self.dual.queries), 8)
        self.assertEqual(len(self.dual.setters), 4)

    def test_jdy31_profile_is_read_only(self):
        p = parse_profile(BASE / "modules" / "jdy31")
        self.assertEqual([q["command"] for q in p.queries],
                         ["AT+VERSION", "AT+LADDR", "AT+NAME", "AT+BAUD", "AT+PIN"])
        self.assertEqual(p.baud, 9600)
        self.assertEqual(p.ending, b"\\r\\n")
        self.assertFalse(p.verified_reads)
        self.assertFalse(p.setters)
        self.assertIsNone(p.factory_reset)

    def test_queries_match_physical_at_read_set(self):
        self.assertEqual([x["command"] for x in self.dual.queries], [
            "AT+TEST", "AT+VERS?", "AT+ADSS?", "AT+NAME?",
            "AT+BAUD?", "AT+PIN?", "AT+UUID?", "AT+FLOW?",
        ])

    def test_valid_write_only(self):
        field = self.dual.by_id("name")
        self.assertEqual(validate_setting(field, "KON_BT18"), "AT+NAME=KON_BT18")
        for bad in ("", "X" * 20, "HELLO\r\nAT+BAUD=5", "TEST\x00", "Test\u042f"):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                validate_setting(field, bad)
        self.assertEqual(validate_setting(self.dual.by_id("baud"), "3"), "AT+BAUD=3")
        with self.assertRaises(ValueError):
            validate_setting(self.dual.by_id("baud"), "6")
        with self.assertRaises(ValueError):
            validate_setting(self.dual.by_id("version"), "TEST")

    def test_response_extraction_and_status(self):
        frame = b"\r\n+NAME=BT18-T\r\nOK\r\n"
        self.assertEqual(response_value(frame, "+NAME="), "BT18-T")
        self.assertEqual(status_of(frame), "OK")
        self.assertEqual(status_of(b"ERR\r\n"), "ERROR")
        self.assertEqual(status_of(b""), "TIMEOUT")

    def test_factory_reset_is_blocked_for_both_real_profiles(self):
        for p in discover_profiles(BASE / "modules")[0]:
            self.assertIsNone(p.factory_reset)

    def test_new_module_folder_autoloaded(self):
        with tempfile.TemporaryDirectory() as d:
            module = Path(d) / "example_1"
            module.mkdir()
            data = {
                "schema_version": 1, "id": "example_1", "title": "Example module",
                "queries": [{"id":"test", "label":"Ping", "command":"AT"}],
                "factory_reset": None,
            }
            (module / "profile.json").write_text(json.dumps(data), encoding="utf-8")
            profiles, errors = discover_profiles(Path(d))
            self.assertEqual(len(profiles), 1)
            self.assertFalse(errors)
            self.assertEqual(profiles[0].title, "Example module")

    def test_reset_needs_documentation_and_hardware_verification(self):
        with tempfile.TemporaryDirectory() as d:
            module = Path(d) / "example_2"
            module.mkdir()
            data = {
                "schema_version": 1, "id": "example_2", "title": "Fake",
                "queries": [{"id":"test", "label":"Ping", "command":"AT"}],
                "factory_reset": {"command":"AT+DEFAULT", "source_url":"https://example.com"},
            }
            (module / "profile.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ProfileError):
                parse_profile(module)
            data["factory_reset"]["verified_on_hardware"] = True
            (module / "profile.json").write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(parse_profile(module).factory_reset["command"], "AT+DEFAULT")

    def test_reject_commands_with_control_characters(self):
        with tempfile.TemporaryDirectory() as d:
            module = Path(d) / "example_3"
            module.mkdir()
            data = {"schema_version":1, "id":"example_3", "title":"Fake",
                    "queries":[{"id":"test","label":"Test","command":"AT+NAME?\nAT+BAUD=5"}]}
            (module / "profile.json").write_text(json.dumps(data), encoding="utf-8")
            self.assertRaises(ProfileError, parse_profile, module)


if __name__ == "__main__":
    unittest.main()
