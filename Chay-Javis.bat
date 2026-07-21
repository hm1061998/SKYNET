@echo off
where node >nul 2>nul
if errorlevel 1 set "PATH=C:\Users\Minh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;%PATH%"
set "PATH=%CD%\node_modules\.bin;%PATH%"

if exist "node_modules\.bin\yarn.cmd" (
  call "node_modules\.bin\yarn.cmd" start
) else (
  yarn start
)
