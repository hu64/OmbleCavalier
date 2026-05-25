#!/bin/bash
set -e

cd "$(dirname "$0")/.."

nohup .venv/bin/python lichess-bot.py --config config_cpp.yml > lichess_bot_auto_logs/cpp_engine.log 2>&1 &
echo "Started C++ engine (PID $!)"

nohup .venv/bin/python lichess-bot.py --config config_python.yml > lichess_bot_auto_logs/python_engine.log 2>&1 &
echo "Started Python engine (PID $!)"
