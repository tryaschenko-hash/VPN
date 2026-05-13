@echo off
cd /d "%~dp0"
echo Starting SOCKS5 proxy on 0.0.0.0:1080 --^> Render...
echo.
echo Happ настройки: SOCKS5 %COMPUTERNAME%-IP:1080
echo.
python wsclient.py
pause
