@echo off
setlocal
cd /d "%~dp0"
py -m konat.registry_cli %*
