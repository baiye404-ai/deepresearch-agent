@echo off
REM Stop local middleware (PostgreSQL + Memurai). ASCII only.
setlocal
set PGBIN=C:\dr-runtime\pg\pgsql\bin
set PGDATA=C:\dr-runtime\pgdata
set MEM_CLI=C:\dr-runtime\memurai\extracted\Memurai\memurai-cli.exe

echo [STOP] PostgreSQL ...
"%PGBIN%\pg_ctl.exe" stop -D "%PGDATA%" -m fast -w -t 30 2>nul

echo [STOP] Memurai ...
"%MEM_CLI%" -h 127.0.0.1 -p 6379 SHUTDOWN NOSAVE >nul 2>&1
if errorlevel 1 taskkill /IM memurai.exe /F >nul 2>&1

echo [DONE] middleware stopped
