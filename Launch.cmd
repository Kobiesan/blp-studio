@echo off
if exist "%~dp0BLPStudio.exe" (
  start "" "%~dp0BLPStudio.exe" %*
) else (
  start "" "%~dp0dist\BLPStudio.exe" %*
)
