#!/bin/bash

export PYTHONPATH=/Users/kseniazavyalova/PycharmProjects/poetry_generator/py

python3 /Users/kseniazavyalova/PycharmProjects/poetry_generator/py/generative_poetry/temp_gpt_poetry_generation.py \
  --mode telegram \
  --log /Users/kseniazavyalova/PycharmProjects/poetry_generator/tmp/verslibre_tg.log \
  --models_dir /Users/kseniazavyalova/PycharmProjects/poetry_generator/models \
  --tmp_dir /Users/kseniazavyalova/PycharmProjects/poetry_generator/tmp \
  --data_dir /Users/kseniazavyalova/PycharmProjects/poetry_generator/data