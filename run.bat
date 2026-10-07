@echo off
REM ==============================================================================
REM CreditPulse Lending Analytics Platform - One-Click Windows Runner
REM Author: Sandeep Choudhary (IIT Delhi)
REM ==============================================================================

echo [CreditPulse] Initializing environment...
IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [CreditPulse] Virtual environment not found! Creating .venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) ELSE (
    call .venv\Scripts\activate.bat
)

echo [CreditPulse] Launching Master Orchestration Pipeline...
python main.py

echo.
echo [CreditPulse] Execution Complete. Press any key to exit.
pause
