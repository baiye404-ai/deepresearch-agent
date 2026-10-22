@echo off
REM ===============================================================
REM Start Memurai (Redis 7.2 compatible) on port 6379
REM No admin required: runs as a console process, not a service.
REM NOTE: the Memurai config parser rejects non-ASCII paths, so both
REM the binaries and the data dir live under C:\dr-runtime (ASCII),
REM not inside the project directory.
REM (ASCII only: cmd.exe parses .bat in the OEM codepage.)
REM ===============================================================
setlocal
set MEM_EXE=C:\dr-runtime\memurai\extracted\Memurai\memurai.exe
set MEM_CONF=C:\dr-runtime\memurai\memurai.conf
set MEM_CLI=C:\dr-runtime\memurai\extracted\Memurai\memurai-cli.exe

if not exist "%MEM_EXE%" (
    echo [ERROR] Memurai not found: %MEM_EXE%
    echo         see runtime\README.md for install steps
    exit /b 1
)

"%MEM_CLI%" -h 127.0.0.1 -p 6379 PING >nul 2>&1
if %errorlevel%==0 (
    echo [SKIP] Memurai already running on 6379
    exit /b 0
)

echo [START] Memurai 127.0.0.1:6379  (detached console)
REM Launch through PowerShell Start-Process so Memurai gets its own console.
REM `start /b` makes it inherit the caller's console/process group, so a
REM console-group abort (Ctrl+C, job-tree kill) in that session takes the
REM Redis-compatible server down with it.
powershell -NoProfile -Command "Start-Process -FilePath '%MEM_EXE%' -ArgumentList '%MEM_CONF%' -WindowStyle Hidden"

REM NOTE: `ping` instead of `timeout /t` -- `timeout` aborts under redirected
REM stdin and would break this readiness loop.
for /l %%i in (1,1,15) do (
    "%MEM_CLI%" -h 127.0.0.1 -p 6379 PING >nul 2>&1
    if not errorlevel 1 (
        echo [READY] Memurai listening on 6379
        exit /b 0
    )
    ping -n 2 127.0.0.1 >nul
)
echo [FAIL] not ready in 15s, log: C:\dr-runtime\memurai\data\memurai.log
exit /b 1
