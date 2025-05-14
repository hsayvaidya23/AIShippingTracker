@echo off
echo HMM Shipping Line Tracker (Adaptive)
echo ==================================

SET HEADLESS=

IF "%1"=="-h" (
    SET HEADLESS=--headless
    SHIFT /1
) ELSE IF "%1"=="--headless" (
    SET HEADLESS=--headless
    SHIFT /1
)

IF "%~1"=="" (
    echo No booking ID provided, using default example: SINI25432400
    echo To use a custom booking ID, use: run_adaptive.bat [--headless] YOUR_BOOKING_ID
    python adaptive_tracking.py %HEADLESS%
) ELSE (
    echo Tracking booking ID: %1
    python adaptive_tracking.py %HEADLESS% %1
)

pause 