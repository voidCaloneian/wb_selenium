import os
import sys
import json
import re
import time
import logging
import subprocess
import threading
import requests
import keyboard
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Подключаемся к запущенному браузеру Chrome через remote debugging
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
try:
    driver = webdriver.Chrome(options=chrome_options)
    logging.info("Подключились к запущенному браузеру Chrome через remote debugging.")
except Exception as exc:
    logging.error(f"Ошибка подключения к запущенному Chrome: {exc}")
    sys.exit(1)


def get_output_folder(driver) -> str:
    """
    Извлекает название товара и артикль из страницы:
    - Название товара находится между тегами:
      <script type="jsv#73^"></script>Тапочки домашние меховые<script type="jsv/73^">
    - Артикль извлекается из URL по шаблону /catalog/<артикль>/feedbacks
    Возвращает строку с именем папки "название товара_артикль".
    """
    page_source = driver.page_source
    # Ищем название товара между заданными тегами
    title_match = re.search(
        r'<script\s+type="jsv#73\^"></script>\s*(.*?)\s*<script\s+type="jsv/73\^">',
        page_source,
        re.DOTALL,
    )
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = "unknown_product"

    current_url = driver.current_url
    article_match = re.search(r"/catalog/(\d+)/feedbacks", current_url)
    if article_match:
        article = article_match.group(1)
    else:
        article = "unknown_article"

    folder_name = f"{title}_{article}"
    # Убираем недопустимые символы для имени папки
    folder_name = re.sub(r'[\\/*?:"<>|]', "_", folder_name)
    logging.info(f"Определено название папки: {folder_name}")
    return folder_name


def download_ts_segments(driver, folder: str) -> list:
    """
    Извлекает логи производительности (network) из Selenium,
    находит TS-сегменты, скачивает их в папку folder и возвращает список путей к файлам.
    """
    logging.info("Извлекаем сетевые логи для поиска TS-сегментов...")
    logs = driver.get_log("performance")
    ts_urls = []
    # Фильтруем логи: ищем ответ с URL, содержащим '.ts'
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.responseReceived":
                url = msg["params"]["response"].get("url", "")
                if ".ts" in url and url not in ts_urls:
                    ts_urls.append(url)
        except Exception:
            continue

    if not ts_urls:
        logging.info("TS-сегменты не найдены в логах.")
        return []

    # Сортируем URL по номеру сегмента (предполагается, что URL заканчиваются, например, на '/1.ts', '/2.ts', ...)
    try:
        ts_urls = sorted(ts_urls, key=lambda url: int(url.rstrip(".ts").split("/")[-1]))
    except Exception as e:
        logging.warning(
            "Не удалось отсортировать TS-сегменты по номеру, используем исходный порядок."
        )

    logging.info(f"Найдено {len(ts_urls)} TS-сегментов: {ts_urls}")
    downloaded_files = []
    os.makedirs(folder, exist_ok=True)
    for i, seg_url in enumerate(ts_urls, start=1):
        try:
            r = requests.get(seg_url, stream=True)
            if r.status_code == 200:
                filename = os.path.join(folder, f"segment_{i}.ts")
                with open(filename, "wb") as f:
                    f.write(r.content)
                logging.info(f"Сегмент {i} скачан: {filename}")
                downloaded_files.append(filename)
            else:
                logging.error(f"Ошибка скачивания сегмента {i}: статус {r.status_code}")
        except Exception as exc:
            logging.error(f"Ошибка при скачивании сегмента {i} с URL {seg_url}: {exc}")
    return downloaded_files


def merge_ts_segments(ts_files: list, folder: str) -> None:
    """
    Создает текстовый файл со списком TS-сегментов (в папке folder) и вызывает FFmpeg для объединения их
    в единый MP4. Имя итогового файла формируется по текущим дате и времени (формат dd.mm.yyyy hh;mm;ss).
    После успешного объединения удаляет TS-сегменты и segments.txt.
    """
    if not ts_files:
        logging.error("Нет TS-сегментов для объединения.")
        return

    segments_list_file = os.path.join(folder, "segments.txt")
    with open(segments_list_file, "w") as f:
        for ts in ts_files:
            # FFmpeg требует, чтобы путь был абсолютным и заключался в одинарные кавычки.
            f.write(f"file '{os.path.abspath(ts)}'\n")
    logging.info(f"Файл списка сегментов '{segments_list_file}' создан.")

    # Формируем имя видео по текущей дате и времени формата dd.mm.yyyy hh;mm;ss
    timestamp = datetime.now().strftime("%d.%m.%Y %H;%M;%S")
    output_file = os.path.join(folder, f"{timestamp}.mp4")
    cmd = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        segments_list_file,
        "-c",
        "copy",
        output_file,
    ]
    logging.info("Запускаем FFmpeg для объединения сегментов TS...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        logging.info(f"Видео успешно сохранено в {output_file}")
        # После успешного объединения удаляем TS-сегменты и segments.txt
        for ts in ts_files:
            try:
                os.remove(ts)
                logging.info(f"Удалён файл сегмента: {ts}")
            except Exception as e:
                logging.error(f"Не удалось удалить {ts}: {e}")
        try:
            os.remove(segments_list_file)
            logging.info(f"Удалён файл списка сегментов: {segments_list_file}")
        except Exception as e:
            logging.error(f"Не удалось удалить {segments_list_file}: {e}")
    else:
        logging.error("Ошибка при объединении сегментов.")
        logging.error(result.stderr.decode("utf-8"))


def process_video_download() -> None:
    """
    Основная функция, вызываемая при нажатии F4.
    Извлекает TS-сегменты из логов, скачивает их и объединяет в итоговое видео,
    которое сохраняется в папку с именем "название товара_артикль".
    """
    folder = get_output_folder(driver)
    logging.info("Начинается обработка TS-сегментов для формирования видео...")
    ts_files = download_ts_segments(driver, folder)
    if ts_files:
        merge_ts_segments(ts_files, folder)
    else:
        logging.error("Не удалось скачать ни одного TS-сегмента.")


def on_f4_pressed() -> None:
    logging.info("Нажата клавиша F4!")
    threading.Thread(target=process_video_download, daemon=True).start()


def main() -> None:
    print("Инструкция:")
    print(
        "1. Запустите браузер Chrome с опцией remote debugging (например, запустите: "
        'google-chrome --remote-debugging-port=9222 --user-data-dir="/some/unique/dir").'
    )
    print(
        "2. В браузере перейдите на страницу Wildberries с отзывами товара и выберите видео отзыв,"
    )
    print(
        "   дождитесь полной загрузки видео (полоска загрузки должна стать полностью серой)."
    )
    print(
        "3. После этого вернитесь в терминал и нажмите F4 для начала скачивания и объединения TS-сегментов."
    )
    print("\nОжидание нажатия клавиши F4...")

    logging.info(
        "Скрипт запущен. Ожидается нажатие клавиши F4 для скачивания и объединения TS-сегментов в видео."
    )
    keyboard.add_hotkey("F4", on_f4_pressed)
    keyboard.wait()


if __name__ == "__main__":
    main()
