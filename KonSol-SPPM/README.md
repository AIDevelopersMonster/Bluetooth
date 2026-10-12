# KonSol-SPPM — Bluetooth Classic SPP Universal Android Terminal

**Version:** v0.1.3 (MVP build) · Android 6.0+ (minSdk 23, control platform Android 7.1.2 / API 25) · Java · RFCOMM/SPP · targetSdk/compileSdk 35.

KonSol-SPPM is an **equipment-independent** mobile terminal for development, setup and on-site debugging of UART-connected devices over Bluetooth Classic Serial Port Profile. Commands, button labels, formats and line endings are configured by the user directly on the phone. It is not embedded firmware, not a control system, and implements no fixed equipment protocol. No server, internet, cloud, registration or root is required.

## Capabilities (MVP)

- **FR-01 Connect:** list already-paired Classic Bluetooth devices, show the selected name, connect over RFCOMM with the standard SPP UUID `00001101-0000-1000-8000-00805F9B34FB`, disconnect on demand; states `DISCONNECTED / CONNECTING / CONNECTED / ERROR`; missing adapter, disabled radio, denied permission and failed connects are handled without blocking the UI (all socket I/O runs on background threads).
- **FR-02 Manual TX:** input line + **SEND**; TEXT mode sends UTF-8 with selectable ending NONE / CR (`0D`) / LF (`0A`) / CRLF; HEX mode sends exactly the entered bytes (line ending is *not* appended — type `0D`/`0A` explicitly). Malformed HEX produces a clear error and nothing is sent. Sending while disconnected is refused with a message.
- **FR-03 RX journal:** continuous reception; raw bytes are stored unmodified; entries carry a millisecond timestamp and separate TX/RX markers; view switches render RX as TEXT (with correct reassembly of UTF-8 characters split across consecutive RFCOMM reads) or as HEX byte-exact dump; scrollable, bounded in memory (last 2000 entries), clear button, export via the standard Android share sheet. RFCOMM read boundaries are treated as stream fragments, never as protocol message boundaries.
- **FR-04 Eight programmable buttons M1–M8:** every slot ships **blank** — no PING/STATUS/HELP/relay commands or any other demo values are embedded in the source. Tap a blank slot → editor opens; tap an assigned slot → its command is sent; long press → editor. Per-button label, TEXT/HEX format and line ending are persisted locally. Editing works without a connection; assignments survive app restarts and ordinary APK updates.
- **FR-05 UI:** single screen: title + connection state, paired-device picker + CONNECT/DISCONNECT, TX/RX journal, manual input + SEND, TEXT/HEX and EOL selectors, M1–M8 grid, macro configuration / clear / export access. Four weighted columns with ellipsized captions keep the layout usable at 320–400 dp width and enlarged system fonts; `adjustResize` keeps the input line and SEND reachable while the soft keyboard is open.

## Architecture

| Component | Responsibility |
|---|---|
| `MainActivity` | UI and user actions only (main thread) |
| `SppClient` | RFCOMM connect/disconnect, TX queue, continuous RX loop, generation tickets for safe reconnect |
| `HexCodec` | TEXT↔bytes and HEX↔bytes conversion, hex display |
| `MacroCommand` | one persistent user command button (pure JVM class) |
| `SettingsRepository` | SharedPreferences persistence: M1–M8, TX mode/EOL, RX view, last device address |
| `SessionLog` | bounded ring-buffer journal + export text (pure JVM class) |
| `Utf8StreamDecoder` | reassembles UTF-8 characters split across socket reads (pure JVM class) |

Permissions: `BLUETOOTH` (maxSdk 30) + runtime `BLUETOOTH_CONNECT` request on Android 12+; legacy model on older Android. No location, BLE scan or network permissions — the MVP lists bonded devices only.

## Build

Toolchain: Android Gradle Plugin **8.7.3**, Gradle **8.9**, JDK **17**, compileSdk **35**, `minSdk 23`.

CI (reproducible): workflow [`konsol-sppm-android.yml`](../.github/workflows/konsol-sppm-android.yml) runs the core regression tests, builds `:app:assembleDebug`, verifies DEX/signature/alignment, prints SHA-256 and uploads the installable APK artifact.

Local build from `KonSol-SPPM`:

```powershell
gradle --no-daemon :app:assembleDebug
```

Core unit tests (JDK only, no Android SDK needed):

```powershell
.\tools\test-core.ps1
```

## Use

Pair the Classic Bluetooth SPP device once in Android Bluetooth settings, open KonSol-SPPM, pick it from the list and press **CONNECT**. Send commands manually (TEXT/HEX + ending) or assign your own commands to M1–M8 (long press or «НАСТРОИТЬ КОМАНДНЫЕ КНОПКИ»). The chosen byte format and line endings must match the equipment behind the Bluetooth-UART bridge; the app transmits exactly what is configured.

## Scope and validation status

- Classic Bluetooth SPP only; **not BLE GATT**; foreground terminal; no auto-reconnect service.
- 30 plain-JVM core checks pass locally and in CI (hex exactness, endings, blank slots, journal bound, split-UTF-8 reassembly).
- GitHub Actions validates packaging for Android 7-class devices (API 23 minSdk verified in the APK). **Physical SPP acceptance (AT-03…AT-12) against real hardware (e.g. BT18-T) and the cross-device matrix are still to be executed on site** — a successful APK build is not proof of functional operation.
- Device-specific installation logs and transient support incidents stay out of the published project; only reproducible, meaningful results belong here.
