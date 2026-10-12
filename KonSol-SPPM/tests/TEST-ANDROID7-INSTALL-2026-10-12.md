# TEST-ANDROID7-INSTALL — Xiaomi Redmi 5 Plus / MIUI

**Дата:** 2026-10-12  
**Статус:** **BLOCKED BY DEVICE INSTALLATION / VERIFIER**; запуск приложения и SPP не проверены.

## APK

KonSol-SPPM v0.1.1, Android API 24+, GitHub Actions [#9](https://github.com/AIDevelopersMonster/Bluetooth/actions/runs/38185476622) **PASS**: JVM codec tests, Gradle `assembleDebug`, `classes.dex`, `aapt sdkVersion:'24'`, artifact `KonSol-SPPM-v0.1.1-Android7-debug-apk`. CI PASS не означает успешной установки на телефон.

## Устройство

- Xiaomi Redmi 5 Plus, ADB model `Redmi_5_Plus`, product/device `vince`, Android 7 (по заявлению пользователя).
- Тестовый телефон без SIM-карты; SIM не требуется для работы Bluetooth SPP.
- `adb devices -l` → устройство присутствует, status `device`.

## Наблюдения с устройства

Прямые попытки установки:
```text
adb install -r -t .\app-debug.apk
Performing Streamed Install
Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]
```
```text
adb push .\app-debug.apk /data/local/tmp/konsol-sppm.apk
1 file pushed, 0 skipped. 29763 bytes transferred.
adb shell pm install -r -t /data/local/tmp/konsol-sppm.apk
Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]
```
GUI PackageInstaller: «вечная установка» (со слов пользователя). При воспроизведении журнал `logcat`:
```text
I/Finsky(3984): VerifyApps: Anti-malware verification task started for package=io.github.aidevelopersmonster.konsolsppm
I/Finsky(3984): VerifyApps: Installer app: com.google.android.packageinstaller
I/Finsky(3984): VerifyApps: Starting APK Analysis scan for io.github.aidevelopersmonster.konsolsppm
I/Finsky(3984): VerifyApps: firstScanResult for package=io.github.aidevelopersmonster.konsolsppm: 3
E/Finsky(3984): VerifyApps: Unable to get APK Analysis scan result. package=io.github.aidevelopersmonster.konsolsppm
F/art(3984): art/runtime/runtime.cc:422] native: #09 ... /system/lib64/libmiuiclassproxy.so
F/art(3984): art/runtime/runtime.cc:422] "PackageInstallerImpl" prio=4 tid=70 Native
```

## Разграничение выводов

- **PASS:** ADB transport, API 24 APK build, DEX presence, JVM tests.
- **BLOCKED:** MIUI `INSTALL_FAILED_USER_RESTRICTED` for ADB installs; GUI path enters Finsky/VerifyApps verification then logs fatal Android Runtime native frame in MIUI library in process PID 3984.
- **НЕ УСТАНОВЛЕНО:** действительно ли сбой Google verifier является единственной причиной зависания GUI; полный crash backtrace не предоставлен.
- **НЕ ЗАФИКСИРОВАНО:** вредоносность APK, дефект Java KonSol-SPPM, успешная установка, открытие UI, Classic SPP connection, UART exchange.
- Следующее ограниченное действие по желанию владельца: проверить локальную установку **с временно отключённой Play Protect проверкой** и немедленно вернуть её обратно; **не** изменять систему, прошивку, не требовать SIM, root, bootloader unlock. Если не помогло, остановить тест данного экземпляра телефона и испытать APK на другом Android-устройстве.

Эта запись фиксирует блокировку установки, а не неуспех функциональности KonSol-SPPM.
