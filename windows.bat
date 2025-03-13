@echo off
REM Получаем директорию скрипта
set SCRIPT_DIR=%~dp0

REM Запускаем Google Chrome с remote debugging (проверьте путь к chrome.exe)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\temp\unique_chrome_profile"

REM Запускаем Python-скрипт из виртуального окружения
REM На Windows виртуальное окружение обычно находится в папке env\Scripts
call env\Scripts\activate
python main.py

pause