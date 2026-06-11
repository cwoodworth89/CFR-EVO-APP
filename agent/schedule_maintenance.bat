@echo off
:: schedule_maintenance.bat
:: Registers update_gis_data.py to run monthly in Windows Task Scheduler

echo Checking Administrator privileges...
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Please right-click this script and run it as Administrator!
    pause
    exit /b
)

:: Get current directory with backslashes
set SCRIPT_PATH=%~dp0scripts\update_gis_data.py

echo Registering monthly GIS update task in Task Scheduler...
schtasks /create /tn "CFR_GIS_Maintenance" /tr "python \"%SCRIPT_PATH%\"" /sc monthly /mo 1 /d 1 /st 03:00 /f

if %errorlevel% eq 0 (
    echo SUCCESS: The monthly GIS update has been scheduled for the 1st of every month at 3:00 AM.
) else (
    echo ERROR: Failed to register the scheduled task.
)

pause
