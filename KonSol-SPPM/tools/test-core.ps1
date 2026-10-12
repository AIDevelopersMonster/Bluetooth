$ErrorActionPreference = 'Stop'
# Runs the Android-independent core regression tests (HexCodec, MacroCommand,
# SessionLog, Utf8StreamDecoder) on any machine with a JDK. No Android SDK needed.
$Root = Split-Path -Parent $PSScriptRoot
$Package = Join-Path $Root 'app/src/main/java/io/github/aidevelopersmonster/konsolsppm'
$Build = Join-Path $Root 'build/core-test'
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& javac -encoding UTF-8 -d $Build `
    (Join-Path $Package 'HexCodec.java') `
    (Join-Path $Package 'MacroCommand.java') `
    (Join-Path $Package 'SessionLog.java') `
    (Join-Path $Package 'Utf8StreamDecoder.java') `
    (Join-Path $PSScriptRoot 'TestCore.java')
if ($LASTEXITCODE -ne 0) { throw 'javac failed' }
& java -cp $Build io.github.aidevelopersmonster.konsolsppm.TestCore
if ($LASTEXITCODE -ne 0) { throw 'core tests failed' }
