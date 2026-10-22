@echo off
REM ===============================================================
REM Start the backend for the FULL local deployment.
REM   Python env   : backend\.venv
REM   Database     : PostgreSQL 17 portable (runtime\start_postgres.bat)
REM   Session/queue: Memurai, Redis 7.2 compatible (runtime\start_memurai.bat)
REM   Knowledge base: embedded Milvus Lite (C:\dr-runtime\milvus\milvus.db)
REM   Checkpoints  : PostgreSQL (Memurai lacks RediSearch, so Redis
REM                  checkpoints are not usable here)
REM
REM IMPORTANT: use run_server.py, not the uvicorn command. psycopg's async
REM mode does not work with the Windows ProactorEventLoop, and run_server.py
REM forces a SelectorEventLoop.
REM
REM See runtime\README.md for the full setup and troubleshooting notes.
REM (ASCII only: cmd.exe parses .bat in the OEM codepage.)
REM ===============================================================
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -e . ipython milvus-lite "psycopg[binary]" langgraph-checkpoint-postgres
    exit /b 1
)

echo [START] backend http://127.0.0.1:2024   (Ctrl+C to stop)
".venv\Scripts\python.exe" run_server.py
