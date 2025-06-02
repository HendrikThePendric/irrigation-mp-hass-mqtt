#!/bin/bash

pip install -r requirements.txt
pip install -U micropython-esp32-stubs --target typings --no-user --no-cache-dir
pip install -U micropython-rp2-stubs --target typings --no-user --no-cache-dir
