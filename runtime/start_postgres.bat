@echo off
REM ===============================================================
REM Start PostgreSQL 17 (portable) on port 5432.
REM No admin required: initdb + pg_ctl run as the current user,
REM no Windows service is registered.
REM
REM IMPORTANT: pg_ctl is launched through PowerShell Start-Process so it
REM gets its own console/process group. Launching it directly (cmd /c or
REM WMI) makes the postgres children inherit the caller's console group,
REM and a Ctrl+C / console-group abort in that session kills the server
REM (logged as "terminated by exception 0xC000013A").
REM
REM First run performs initdb, later runs just start the server.
REM (ASCII only: cmd.exe parses .bat in the OEM codepage.)
REM ===============================================================
setlocal
set PGBIN=C:\dr-runtime\pg\pgsql\bin
set PGDATA=C:\dr-runtime\pgdata
set PGPORT=5432

if not exist "%PGBIN%\initdb.exe" (
    echo [ERROR] PostgreSQL not found: %PGBIN%
    exit /b 1
)

if not exist "%PGDATA%\PG_VERSION" (
    echo [INIT] running initdb -D "%PGDATA%" ...
    "%PGBIN%\initdb.exe" -D "%PGDATA%" -U postgres --pwfile="%~dp0pg\pw.txt" -E UTF8 --locale=C
    if errorlevel 1 (
        echo [FAIL] initdb failed
        exit /b 1
    )
    >> "%PGDATA%\postgresql.conf" echo listen_addresses = '127.0.0.1'
    >> "%PGDATA%\postgresql.conf" echo port = %PGPORT%
    echo [DONE] data directory initialized: %PGDATA%
)

"%PGBIN%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT% >nul 2>&1
if %errorlevel%==0 (
    echo [SKIP] PostgreSQL already running on 5432
    exit /b 0
)

echo [START] PostgreSQL 127.0.0.1:5432  (detached console)
powershell -NoProfile -Command "Start-Process -FilePath '%PGBIN%\pg_ctl.exe' -ArgumentList 'start','-D','%PGDATA%','-l','%~dp0pg\postgres.log' -WindowStyle Hidden"
if errorlevel 1 (
    echo [FAIL] could not launch pg_ctl
    exit /b 1
)

REM NOTE: use `ping` instead of `timeout /t` for the wait loop. `timeout`
REM aborts with "Input redirection is not supported" when the script is run
REM with redirected stdin (e.g. launched by another process), which breaks
REM the readiness loop and makes the script report a false failure.
REM Cold start can exceed 20s because PostgreSQL replays WAL after an
REM unclean shutdown, so allow up to ~60s.
for /l %%i in (1,1,60) do (
    "%PGBIN%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT% >nul 2>&1
    if not errorlevel 1 (
        echo [READY] PostgreSQL listening on 5432
        exit /b 0
    )
    ping -n 2 127.0.0.1 >nul
)
echo [FAIL] not ready in 60s, see log: %~dp0pg\postgres.log
exit /b 1
