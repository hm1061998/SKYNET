@echo off
setlocal
title Hermes Agent
cd /d "%~dp0"

rem ---- Tim lenh hermes: PATH truoc, sau do cac vi tri cai dat quen thuoc ----
set "HERMES_CMD="
where hermes >nul 2>nul && set "HERMES_CMD=hermes"
if not defined HERMES_CMD if exist "%USERPROFILE%\.local\bin\hermes.exe" set "HERMES_CMD=%USERPROFILE%\.local\bin\hermes.exe"
if not defined HERMES_CMD if exist "%USERPROFILE%\.local\bin\hermes.cmd" set "HERMES_CMD=%USERPROFILE%\.local\bin\hermes.cmd"
if not defined HERMES_CMD if exist "%USERPROFILE%\.local\bin\hermes.bat" set "HERMES_CMD=%USERPROFILE%\.local\bin\hermes.bat"
if not defined HERMES_CMD if exist "%USERPROFILE%\.hermes\hermes-agent\venv\Scripts\hermes.exe" set "HERMES_CMD=%USERPROFILE%\.hermes\hermes-agent\venv\Scripts\hermes.exe"
if not defined HERMES_CMD if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe" set "HERMES_CMD=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe"
if not defined HERMES_CMD if exist "%LOCALAPPDATA%\Programs\hermes\hermes.exe" set "HERMES_CMD=%LOCALAPPDATA%\Programs\hermes\hermes.exe"

if defined HERMES_CMD goto :run

echo.
echo  [!] Chua tim thay Hermes Agent tren may nay.
echo      Can chay trinh cai dat truoc - chi can 1 lan duy nhat.
echo.
choice /C YN /M "Chay cai dat ngay bay gio"
if errorlevel 2 goto :end
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0hermes-migration\Cai-Hermes.ps1"
echo.
echo  Cai dat xong. Hay MO LAI file Chay-Hermes.bat nay de bat dau.
goto :end

:run
"%HERMES_CMD%"
if errorlevel 1 (
    echo.
    echo  [!] Hermes thoat voi loi. Thu chay "hermes doctor" trong PowerShell de kiem tra.
)

:end
echo.
pause
