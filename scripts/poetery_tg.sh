#!/bin/bash
# Путь к конфигурационному файлу
CONFIG_FILE="config_tg.json"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Ошибка: Конфигурационный файл $CONFIG_FILE не найден."
  exit 1
fi

PYTHONPATH=$(jq -r '.pythonpath' "$CONFIG_FILE")
PYTHON_SCRIPT=$(jq -r '.python_script' "$CONFIG_FILE")
LOG_PATH=$(jq -r '.log_path' "$CONFIG_FILE")
MODELS_DIR=$(jq -r '.models_dir' "$CONFIG_FILE")
TMP_DIR=$(jq -r '.tmp_dir' "$CONFIG_FILE")
DATA_DIR=$(jq -r '.data_dir' "$CONFIG_FILE")

export PYTHONPATH="$PYTHONPATH"

python3 "$PYTHON_SCRIPT" \
  --mode telegram \
  --log "$LOG_PATH" \
  --models_dir "$MODELS_DIR" \
  --tmp_dir "$TMP_DIR" \
  --data_dir "$DATA_DIR"
