# KonSol-SPPM — Bluetooth Classic SPP Mobile Terminal

**Version:** v0.1.2 (prototype) · Android 6.0+ (API 23) · Java · RFCOMM/SPP.

KonSol-SPPM is an **equipment-independent** mobile terminal for development, setup and testing of UART-connected devices over Bluetooth Classic SPP. Commands and button labels are configured in the mobile UI. It is not embedded firmware and does not implement a specific equipment protocol.

## Capabilities

- Connect/disconnect to an already paired Bluetooth Classic SPP device, RFCOMM UUID `00001101-0000-1000-8000-00805F9B34FB`.
- Separate TX command input and scrollable, timestamped RX/TX log.
- TEXT (UTF-8) and HEX command input, selectable None/CR/LF/CRLF line ending.
- Eight programmable buttons M1–M8: user-defined label, TEXT or HEX payload and line ending, persisted across launches. Tap to send; long press or use **НАСТРОИТЬ КОМАНДНЫЕ КНОПКИ** to edit.
- Share/clear the session log.
- No cloud or network dependencies.

**Prototype note:** In v0.1.2, M1–M4 still contain demonstration commands `PING`, `STATUS`, `HELP`, `?`; M5–M8 are initially blank. Those defaults are not part of any fixed equipment protocol and can be changed in the UI. The desired subsequent behavior is to ship all eight slots blank.

## Build

Source: `KonSol-SPPM/app/`. Android Gradle Plugin **8.7.3**, Gradle **8.9**, JDK **17**, Android SDK **35**, `minSdk 23`, `targetSdk 35`.

GitHub Actions: [Build KonSol-SPPM Android APK](https://github.com/AIDevelopersMonster/Bluetooth/actions/workflows/konsol-sppm-android.yml).

Workflow `assembleDebug` produces `app-debug.apk` as an Actions artifact. Download and extract the artifact ZIP to obtain the APK. The project currently has no published stable Android release.

Local build from `KonSol-SPPM`:

```powershell
gradle --no-daemon :app:assembleDebug
```

Unit tests for TEXT/HEX command encoding and programmable button payloads:

```powershell
.\tools\test-core.ps1
```

## Use

Pair a Classic Bluetooth SPP device in Android Bluetooth settings, open KonSol-SPPM, select it from the paired-device list and press **CONNECT**. Enter commands using SEND or assign your own button commands in the UI. The selected protocol and line endings must match the equipment connected to the Bluetooth-UART module.

## Scope and validation

- Classic Bluetooth SPP only; **not BLE GATT**.
- Foreground terminal; only paired devices listed.
- Android build/packaging validation is available in GitHub Actions. **No completed physical SPP acceptance test of KonSol-SPPM is claimed.**
- Device-specific installation logs, transient ADB/MIUI incidents and unsuccessful local attempts are not part of the project documentation. Keep published lab results limited to reproducible and technically meaningful evidence.
