@echo off
setlocal

set "MERCURY_BINARY=%~dp0mercury\mercury.exe"
set "MERCURY_PROFILE=%~dp0USER_DATA"

if not exist "%MERCURY_BINARY%" (
  echo Mercury executable not found: "%MERCURY_BINARY%" 1>&2
  exit /b 127
)

if not exist "%MERCURY_PROFILE%" mkdir "%MERCURY_PROFILE%"
if errorlevel 1 exit /b %errorlevel%

start "" "%MERCURY_BINARY%" --profile "%MERCURY_PROFILE%" %*
exit /b %errorlevel%
