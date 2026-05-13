@echo off
cd /d "%~dp0"
echo === VPN Client ===
echo.
echo Выбери вариант:
echo   P — запустить xray-core (SOCKS5 :1080 / HTTP :1081)
echo   W — запустить wsclient (только Render прокси)
echo.
choice /C PW /N /M "Вариант (P/W): "
if errorlevel 2 goto ws
if errorlevel 1 goto xray

:xray
echo.
echo Запускаю xray-core...
powershell -ExecutionPolicy Bypass -File "setup-pc.ps1"
goto end

:ws
echo.
echo Запускаю WebSocket-клиент...
python wsclient.py
pause
goto end

:end
