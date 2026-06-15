@echo off
:: schedule_maintenance.bat
:: Registers update_gis_data.py to run weekly in Windows Task Scheduler
:: NOTE: For automation setup, cron scheduling, and retry details, see docs/gis_endpoints.md

echo Checking Administrator privileges...
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Please right-click this script and run it as Administrator!
    pause
    exit /b
)

:: Get current directory with backslashes
set SCRIPT_PATH=%~dp0scripts\update_gis_data.py

echo Registering weekly GIS update task with 3-hour retry window in Task Scheduler...
schtasks /create /tn "CFR_GIS_Maintenance" /tr "python \"%SCRIPT_PATH%\"" /sc weekly /d SUN /st 03:00 /ri 60 /du 03:00 /f

if %errorlevel% eq 0 (
    echo SUCCESS: The weekly GIS update has been scheduled for Sundays at 3:00 AM, with 1-hour retries up to 3 hours.
) else (
    echo ERROR: Failed to register the scheduled task.
)

pause
