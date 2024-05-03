#!/bin/bash

export WYZE_ACCESS_TOKEN="your_access_token_here"

cd ..
cd src/sync-locks/

pip3 install -r requirements.txt --upgrade --force-reinstall

cd sync-locks-function/

# Run the Python script
#python3 ./timer_function.py

