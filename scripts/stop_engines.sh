#!/bin/bash

pkill -SIGINT -f "lichess-bot.py --config config_cpp.yml" && echo "Stopped C++ engine" || echo "C++ engine was not running"
pkill -SIGINT -f "lichess-bot.py --config config_python.yml" && echo "Stopped Python engine" || echo "Python engine was not running"
