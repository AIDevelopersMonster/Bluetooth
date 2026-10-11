$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Package = Join-Path $Root 'app/src/main/java/io/github/aidevelopersmonster/konsolsppm'
$Build = Join-Path $Root 'build/codec-test'
New-Item -ItemType Directory -Force -Path $Build | Out-Null
& javac -encoding UTF-8 -d $Build (Join-Path $Package 'HexCodec.java') (Join-Path $Package 'MacroCommand.java') (Join-Path $PSScriptRoot 'TestCodec.java')
if ($LASTEXITCODE -ne 0) { throw 'javac failed' }
& java -cp $Build io.github.aidevelopersmonster.konsolsppm.TestCodec
if ($LASTEXITCODE -ne 0) { throw 'codec tests failed' }
