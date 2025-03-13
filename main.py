import os
import sys
import json
import re
import subprocess
import threading
import requests
import keyboard
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import colorlog

# Настраиваем логирование с цветами с помощью colorlog
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
        datefmt=None,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)
logger = colorlog.getLogger()
logger.addHandler(handler)
logger.setLevel("INFO")


def get_output_folder(driver) -> str:
    """
    Извлекает артикль из URL по шаблону /catalog/<артикль>/feedbacks.
    Возвращает строку с именем папки, равную артиклю.
    """
    current_url = driver.current_url
    article_match = re.search(r"/catalog/(\d+)/feedbacks", current_url)
    if article_match:
        article = article_match.group(1)
    else:
        article = "unknown_article"

    logger.info(f"Определено название папки: {article}")
    return article


def download_ts_segments(driver, folder: str) -> list:
    """
    Извлекает логи производительности (network) из Selenium,
    находит TS-сегменты, скачивает их в папку folder и возвращает список путей к файлам.
    """
    logger.info("Извлекаем сетевые логи для поиска TS-сегментов...")
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
        logger.info("TS-сегменты не найдены в логах.")
        return []

    try:
        ts_urls = sorted(ts_urls, key=lambda url: int(url.rstrip(".ts").split("/")[-1]))
    except Exception as e:
        logger.warning(
            "Не удалось отсортировать TS-сегменты по номеру, используем исходный порядок."
        )

    logger.info(f"Найдено {len(ts_urls)} TS-сегментов: {ts_urls}")
    downloaded_files = []
    os.makedirs(folder, exist_ok=True)
    for i, seg_url in enumerate(ts_urls, start=1):
        try:
            r = requests.get(seg_url, stream=True)
            if r.status_code == 200:
                filename = os.path.join(folder, f"segment_{i}.ts")
                with open(filename, "wb") as f:
                    f.write(r.content)
                logger.info(f"Сегмент {i} скачан: {filename}")
                downloaded_files.append(filename)
            else:
                logger.error(f"Ошибка скачивания сегмента {i}: статус {r.status_code}")
        except Exception as exc:
            logger.error(f"Ошибка при скачивании сегмента {i} с URL {seg_url}: {exc}")
    return downloaded_files


def merge_ts_segments(ts_files: list, folder: str) -> None:
    """
    Создает текстовый файл со списком TS-сегментов (в папке folder) и вызывает FFmpeg для объединения их
    в единый MP4. Имя итогового файла формируется по текущим дате и времени (формат dd.mm.yyyy hh;mm;ss).
    После успешного объединения удаляет TS-сегменты и segments.txt.
    """
    if not ts_files:
        logger.error("Нет TS-сегментов для объединения.")
        return

    segments_list_file = os.path.join(folder, "segments.txt")
    with open(segments_list_file, "w") as f:
        for ts in ts_files:
            f.write(f"file '{os.path.abspath(ts)}'\n")
    logger.info(f"Файл списка сегментов '{segments_list_file}' создан.")

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
    logger.info("Запускаем FFmpeg для объединения сегментов TS...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        logger.info(f"Видео успешно сохранено в {output_file}")
        for ts in ts_files:
            try:
                os.remove(ts)
                logger.info(f"Удалён файл сегмента: {ts}")
            except Exception as e:
                logger.error(f"Не удалось удалить {ts}: {e}")
        try:
            os.remove(segments_list_file)
            logger.info(f"Удалён файл списка сегментов: {segments_list_file}")
        except Exception as e:
            logger.error(f"Не удалось удалить {segments_list_file}: {e}")
    else:
        logger.error("Ошибка при объединении сегментов.")
        logger.error(result.stderr.decode("utf-8"))


def process_video_download() -> None:
    """
    Основная функция, вызываемая при нажатии F4.
    Извлекает TS-сегменты из логов, скачивает их и объединяет в итоговое видео,
    которое сохраняется в папку с артиклем в качестве имени.
    """
    global driver
    folder = get_output_folder(driver)
    logger.info("Начинается обработка TS-сегментов для формирования видео...")
    ts_files = download_ts_segments(driver, folder)
    if ts_files:
        merge_ts_segments(ts_files, folder)
    else:
        logger.error("Не удалось скачать ни одного TS-сегмента.")


def on_f4_pressed() -> None:
    logger.info("Нажата клавиша F4!")
    threading.Thread(target=process_video_download, daemon=True).start()


def main() -> None:
    global driver

    # Подключаемся к запущенному браузеру Chrome через remote debugging
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    try:
        driver = webdriver.Chrome(options=chrome_options)
        logger.info(
            "Подключились к запущенному браузеру Chrome через remote debugging."
        )
    except Exception as exc:
        logger.error(f"Ошибка подключения к запущенному Chrome: {exc}")
        sys.exit(1)

    print("Инструкция:")
    print("1. Запустите браузер Chrome с опцией remote debugging.")
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

    logger.info(
        "Скрипт запущен. Ожидается нажатие клавиши F4 для скачивания и объединения TS-сегментов в видео."
    )
    keyboard.add_hotkey("F4", on_f4_pressed)
    keyboard.wait()


if __name__ == "__main__":
    main()
