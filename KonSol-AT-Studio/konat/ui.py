"""KonSol AT Studio: native, dependency-light Tkinter AT module manager."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .profiles import discover_profiles, response_value, status_of, validate_setting
from .serial_io import AtTransport
from .inspection_capture import examine_queries, timestamp_utc
from .inspection_registry import (DEFAULT_DB, add_inspection, normalize_mac,
                                  query_inspections, get_inspection, db_status,
                                  export_json, export_csv, generate_report,
                                  backup_database)

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


class SerialWorker(threading.Thread):
    """Single owner of the COM handle: serial operations never overlap."""

    def __init__(self, inbox: queue.Queue, outbox: queue.Queue, root: Path, db_path: Path = DEFAULT_DB):
        super().__init__(name="KonSol-AT-UART", daemon=True)
        self.inbox, self.outbox, self.root = inbox, outbox, root
        self.db_path = db_path
        self.port = None
        self.connected_profile = None
        self.running = True

    def emit(self, event, **kw):
        self.outbox.put((event, kw))

    def _exchange(self, command, profile):
        self.emit("log", message=f"TX {'[PIN WRITE REDACTED]' if profile.key == 'jdy31' and command.startswith('AT+PIN') and command != 'AT+PIN' else command}")
        reply = AtTransport(self.port).exchange(command, profile.ending, profile.timeout)
        shown = reply.decode("utf-8", errors="backslashreplace").replace("\r", "\\r").replace("\n", "\\n")
        self.emit("log", message=f"RX {'[PIN RESPONSE REDACTED]' if profile.key == 'jdy31' and command.startswith('AT+PIN') else (shown if reply else '[TIMEOUT]')}")
        return reply

    def _query(self, profile, query):
        reply = self._exchange(query["command"], profile)
        self.emit("query", profile=profile.key, qid=query["id"], reply=reply)
        return reply

    def _snapshot(self, profile, required_all=True):
        responses = []
        for query in profile.queries:
            if query.get("probe_only"):
                continue
            reply = self._query(profile, query)
            responses.append({
                "id": query["id"], "command": query["command"],
                "value": response_value(reply, query.get("prefix", "")),
                "response_text": reply.decode("utf-8", errors="replace"),
                "response_hex": reply.hex(),
            })
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        base = self.root / "snapshots"
        base.mkdir(parents=True, exist_ok=True)
        output = base / f"{profile.key}_{stamp}.json"
        data = {
            "tool": "KonSol AT Studio 0.2.0", "module_profile": profile.key,
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "port": self.port.port, "baud": self.port.baudrate,
            "warning": "Local-only data: may include Bluetooth address and pairing PIN",
            "results": responses,
        }
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.emit("snapshot", path=str(output))
        complete = all(x["response_hex"] for x in responses)
        if required_all and not complete:
            self.emit("log", message="WARNING: snapshot has missing replies; review before changing anything")
        return output, complete

    def _identity(self, profile):
        """Obtain module-reported MAC from the current live UART session."""
        query = profile.by_id("address")
        reply = self._query(profile, query)
        if status_of(reply) not in ("OK", "RESPONSE"):
            raise RuntimeError("Cannot read the module address; no untraceable WRITE is allowed")
        value = response_value(reply, query.get("prefix", ""))
        try:
            return normalize_mac(value), query["command"]
        except ValueError as exc:
            raise RuntimeError("AT address response is not a full six-byte identifier") from exc

    def _inspection(self, profile):
        start = timestamp_utc()
        replies = {}
        for query in profile.queries:
            if query.get("probe_only"):
                continue
            replies[query["id"]] = self._query(profile, query)
        outcome = examine_queries(profile, replies)
        if outcome["mac"] is None:
            raise RuntimeError("Inspection was NOT saved: no complete module-reported MAC. "
                               "Review the AT address reply and retry.")
        record = add_inspection(
            mac=outcome["mac"], identity_source=profile.by_id("address")["command"],
            profile=profile.key, test_code="AT_READ_ALL_V1", result=outcome["result"],
            tested_on=start[:10], tested_at_utc=start, evidence_source="live_uart",
            evidence_ref="KonSol AT Studio: Inspect & record",
            board=profile.title, sw_version=outcome["firmware"],
            port=self.port.port, baud=self.port.baudrate,
            db_path=self.db_path,
            payload={"passed": outcome["passed"], "total": outcome["total"],
                     "checks": outcome["checks"],
                     "scope": "UART AT queries only; not total incoming acceptance"},
        )
        self.emit("inspection", record=record, test_code="AT_READ_ALL_V1",
                  passed=outcome["passed"], total=outcome["total"])

    def _write_record(self, profile, query, mac, address_command, old, new, actual, ack, status):
        started = timestamp_utc()
        recorded = add_inspection(
            mac=mac, identity_source=address_command, profile=profile.key,
            test_code="AT_WRITE_READBACK_V1", result="PASS" if status == "verified" else "FAIL",
            tested_on=started[:10], tested_at_utc=started,
            evidence_source="live_uart", evidence_ref="KonSol AT Studio: confirmed Apply and readback",
            board=profile.title, port=self.port.port, baud=self.port.baudrate,
            db_path=self.db_path, payload={"qid": query["id"], "command": query["edit"]["template"],
                     "old": old, "new": new, "actual": actual, "ack": status_of(ack),
                     "verified": status == "verified",
                     "scope": "Single AT setting only; persistence after power-cycle not established"},
        )
        self.emit("inspection", record=recorded, test_code="AT_WRITE_READBACK_V1")

    def run(self):
        try:
            while self.running:
                action, profile, kw = self.inbox.get()
                try:
                    if action == "stop":
                        self.running = False
                        continue
                    if action == "disconnect":
                        self._close()
                        self.emit("disconnected")
                    elif action == "connect":
                        self._close()
                        if serial is None:
                            raise RuntimeError("pyserial is missing: py -m pip install pyserial")
                        self.port = serial.Serial(
                            port=kw["port"], baudrate=kw["baud"],
                            bytesize=8, parity="N", stopbits=1,
                            timeout=0.04, write_timeout=1.0,
                            rtscts=False, xonxoff=False, dsrdtr=False,
                        )
                        self.connected_profile = profile.key
                        time.sleep(0.12)
                        self.emit("connected", port=self.port.port, baud=self.port.baudrate,
                                  profile=profile.key)
                    else:
                        if self.port is None or not self.port.is_open:
                            raise RuntimeError("Open a COM port first")
                        if self.connected_profile != profile.key:
                            raise RuntimeError("This COM session belongs to another module tab. Disconnect and reconnect to switch profiles")
                        if action == "query":
                            self._query(profile, profile.by_id(kw["qid"]))
                        elif action == "read_all":
                            for query in profile.queries:
                                if not query.get("probe_only"):
                                    self._query(profile, query)
                        elif action == "snapshot":
                            self._snapshot(profile)
                        elif action == "inspect":
                            self._inspection(profile)
                        elif action == "write":
                            query = profile.by_id(kw["qid"])
                            if not query.get("edit", {}).get("enabled", True):
                                raise RuntimeError("This setter is disabled in the module profile")
                            value = kw["value"]
                            command = validate_setting(query, value)
                            if profile.key == "jdy31":
                                version_reply = self._query(profile, profile.by_id("version"))
                                version_value = response_value(version_reply, profile.by_id("version").get("prefix", ""))
                                expected = query["edit"].get("require_version_prefix")
                                if not expected or not version_value or not version_value.startswith(expected):
                                    raise RuntimeError("JDY-31A firmware mismatch; WRITE NOT SENT")
                            mac, address_command = self._identity(profile)
                            # Never write without an initial response for this exact field.
                            previous = self._query(profile, query)
                            old = response_value(previous, query.get("prefix", ""))
                            if old is None or status_of(previous) == "ERROR":
                                raise RuntimeError("Pre-write readback failed. Configuration was NOT changed")
                            self.emit("log", message=f"PRE-WRITE {query['label']}: {'[REDACTED]' if query['id'] == 'pin' else old}")
                            if old == value:
                                self.emit("change", profile=profile.key, qid=query["id"],
                                          status="unchanged", old=old, new=value)
                                continue
                            ack = self._exchange(command, profile)
                            ack_text = ack.decode("ascii", errors="replace").replace("\\r", "\\n").strip().upper()
                            ack_ok = status_of(ack) == "OK" or (profile.key == "jdy31" and "+OK" in ack_text.split())
                            if not ack_ok:
                                raise RuntimeError("Write was not acknowledged with OK. State is UNKNOWN; read again before retrying")
                            if query["edit"].get("power_cycle") and profile.key == "jdy31":
                                self.emit("change", profile=profile.key, qid=query["id"],
                                          status="pending_power_cycle", old=old, new=value,
                                          power_cycle=True)
                                continue
                            actual_reply = self._query(profile, query)
                            actual = response_value(actual_reply, query.get("prefix", ""))
                            success = actual == value
                            self._write_record(profile, query, mac, address_command,
                                               old, value, actual, ack,
                                               "verified" if success else "unverified")
                            self.emit("change", profile=profile.key, qid=query["id"],
                                      status="verified" if success else "unverified",
                                      old=old, new=value, actual=actual,
                                      power_cycle=query["edit"].get("power_cycle", False))
                        elif action == "restart":
                            reboot = profile.folder / "profile.json"
                            config = json.loads(reboot.read_text(encoding="utf-8")).get("soft_reset")
                            if not config or profile.key != "jdy31":
                                raise RuntimeError("No supported software-restart command")
                            vr = self._query(profile, profile.by_id("version"))
                            vv = response_value(vr, "+VERSION=")
                            if not vv or not vv.startswith(config["require_version_prefix"]):
                                raise RuntimeError("Firmware mismatch: restart not sent")
                            ack = self._exchange(config["command"], profile)
                            self.emit("restart", status=("+OK" if b"+OK" in ack.upper() else status_of(ack)))
                        elif action == "factory":
                            reset = profile.factory_reset
                            if reset is None or not (reset.get("verified_on_hardware") or (profile.key == "jdy31" and reset.get("experimental"))):
                                raise RuntimeError("Factory reset command is not verified for this module")
                            if reset.get("experimental"):
                                vr = self._query(profile, profile.by_id("version"))
                                vv = response_value(vr, "+VERSION=")
                                if not vv or not vv.startswith(reset.get("require_version_prefix", "UNKNOWN")):
                                    raise RuntimeError("Firmware mismatch: factory command not sent")
                            _, snapshot_complete = self._snapshot(profile)
                            if not snapshot_complete:
                                raise RuntimeError("Pre-reset snapshot incomplete; factory reset NOT SENT")
                            ack = self._exchange(reset["command"], profile)
                            self.emit("factory", status=("+OK" if b"+OK" in ack.upper() else status_of(ack)))
                        else:
                            raise RuntimeError(f"Unknown worker action: {action}")
                except Exception as exc:
                    self.emit("error", message=f"{action}: {exc}")
                    if action == "connect":
                        self._close()
                        self.emit("disconnected")
                finally:
                    self.emit("done")
        finally:
            self._close()

    def _close(self):
        current = self.port
        self.port = None
        self.connected_profile = None
        if current is not None:
            try:
                current.close()
            except Exception:
                pass


class ModuleTab:
    def __init__(self, app, profile, frame):
        self.app, self.profile, self.frame = app, profile, frame
        self.values = {}
        self._build()

    def _build(self):
        f = self.frame
        f.columnconfigure(0, weight=2)
        f.columnconfigure(1, weight=3)
        f.rowconfigure(1, weight=1)
        notes = ttk.Label(f, text=self.profile.notes, wraplength=1090, justify="left")
        notes.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 7))
        left = ttk.LabelFrame(f, text="AT Queries (read-only; probes manual)", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=4)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=("command", "value", "state"), show="tree headings",
                                 selectmode="browse", height=12)
        self.tree.heading("#0", text="Parameter")
        self.tree.heading("command", text="AT command")
        self.tree.heading("value", text="Value")
        self.tree.heading("state", text="Result")
        self.tree.column("#0", width=148, minwidth=100)
        self.tree.column("command", width=110, minwidth=85)
        self.tree.column("value", width=123, minwidth=75)
        self.tree.column("state", width=66, minwidth=50)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        for query in self.profile.queries:
            self.tree.insert("", "end", iid=query["id"], text=query["label"],
                             values=(query["command"], "-", "-"))
        controls = ttk.Frame(left)
        controls.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Read selected", command=self.read_selected).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="Read core", command=lambda:self.app.action("read_all", self.profile)).pack(side="left", padx=5)
        ttk.Button(controls, text="Save snapshot JSON", command=lambda:self.app.action("snapshot", self.profile)).pack(side="left", padx=5)
        ttk.Button(controls, text="Inspect & record", command=lambda:self.app.action("inspect", self.profile)).pack(side="left", padx=5)

        right = ttk.Frame(f)
        right.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=4)
        right.columnconfigure(0, weight=1)
        settings = ttk.LabelFrame(right, text="Configuration writes (disabled globally until enabled)", padding=10)
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        if not self.profile.setters:
            ttk.Label(settings, text="This profile has no editable fields.").grid(row=0, column=0)
        for i, query in enumerate(self.profile.setters):
            edit = query["edit"]
            ttk.Label(settings, text=query["label"]).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=7)
            variable = tk.StringVar(value="")
            self.values[query["id"]] = variable
            if "choices" in edit:
                choice_labels = [f"{k} = {v}" for k, v in edit["choices"].items()]
                c = ttk.Combobox(settings, values=choice_labels, width=14, state="readonly")
                c.bind("<<ComboboxSelected>>", lambda e, qid=query["id"], cb=c: self.values[qid].set(cb.get().split(" = ", 1)[0]))
                c.grid(row=i, column=1, sticky="ew", padx=(0, 5))
                # Preserve the actual combobox to synchronize on a query result.
                self.values[query["id"] + "_combobox"] = c
            else:
                ttk.Entry(settings, textvariable=variable, width=18).grid(row=i, column=1, sticky="ew", padx=(0, 5))
            ttk.Button(settings, text="Read", width=6,
                       command=lambda qid=query["id"]: self.app.action("query", self.profile, qid=qid)).grid(row=i, column=2, padx=3)
            button = ttk.Button(settings, text="Apply", width=7,
                                command=lambda qid=query["id"]: self.write_setting(qid))
            button.grid(row=i, column=3, padx=(3, 0))
            if not edit.get("enabled", True):
                button.state(["disabled"])
        info = ttk.Label(right, text="Changes are never sent automatically. Each change is confirmed,\npre-read, acknowledged and read back; UART baud changes need a power cycle.",
                         wraplength=610, justify="left")
        info.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        reset = ttk.LabelFrame(right, text="Factory defaults", padding=10)
        reset.grid(row=2, column=0, sticky="ew")
        if self.profile.factory_reset is None:
            self.factory_button = ttk.Button(reset, text="Factory RESET: not documented")
            self.factory_button.state(["disabled"])
            ttk.Label(reset, text="No documented factory-reset command for this profile.\nNo guessed AT+DEFAULT / AT+RESET will be transmitted.",
                      justify="left", wraplength=580).pack(anchor="w", pady=(6, 0))
        else:
            self.factory_button = ttk.Button(reset, text="Restore FACTORY defaults...", command=self.app.factory_reset)
            ttk.Label(reset, text="Requires a verified command, double confirmation and a pre-reset snapshot.",
                      wraplength=570).pack(anchor="w", pady=(6, 0))
        self.factory_button.pack(anchor="w")
        if self.profile.key == "jdy31":
            ttk.Button(reset, text="Restart module (AT+RESET)", command=self.app.soft_restart).pack(anchor="w", pady=(8, 0))

    def read_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Selection", "Select a query in the left table first")
            return
        q = self.profile.by_id(selection[0])
        if q.get("probe_only") and not messagebox.askyesno("Unverified JDY-31A query",
                f"{q['command']} is unverified on this firmware. Send this ONE query?"):
            return
        self.app.action("query", self.profile, qid=selection[0])

    def update_query(self, qid, reply):
        query = self.profile.by_id(qid)
        value = response_value(reply, query.get("prefix", ""))
        status = status_of(reply)
        self.tree.set(qid, "value", value if value is not None else ("OK" if status == "OK" else "-"))
        self.tree.set(qid, "state", status)
        if value is not None and qid in self.values:
            self.values[qid].set(value)
            cb = self.values.get(qid + "_combobox")
            if cb is not None:
                choices = query["edit"].get("choices", {})
                cb.set(f"{value} = {choices[value]}" if value in choices else "")

    def write_setting(self, qid):
        query = self.profile.by_id(qid)
        value = self.values[qid].get().strip()
        try:
            command = validate_setting(query, value)
        except ValueError as error:
            messagebox.showerror("Invalid setting", str(error))
            return
        if not self.app.writes_enabled.get():
            messagebox.showwarning("Writes locked", "Enable configuration writes in the top toolbar first")
            return
        danger = query["edit"].get("hint", "Configuration may change the module behavior")
        command_shown = "[PIN WRITE REDACTED]" if qid == "pin" else command
        prompt = (f"Module: {self.profile.title}\n\nAT command: {command_shown}\n\n{danger}\n\n"
                  "A read-before-write and readback check will be performed.\n\nSend this configuration change?")
        if messagebox.askyesno("Confirm module configuration WRITE", prompt, icon="warning"):
            self.app.action("write", self.profile, qid=qid, value=value)


class ATStudio:
    def __init__(self, root_folder: Path):
        self.root_folder = root_folder
        self.root = tk.Tk()
        self.root.title("KonSol AT Studio 0.2.0 | KonSol Tools")
        self.root.geometry("1160x780")
        self.root.minsize(970, 640)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.profile_tabs = {}
        self.connected_profile = None
        self.busy = False
        self.writes_enabled = tk.BooleanVar(value=False)
        self.port_var = tk.StringVar(value="COM4")
        self.baud_var = tk.StringVar(value="9600")
        self.conn_status = tk.StringVar(value="Disconnected")
        self.queue_in = queue.Queue()
        self.queue_out = queue.Queue()
        self.worker = SerialWorker(self.queue_in, self.queue_out, root_folder)
        self.worker.start()
        self._build_shell()
        self.reload_modules()
        self.refresh_ports()
        self.root.after(80, self.poll)

    def _build_shell(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)
        top = ttk.LabelFrame(self.root, text="UART connection", padding=9)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        ttk.Label(top, text="COM:").pack(side="left")
        self.port_cb = ttk.Combobox(top, textvariable=self.port_var, width=13)
        self.port_cb.pack(side="left", padx=5)
        ttk.Button(top, text="Scan", command=self.refresh_ports).pack(side="left", padx=(0, 10))
        ttk.Label(top, text="Baud:").pack(side="left")
        self.baud_cb = ttk.Combobox(top, textvariable=self.baud_var, width=9,
                                    values=["9600", "19200", "38400", "57600", "115200"], state="normal")
        self.baud_cb.pack(side="left", padx=5)
        ttk.Button(top, text="OPEN", command=self.connect).pack(side="left", padx=(10, 4))
        ttk.Button(top, text="CLOSE", command=self.disconnect).pack(side="left", padx=(0, 12))
        ttk.Label(top, textvariable=self.conn_status).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(top, text="Enable AT WRITES", variable=self.writes_enabled).pack(side="right", padx=(5, 0))
        self.tabs_widget = ttk.Notebook(self.root)
        self.tabs_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        footer = ttk.LabelFrame(self.root, text="Session log (local only)", padding=6)
        footer.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 8))
        footer.columnconfigure(0, weight=1)
        self.log = tk.Text(footer, height=9, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroller = ttk.Scrollbar(footer, orient="vertical", command=self.log.yview)
        scroller.grid(row=0, column=1, sticky="ns")
        self.log.config(yscrollcommand=scroller.set)
        buttons = ttk.Frame(footer)
        buttons.grid(row=1, column=0, sticky="e", pady=4)
        ttk.Button(buttons, text="Inspection registry", command=self.open_registry).pack(side="left", padx=5)
        ttk.Button(buttons, text="Reload module folders", command=self.reload_modules).pack(side="left", padx=5)
        ttk.Button(buttons, text="Clear log", command=self.clear_log).pack(side="left", padx=5)

    def refresh_ports(self):
        if list_ports is None:
            self.log_line("pyserial not installed: py -m pip install pyserial")
            return
        available = sorted(p.device for p in list_ports.comports())
        self.port_cb["values"] = available
        if available and self.port_var.get() not in available:
            self.port_var.set(available[0])
        self.log_line(f"COM ports: {', '.join(available) if available else '(none)'}")

    def reload_modules(self):
        if self.busy or self.connected_profile is not None:
            messagebox.showwarning("Module reload", "Close the COM session before reloading module profiles")
            return
        profiles, errors = discover_profiles(self.root_folder / "modules")
        for tabid in self.tabs_widget.tabs():
            self.tabs_widget.forget(tabid)
        self.profile_tabs.clear()
        for profile in profiles:
            frame = ttk.Frame(self.tabs_widget)
            self.tabs_widget.add(frame, text=profile.title)
            self.profile_tabs[profile.key] = ModuleTab(self, profile, frame)
        if profiles:
            self.baud_var.set(str(profiles[0].baud))
        self.log_line(f"Module discovery: {len(profiles)} tabs from modules/*/profile.json")
        for error in errors:
            self.log_line("PROFILE ERROR: " + error)
        if errors:
            messagebox.showwarning("Profile loading", "\n".join(errors[:5]))

    def selected_tab(self) -> ModuleTab | None:
        active = self.tabs_widget.select()
        for item in self.profile_tabs.values():
            if str(item.frame) == str(active):
                return item
        return None

    def connect(self):
        tab = self.selected_tab()
        if not tab:
            return
        try:
            baud = int(self.baud_var.get())
            if baud <= 0 or baud > 4000000:
                raise ValueError
        except ValueError:
            messagebox.showerror("UART speed", "Enter a valid positive baud rate")
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("COM port", "Select a serial COM port")
            return
        self.action("connect", tab.profile, port=port, baud=baud)

    def disconnect(self):
        tab = self.selected_tab()
        if not tab:
            return
        self.action("disconnect", tab.profile)

    def action(self, action, profile, **kwargs):
        if self.busy:
            self.log_line("BUSY: wait for the previous UART operation")
            return
        if action not in ("connect", "disconnect") and self.connected_profile is None:
            messagebox.showwarning("COM not open", "OPEN the COM port before sending AT commands")
            return
        if action not in ("connect", "disconnect") and self.connected_profile != profile.key:
            messagebox.showwarning("Wrong module tab", "Disconnect and reconnect to select a different AT profile")
            return
        if action == "write" and not self.writes_enabled.get():
            messagebox.showwarning("Writes locked", "Enable AT WRITES first")
            return
        self.busy = True
        self.conn_status.set("Working...")
        self.queue_in.put((action, profile, kwargs))

    def soft_restart(self):
        tab = self.selected_tab()
        if tab is None or tab.profile.key != "jdy31":
            return
        if not messagebox.askyesno("Restart Bluetooth module", "Send AT+RESET? Bluetooth connections may disconnect; stored settings should remain unchanged."):
            return
        self.action("restart", tab.profile)

    def factory_reset(self):
        tab = self.selected_tab()
        if tab is None or tab.profile.factory_reset is None:
            return
        reset = tab.profile.factory_reset
        if not self.writes_enabled.get():
            messagebox.showwarning("Writes locked", "Enable AT WRITES before factory reset")
            return
        if not messagebox.askyesno("DANGER: factory settings", "This changes the MODULE, not just the GUI.\n"
                                   "Bluetooth pairing, UART speed and other configuration may be lost.\n"
                                   "A local snapshot will be saved first. Proceed?", icon="warning"):
            return
        confirmation = simpledialog.askstring("Confirm factory reset", "Type RESET in capital letters to proceed:")
        if confirmation != "RESET":
            self.log_line("Factory reset cancelled")
            return
        self.action("factory", tab.profile)

    def poll(self):
        try:
            for _ in range(75):
                try:
                    kind, data = self.queue_out.get_nowait()
                except queue.Empty:
                    break
                if kind == "log":
                    self.log_line(data["message"])
                elif kind == "connected":
                    self.connected_profile = data["profile"]
                    self.log_line(f"OPEN {data['port']} {data['baud']} 8N1 ({data['profile']})")
                elif kind == "disconnected":
                    self.connected_profile = None
                    self.log_line("COM closed")
                elif kind == "error":
                    self.log_line("ERROR: " + data["message"])
                    messagebox.showerror("AT Studio", data["message"])
                elif kind == "query":
                    tab = self.profile_tabs.get(data["profile"])
                    if tab is not None:
                        tab.update_query(data["qid"], data["reply"])
                elif kind == "change":
                    self.log_line("WRITE: " + str({**data, **({"old":"[REDACTED]","new":"[REDACTED]","actual":"[REDACTED]"} if data.get("qid")=="pin" else {})}))
                    state = data["status"]
                    if state == "verified":
                        messagebox.showinfo("Configuration", "Write acknowledged and readback VERIFIED."
                                            + (" Power-cycle the module, then adjust host baud." if data.get("power_cycle") else ""))
                    elif state == "pending_power_cycle":
                        messagebox.showwarning("Configuration", "Write acknowledged, but persistence is PENDING power-cycle and re-read. Update PC COM baud after restart.")
                    elif state == "unchanged":
                        messagebox.showinfo("Configuration", "Current module value already matches the requested value. No write was sent.")
                    else:
                        messagebox.showwarning("Unverified write", "Module replied OK, but readback did not match. Read the settings before proceeding.")
                elif kind == "snapshot":
                    self.log_line("Local snapshot: " + data["path"])
                elif kind == "inspection":
                    item = data["record"]
                    self.log_line("REGISTERED: #{} {} {} MAC={} scope={} (acceptance NOT EVALUATED)".format(
                        item["id"], item["module_code"], item["result"],
                        item["reported_mac"], data["test_code"]))
                    messagebox.showinfo("Inspection recorded", "Record #{} | {} | {}\nStored privately in: {}".format(
                        item["id"], item["module_code"], item["result"], item["database"]))
                elif kind == "restart":
                    messagebox.showinfo("Restart sent", "Restart command result: " + data["status"] + ". Re-read settings to verify they were retained.")
                elif kind == "factory":
                    messagebox.showwarning("Factory reset result", f"Reset command reply: {data['status']}.\n"
                                           "Check module settings and UART baud after restart; do not assume restore succeeded.")
                elif kind == "done":
                    self.busy = False
                    self.conn_status.set("Open: " + self.connected_profile if self.connected_profile else "Disconnected")
        finally:
            self.root.after(80, self.poll)

    def log_line(self, message):
        now = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{now}] {message}\n")
        if int(self.log.index("end-1c").split(".")[0]) > 1800:
            self.log.delete("1.0", "300.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def open_registry(self):
        RegistryWindow(self.root)

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def close(self):
        if not self.busy:
            self.queue_in.put(("stop", None, {}))
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class RegistryWindow:
    """Local browsing/export of immutable, scope-limited inspection records."""

    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("KonSol Tools | Private inspection registry")
        self.window.geometry("1050x620")
        self.window.transient(parent)
        self.mac = tk.StringVar()
        self.status = tk.StringVar(value=f"Database: {DEFAULT_DB}")
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="MAC (optional):").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.mac, width=24)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda event: self.refresh())
        ttk.Button(top, text="Search", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="All records", command=self.reset_filter).pack(side="left", padx=4)
        ttk.Label(top, text="Each run is a new record; incoming acceptance is NOT EVALUATED.").pack(
            side="right")

        columns = ("id", "module_code", "mac", "date", "profile", "test", "result", "source")
        outer = ttk.Frame(self.window, padding=(10, 2))
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=14)
        titles = ("#", "Module", "Reported MAC", "Test date", "Profile", "Test code", "Result", "Evidence")
        widths = (45, 110, 125, 105, 115, 195, 105, 155)
        for key, label, width in zip(columns, titles, widths):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=45)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(outer, orient="vertical", command=self.tree.yview).grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _: self.details())
        bottom = ttk.Frame(self.window, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Record details", command=self.details).pack(side="left", padx=3)
        ttk.Button(bottom, text="Export JSON", command=lambda: self.export("json")).pack(side="left", padx=3)
        ttk.Button(bottom, text="Export CSV", command=lambda: self.export("csv")).pack(side="left", padx=3)
        ttk.Button(bottom, text="HTML report", command=lambda: self.export("html")).pack(side="left", padx=3)
        ttk.Button(bottom, text="SQLite backup", command=lambda: self.export("sqlite3")).pack(side="left", padx=3)
        ttk.Label(self.window, textvariable=self.status, padding=10, anchor="w").pack(fill="x")
        self.refresh()

    def reset_filter(self):
        self.mac.set("")
        self.refresh()

    def refresh(self):
        try:
            rows = query_inspections(mac=self.mac.get().strip() or None, limit=10000)
        except (ValueError, OSError) as exc:
            messagebox.showwarning("Registry search", str(exc), parent=self.window)
            return
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for row in rows:
            self.tree.insert("", "end", iid=str(row["id"]), values=(
                row["id"], row["module_code"], row["reported_mac"],
                row["tested_on"], row["profile"], row["test_code"],
                row["result"], row["evidence_source"]))
        stats = db_status()
        self.status.set("{} | {} modules | {} inspections | shown {}".format(
            stats["path"], stats["modules"], stats["inspections"], len(rows)))

    def details(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Registry", "Select an inspection row", parent=self.window)
            return
        record = get_inspection(int(selected[0]))
        if record is None:
            return
        win = tk.Toplevel(self.window)
        win.title(f"Inspection #{record['id']} | {record['module_code']}")
        win.geometry("830x550")
        output = tk.Text(win, wrap="none", font=("Consolas", 10))
        output.pack(fill="both", expand=True)
        output.insert("1.0", json.dumps(record, indent=2, ensure_ascii=False))
        output.configure(state="disabled")

    def export(self, fmt):
        ext = {"json": ".json", "csv": ".csv", "html": ".html", "sqlite3": ".sqlite3"}[fmt]
        path = filedialog.asksaveasfilename(parent=self.window,
                                             defaultextension=ext,
                                             initialfile=f"konat-inspections{ext}")
        if not path:
            return
        task = {"json": export_json, "csv": export_csv,
                "html": generate_report, "sqlite3": backup_database}[fmt]
        try:
            saved = task(Path(path))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.window)
            return
        messagebox.showinfo("Export complete", f"Saved locally: {saved}\n\nMay contain Bluetooth MACs; do not publish it.", parent=self.window)
