# KonSol-SPPM — KON Serial Port Profile Mobile

**v0.1.0 source prototype · 2026-10-12 · Android 8+ · Java · Classic SPP/RFCOMM.**

The Android application project is included. An installable APK is built via [GitHub Actions](../../actions/workflows/konsol-sppm-android.yml); **do not claim mobile hardware PASS until a real APK installation and SPP exchange have been observed**.

## Functions

- Already paired Bluetooth Classic devices: list/name/address, connect/disconnect, asynchronous RFCOMM SPP UUID \`00001101-0000-1000-8000-00805F9B34FB\`.
- Live timestamped RX/TX log, packet byte counts, TEXT UTF-8 / HEX display, Share log, Clear.
- Send TEXT with none/CR/LF/CRLF, or raw HEX bytes without EOL.
- **Eight assignable command buttons M1–M8.** Tap to transmit immediately; hold a button or tap **НАСТРОИТЬ КОМАНДНЫЕ КНОПКИ** to configure. Each button stores an individual label, complete command, encoding **TEXT UTF-8/HEX**, and EOL (none/CR/LF/CRLF). Commands survive app restarts. M5–M8 are initially unassigned; assign them through the settings button.
- Dedicated scrollable, timestamped **RX area** and separate manual command input **SEND**; byte TX/RX logging is independent of macro button configuration.
- Android 12+ nearby-devices permission BLUETOOTH_CONNECT; no network or location permission.

## Build APK in GitHub

1. Open **GitHub → Actions → Build KonSol-SPPM Android APK**.
2. Choose **Run workflow**, or check the build triggered by changes to \`KonSol-SPPM/\`.
3. Confirm a **green** \`android-debug\` result.
4. Download the artifact named \`KonSol-SPPM-v0.1-debug-apk\`; extract \`app-debug.apk\`, copy it to the Android phone and install. This is a lab debug APK (not a release).
5. If the workflow fails, collect the error log before claiming a deliverable APK.

Local Android Studio: open the \`KonSol-SPPM\` folder, sync and run \`:app:assembleDebug\`. AGP 8.9.2, Gradle 8.11.1, JDK 17, Android SDK 35.

## Using BT18-T

Pair BT18-T from **Android system Bluetooth settings (Classic)** first. The test UART \`AT+PIN?\` returned \`1234\` on an observed unit; pairing may be different per module. Open the app, allow Nearby devices, tap **СПИСОК**, select paired BT18-T using its address (two modules can have identical names) and tap **CONNECT**. If RFCOMM connects, use TEXT or HEX terminal and four configurable macros. Do not assume BLE discovery means Classic SPP support.

A complete data PASS requires bytes to appear on a UART attached to the **same** physical module. The diagnostic Windows BLE timeout has no bearing on Android Classic SPP.

## Tests and constraints

JDK-only codec tests:

\`\`\`powershell
cd C:\GitHub\Bluetooth\KonSol-SPPM
.\tools\test-core.ps1
\`\`\`

Expected 9 PASS lines after the programmable-buttons extension. The Java HEX codec and Android XML structure were checked in authoring environment; an Android SDK was unavailable there, so APK assembly and phone/hardware tests must be checked separately.

v0.1 limitations: foreground-only; no background service, BLE GATT, or discovery of unpaired devices; no PLC-specific command encoding yet; 40K character scrolling buffer; receiving split UTF-8 multibyte codepoints at packet boundaries can yield replacement characters. Each macro has its own encoding and EOL; the terminal text mode and EOL do not override programmed macros.

Files: \`MainActivity.java\` UI, \`SppClient.java\` RFCOMM, \`HexCodec.java\` bytes, \`tools/TestCodec.java\` JDK unit test, \`../.github/workflows/konsol-sppm-android.yml\` build workflow. Independent original downloadable full source archive is attached in the ChatGPT conversation.
