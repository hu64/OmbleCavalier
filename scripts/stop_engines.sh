#!/bin/bash

pkill -f "lichess-bot.py --config config_cpp.yml" && echo "Stopped C++ engine" || echo "C++ engine was not running"
pkill -f "lichess-bot.py --config config_python.yml" && echo "Stopped Python engine" || echo "Python engine was not running"
