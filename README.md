# О проекте

Этот скрипт предназначен для автоматизации процесса загрузки и объединения TS-сегментов видео с сайта Wildberries. Скрипт использует Selenium для подключения к запущенному Chrome через удалённую отладку, извлекает сетевые логи для поиска TS-сегментов, загружает их и объединяет в итоговое MP4-видео с помощью FFmpeg.

## Как работает скрипт

0. **Запустите хром в режиме дебагинг:**
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/unique_chrome_profile"
   ```

1. **Подключение к Chrome через remote debugging:**  
   Скрипт запускает Selenium с настройками для подключения к уже запущенному браузеру Chrome, запущенному с включенной опцией remote debugging (порт 9222).

2. **Извлечение данных о товаре:**  
   Функция `get_output_folder` извлекает название товара и артикул с текущей страницы для формирования имени папки, куда будут сохранены загруженные сегменты и итоговое видео.

3. **Поиск TS-сегментов:**  
   Скрипт анализирует сетевые логи, полученные через Selenium, и ищет ответы с URL, содержащими расширение `.ts`. Найденные ссылки сортируются по номеру сегмента.

4. **Скачивание сегментов:**  
   Функция `download_ts_segments` скачивает каждый TS-файл в созданную ранее папку.

5. **Объединение сегментов:**  
   Функция `merge_ts_segments` создаёт текстовый файл со списком сегментов и вызывает FFmpeg для объединения их в одно видео. После успешного объединения скрипт удаляет исходные TS-файлы и список сегментов.

6. **Обработка нажатия клавиши F4:**  
   Обработчик `on_f4_pressed` запускает процесс скачивания и объединения в отдельном потоке, что позволяет не блокировать основной поток выполнения.

## Как работать со скриптом

1. **Запуск браузера с удалённой отладкой:**  
   Убедитесь, что у вас установлен Google Chrome. Запустите его с опцией remote debugging, например:
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir="/some/unique/dir"
   ```
2. **Установите зависимости:**
   ```bash
   python -m venv env
   source env/bin/activate
   pip install -r requirements.txt
3. **Запуск скрипта:**  
   Запустите скрипт:
   ```bash
   python main.py
   ```
   В консоли появится инструкция с дальнейшими шагами.

4. **Выбор видео отзыва на сайте Wildberries:**  
   Перейдите в браузере на страницу с отзывами товара и выберите видео отзыв. Дождитесь полной загрузки видео (полоска загрузки должна стать полностью серой).

5. **Нажатие клавиши F4:**  
   Вернувшись в терминал, нажмите клавишу F4 для начала загрузки и объединения TS-сегментов.

6. **Результат:**  
   Итоговое видео в формате MP4 будет сохранено в папке с именем, сформированным по товару и его артиклю.

## Зависимости

- Python 3.12+
- Скачанный и установленный [Google Chrome](https://www.google.com/chrome/)
- [FFmpeg](https://ffmpeg.org/) для объединения TS-сегментов.

> **Важно:** На Linux библиотеке `keyboard` требуются права суперпользователя для работы с глобальными горячими клавишами. Если возникают ошибки, запустите скрипт от имени root или настройте соответствующие разрешения. Я использую команду ```sudo -E <путь до python в вашем venv> main.py```
