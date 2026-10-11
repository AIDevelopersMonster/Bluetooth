#!/usr/bin/env python3
"""Discover BLE advertisements and optionally list a device's GATT layout.

No GATT characteristics are written. Classic Bluetooth SPP is NOT scanned.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except Exception as error:
    # ImportError may originate *inside* installed Bleak (e.g. WinRT),
    # so reporting "Missing bleak" for every import failure is misleading.
    import importlib.metadata
    import traceback

    print(f"BLE import failed: {type(error).__name__}: {error}", file=sys.stderr)
    print(f"Python: {sys.version.split()[0]}  Executable: {sys.executable}", file=sys.stderr)
    try:
        version = importlib.metadata.version("bleak")
        print(f"Installed bleak distribution: {version}", file=sys.stderr)
    except importlib.metadata.PackageNotFoundError:
        print("Installed bleak distribution: NOT FOUND", file=sys.stderr)

    if isinstance(error, ModuleNotFoundError) and error.name == "bleak":
        print(
            "bleak is not installed for this Python. Install with: "
            "py -m pip install --user -r DX-BT18/tools/requirements.txt",
            file=sys.stderr,
        )
    else:
        print(
            "The import failed despite the package being present or while loading "
            "a dependency. Do NOT reinstall packages blindly; inspect the traceback.",
            file=sys.stderr,
        )
    traceback.print_exc()
    sys.exit(2)


async def run(args: argparse.Namespace) -> int:
    print(f"BLE scan: {args.duration:g}s (NOT Classic SPP)")
    discovered = await BleakScanner.discover(timeout=args.duration, return_adv=True)
    matches = 0
    for device, adv in sorted(discovered.values(), key=lambda item: item[0].address):
        name = adv.local_name or device.name or "(no name)"
        if args.name and args.name.casefold() not in name.casefold():
            continue
        matches += 1
        print(f"\nName: {name}\nBLE address/OS identifier: {device.address}\nRSSI: {adv.rssi} dBm")
        print("Advertised service UUIDs:", ", ".join(adv.service_uuids) or "(none)")
        if adv.manufacturer_data:
            print("Manufacturer data IDs:",
                  ", ".join(f"0x{code:04X}" for code in sorted(adv.manufacturer_data)))
    print(f"\nDevices matching filter: {matches}")
    print("Name, UUIDs and Bluetooth addresses do not prove original DX-BT18 hardware.")

    if args.address:
        # Pass the BLEDevice obtained during *this scan*. Passing a string address
        # makes BleakClient perform another implicit scan and can lead to
        # confusing delays/failures, especially on Windows/WinRT.
        target = next(
            (device for device, _ in discovered.values()
             if device.address.casefold() == args.address.casefold()),
            None,
        )
        if target is None:
            print(
                f"GATT NOT ATTEMPTED: {args.address} was not observed in this scan. "
                "Run the discovery again; TEST-02A advertising results remain valid.",
                file=sys.stderr,
            )
            return 3

        print(
            f"\nConnecting to discovered BLEDevice {target.address!r} "
            f"(GATT timeout: {args.connect_timeout:g}s)...",
            flush=True,
        )

        async def connect_and_list() -> None:
            async with BleakClient(target, timeout=args.connect_timeout) as client:
                print("Connected:", client.is_connected, flush=True)
                for service in client.services:
                    print(f"SERVICE {service.uuid}  {service.description}", flush=True)
                    for characteristic in service.characteristics:
                        print(
                            "  CHAR", characteristic.uuid,
                            "properties:", ",".join(characteristic.properties),
                            flush=True,
                        )
                        for descriptor in characteristic.descriptors:
                            print("    DESC", descriptor.uuid, flush=True)
            print("Disconnected. No GATT characteristic value was read or written.", flush=True)

        try:
            await asyncio.wait_for(
                connect_and_list(), timeout=args.connect_timeout
            )
        except asyncio.TimeoutError:
            print(
                "GATT CONNECT TIMEOUT: connection/services enumeration not confirmed. "
                "Previously observed BLE advertising remains PASS.",
                file=sys.stderr,
            )
            return 3
        except Exception as error:
            print(
                f"GATT CONNECTION ERROR: {type(error).__name__}: {error}. "
                "BLE advertising remains PASS; no GATT PASS.",
                file=sys.stderr,
            )
            return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=10.0, help="scan duration, seconds")
    parser.add_argument("--name", help="optional name substring filter, e.g. BT18")
    parser.add_argument("--address", help="optional BLE identifier for GATT enumeration (may connect)")
    parser.add_argument("--connect-timeout", type=float, default=25.0,
                        help="maximum seconds for GATT connection and service enumeration; default: 25")
    args = parser.parse_args()
    if not 1.0 <= args.duration <= 120:
        parser.error("--duration must be 1..120 seconds")
    if not 5.0 <= args.connect_timeout <= 120.0:
        parser.error("--connect-timeout must be 5..120 seconds")
    try:
        return asyncio.run(run(args))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"Bluetooth error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
