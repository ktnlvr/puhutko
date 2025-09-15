#!/usr/bin/env bash

curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
poetry install --no-root --only main
