# Poet-s-assistant

Проект **Poet's Assistant** — это инструмент для генерации поэзии с использованием методов машинного обучения. Он включает в себя модели для обработки текста, определения ударений, классификации метра и генерации стихотворений. Проект также интегрирован с Telegram-ботом для удобного взаимодействия с пользователями.

## Оглавление
- [Как пользоваться ботом?](#как-пользоваться-ботом)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
- [Использование](#использование)
  - [Telegram-бот](#telegram-бот)
- [Зависимости](#зависимости)

## Как пользоваться ботом?
В телеграме найдите бота [@PoemGeneration_bot](https://web.telegram.org/a/#7937455086).
Нажмите кнопку Start, бот напишет приветственное сообщение со всей необходимой информацией.
Если бот не отвечает, значит, он выключен, тогда обратитесь к разработчикам (@mur_myauk) для запуска или же разверните его локально.

**Генерация стихотворения — долгий процесс, он может занять до 7 минут, не переживайте.**

## Структура проекта

```
poetrydict/
  bad_signature1.dat
  collocation_accents.dat
models/
  seeds.pkl
  stressed_long_poetry_generator_medium/
    archive/
    config.json
    pytorch_model.bin
    tokenizer_config.json
    vocab.txt
  udpipe_syntagrus.model
py/
  generative_poetry/
  arabize.py
  break_to_syllables.py
  init_logging.py
  long_poem_generator2.py
  metre_classifier.py
  poetry_alignment.py
  poetry_seeds.py
  stressed_gpt_tokenizer.py
  temp_gpt_poetry_generation.py
  udpipe_parser.py
  whitespace_normalization.py
  poetry/
    phonetic.py
  transcriptor_models/
    rusyllab.py
    stress_model.py
scripts/
  config_tg.json
  poetery_tg.sh
  poetry_bot.db
  requirements.txt
tmp/
  accents.pkl
stress_model/
  nn_stress.cfg
  nn_stress.model
  keras_metadata.pb
  saved_model.pb
  variables/
    variables.data-00000-of-00001
    variables.index

```

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/KsuZavyalova/Poet-s-assistant.git
   cd Poet-s-assistant
   ```

2. **Скачайте недостающие файлы:**
   - Некоторые файлы (например, `accents.pkl`, `udpipe_syntagrus.model`, `pytorch_model.bin` и папка `variables`) отсутствуют в GitHub из-за их большого размера.
   - Вы можете скачать их вручную с [Google Drive](https://drive.google.com/drive/u/1/folders/1pIXtKtZX5eP5VMYJ5UeVUIj7jiuK_zGV) и разместить в соответствующих папках проекта.
   - Или скачайте полный архив с диска, где все файлы уже распределены по папкам.

3. **Создайте виртуальное окружение и установите зависимости:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Для Linux/MacOS
   # или
   venv\Scripts\activate     # Для Windows
   pip install -r scripts/requirements.txt
   ```

4. **Проверьте структуру проекта:**
   - Убедитесь, что все файлы в папках корректно расположены.
   - Все файлы проекта должны храниться в одной директории.

3. **Создайте виртуальное окружение и установите зависимости:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Для Linux/MacOS
   # или
   venv\Scripts\activate     # Для Windows
   pip install -r scripts/requirements.txt
   ```

## Использование

### Telegram-бот
Для запуска Telegram-бота:
1. Отредактируйте файл `scripts/config_tg.json`, указав структуру вашего проекта.
2. Запустите скрипт poetery_tg.sh
3. Введите токен бота в консоли.
   Получить его можно у @BotFather используя команду /newbot.
   <img width="1255" alt="Снимок экрана 2025-03-22 в 10 24 47" src="https://github.com/user-attachments/assets/0a90e2a7-494e-4539-b059-3bb094f82511" />


## Зависимости
Основные зависимости перечислены в `scripts/requirements.txt`. Для работы проекта необходимы:
- Python 3.11.0 или выше
- PyTorch
- TensorFlow/Keras
- UDPipe
- Другие библиотеки, указанные в `requirements.txt`.

**Важно:** Если что-то не работает, возможно, у вас конфликт версий. Рекомендуется использовать версии библиотек, указанные в requirements.txt.
