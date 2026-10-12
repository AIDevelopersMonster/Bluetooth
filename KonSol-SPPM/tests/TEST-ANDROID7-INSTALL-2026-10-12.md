# TEST-ANDROID7-INSTALL — Xiaomi Redmi 5 Plus / MIUI

**Дата:** 2026-10-12  
**Статус:** прежние ADB-установки **BLOCKED**; в более позднем GUI-журнале найдено **`Finished installing`**, требуется отдельная проверка `pm path`. Запуск KonSol-SPPM и SPP не подтверждены.

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
- **НЕ ЗАФИКСИРОВАНО:** вредоносность APK, дефект Java KonSol-SPPM, подтверждённая регистрация пакета в PackageManager, открытие UI, Classic SPP connection, UART exchange.
- Следующее ограниченное действие по желанию владельца: проверить локальную установку **с временно отключённой Play Protect проверкой** и немедленно вернуть её обратно; **не** изменять систему, прошивку, не требовать SIM, root, bootloader unlock. Если не помогло, остановить тест данного экземпляра телефона и испытать APK на другом Android-устройстве.

Эта запись фиксирует блокировку установки, а не неуспех функциональности KonSol-SPPM.

## Дополнение: журнал 03:31–03:56 (предоставлен владельцем 12.10.2026)

Команда `adb logcat -d -v time` завершилась выводом журнала после промежуточных `adb devices` в состоянии `offline` или без устройств. Логи включают:

```text
10-12 03:38:24 E/AndroidRuntime(6906): Process: com.miui.cloudservice
10-12 03:38:24 E/AndroidRuntime(6906): java.lang.NoClassDefFoundError:
  Failed resolution of: Lmiui/cloud/app/NotificationChannelAdapter;
10-12 03:40:37 W/ActivityManager: Scheduling restart of crashed service
  com.android.vending/com.google.android.finsky.verifier.impl.service.impl.PackageVerificationService
10-12 03:55:04 I/InstallAppProgress(11367): Finished installing io.github.aidevelopersmonster.konsolsppm
10-12 03:55:13 I/Timeline: Activity_launch_request ... com.android.packageinstaller.InstallAppProgress
10-12 03:55:27 F/art(12410): "PackageInstallerImpl" ... Native
10-12 03:55:29 W/ActivityManager: Service crashed 2 times ... PackageVerificationService
```

**Интерпретация:** запись `Finished installing` — свидетельство достижения стадии завершения установки **KonSol-SPPM** и исключает категорическое «приложение точно не установлено». Однако один этот лог не подтверждает системный `INSTALL_SUCCEEDED`; требуется `adb shell pm path io.github.aidevelopersmonster.konsolsppm` (либо `pm list packages`). Падение `com.miui.cloudservice` и перезапуски `com.android.vending` относятся к системным сервисам, не к процессу нашего приложения. По логам недостаточно оснований связывать эти падения исключительно с нашей установкой или считать их ошибкой SPP/Java KonSol-SPPM.

**Следующая минимальная проверка после восстановления ADB:** `adb shell pm path io.github.aidevelopersmonster.konsolsppm`; при наличии `package:...` — `adb shell am start -n io.github.aidevelopersmonster.konsolsppm/.MainActivity`. При успехе фиксировать фактическое открытие интерфейса. Не очищать `logcat` до сохранения протокола.

**Текущий тестируемый вариант:** KonSol-SPPM v0.1.2 (App17 toolchain) на Android 7.1.2. Отличать факты этого варианта от прежних тестов v0.1.1; в присланном журнале не указан подтверждённый `versionCode` установленного пакета.
