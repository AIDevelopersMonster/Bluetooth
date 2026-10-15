"""Load declarative, data-only AT module profiles from modules/*/profile.json.

No imports or executable hooks from profile folders are ever performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

_ID = re.compile(r"[a-z][a-z0-9_-]{1,49}\Z")
_AT_READ = re.compile(r"AT(?:\+[A-Z0-9_?.=/-]+)?\Z")
_AT_WRITE = re.compile(r"AT\+[A-Z0-9_]+(?:=)?\{value\}\Z")
_AT_RESET = re.compile(r"AT(?:\+[A-Z0-9_]+)?\Z")


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    folder: Path
    baud: int
    ending: bytes
    timeout: float
    notes: str
    verified_reads: bool
    queries: tuple[dict, ...]
    factory_reset: dict | None

    @property
    def setters(self) -> tuple[dict, ...]:
        return tuple(q for q in self.queries if "edit" in q)

    def by_id(self, key: str) -> dict:
        for item in self.queries:
            if item["id"] == key:
                return item
        raise KeyError(key)


def _string(obj: dict, key: str, limit: int = 256) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ProfileError(f"Expected non-empty string: {key}")
    return value


def parse_profile(folder: Path) -> Profile:
    path = folder / "profile.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ProfileError(f"{path}: schema_version must be 1")
    key = _string(document, "id", 50)
    if not _ID.fullmatch(key) or key != folder.name:
        raise ProfileError(f"{path}: id must match folder name and use lowercase slug")
    title = _string(document, "title", 75)
    baud = document.get("baud", 9600)
    if type(baud) is not int or baud not in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400):
        raise ProfileError(f"{path}: unsupported default baud")
    eol = document.get("ending", "CRLF")
    if eol not in ("CRLF", "CR", "LF"):
        raise ProfileError(f"{path}: invalid ending")
    ending = {"CRLF": b"\r\n", "CR": b"\r", "LF": b"\n"}[eol]
    timeout_ms = document.get("timeout_ms", 650)
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 5000:
        raise ProfileError(f"{path}: timeout_ms must be 100..5000")
    queries = document.get("queries")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 64:
        raise ProfileError(f"{path}: expected 1..64 queries")
    known = set()
    checked = []
    for query in queries:
        if not isinstance(query, dict):
            raise ProfileError(f"{path}: query must be an object")
        qid = _string(query, "id", 50)
        if not _ID.fullmatch(qid) or qid in known:
            raise ProfileError(f"{path}: duplicate/invalid query id {qid!r}")
        known.add(qid)
        _string(query, "label", 80)
        command = _string(query, "command", 100)
        if not command.isascii() or not _AT_READ.fullmatch(command):
            raise ProfileError(f"{path}: invalid read command {command!r}")
        prefix = query.get("prefix", "")
        if not isinstance(prefix, str) or len(prefix) > 100 or "\n" in prefix or "\r" in prefix:
            raise ProfileError(f"{path}: invalid response prefix")
        edit = query.get("edit")
        if edit is not None:
            if not isinstance(edit, dict):
                raise ProfileError(f"{path}: invalid edit block for {qid}")
            template = _string(edit, "template", 100)
            if not template.isascii() or not _AT_WRITE.fullmatch(template):
                raise ProfileError(f"{path}: invalid write template {template!r}")
            if not prefix:
                raise ProfileError(f"{path}: edited query needs prefix for readback")
            pattern = _string(edit, "pattern", 100)
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ProfileError(f"{path}: invalid pattern: {exc}") from exc
            choices = edit.get("choices")
            if choices is not None and (not isinstance(choices, dict) or not choices or any(not isinstance(k, str) or not isinstance(v, str) for k, v in choices.items())):
                raise ProfileError(f"{path}: invalid choices")
            risk = edit.get("risk", "medium")
            if risk not in ("low", "medium", "high"):
                raise ProfileError(f"{path}: invalid risk")
            if type(edit.get("power_cycle", False)) is not bool:
                raise ProfileError(f"{path}: power_cycle must be bool")
        checked.append(query)
    reset = document.get("factory_reset")
    if reset is not None:
        if not isinstance(reset, dict):
            raise ProfileError(f"{path}: factory_reset must be object or null")
        command = _string(reset, "command", 100)
        if not command.isascii() or not _AT_RESET.fullmatch(command):
            raise ProfileError(f"{path}: invalid reset command")
        if not reset.get("source_url") or (reset.get("verified_on_hardware") is not True and not (key == "jdy31" and reset.get("experimental") is True and command == "AT+DEFAULT" and reset.get("require_version_prefix") == "JDY-31A-V2.241,")):
            raise ProfileError(f"{path}: factory reset requires explicit hardware verification and documented source_url")
    return Profile(
        key=key, title=title, folder=folder, baud=baud, ending=ending,
        timeout=timeout_ms / 1000.0, notes=document.get("notes", ""),
        verified_reads=document.get("verified_reads") is True,
        queries=tuple(checked), factory_reset=reset,
    )


def discover_profiles(root: Path) -> tuple[list[Profile], list[str]]:
    profiles: list[Profile] = []
    errors: list[str] = []
    if not root.is_dir():
        return [], [f"Missing modules directory: {root}"]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder / "profile.json").exists():
            continue
        try:
            profiles.append(parse_profile(folder))
        except ProfileError as exc:
            errors.append(str(exc))
    if not profiles:
        errors.append("No valid module folders were found")
    return profiles, errors


def validate_setting(query: dict, value: str) -> str:
    if "edit" not in query:
        raise ValueError("This parameter is read-only")
    if any(char in value for char in ("\n", "\r", "\x00")) or not value.isascii():
        raise ValueError("Only single-line ASCII values are accepted")
    edit = query["edit"]
    if not re.fullmatch(edit["pattern"], value, flags=re.ASCII):
        raise ValueError("Value does not match profile restrictions")
    if edit.get("choices") is not None and value not in edit["choices"]:
        raise ValueError("Value is not a permitted choice")
    # Output must be pure AT ASCII, never a delimiter-injection opportunity.
    command = edit["template"].replace("{value}", value)
    if not command.isascii() or "\n" in command or "\r" in command:
        raise ValueError("Invalid AT command")
    return command


def response_value(response: bytes, prefix: str) -> str | None:
    text = response.decode("utf-8", errors="replace")
    for line in text.replace("\r", "\n").split("\n"):
        clean = line.strip()
        if clean.startswith(prefix) and prefix:
            return clean[len(prefix):].strip()
    return None


def status_of(response: bytes) -> str:
    if not response:
        return "TIMEOUT"
    lines = [line.strip().upper() for line in response.decode("ascii", errors="replace").replace("\r", "\n").split("\n")]
    if "ERR" in lines or "ERROR" in lines:
        return "ERROR"
    if "OK" in lines:
        return "OK"
    return "RESPONSE"
