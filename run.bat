@echo off
echo HMM Shipping Line Tracker
echo ========================

IF "%~1"=="" (
    echo No booking ID provided, using default example: SINI25432400
    echo To use a custom booking ID, use: run.bat YOUR_BOOKING_ID
    python main.py
) ELSE (
    echo Tracking booking ID: %1
    python main.py %1
)
