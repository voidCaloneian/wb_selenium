#!/bin/bash
echo "Получаем текущую директорию"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo $SCRIPT_DIR

echo "Запускаем хром"
nohup google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/unique_chrome_profile" > /tmp/start_chrome.log 2>&1 &

echo "Запускаем скрипт"
sudo -E $SCRIPT_DIR/env/bin/python3 $SCRIPT_DIR/main.py