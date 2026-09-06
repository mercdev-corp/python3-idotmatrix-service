#!/usr/bin/env bash

# load environment variables
source .env

cd $CWD

source .venv/Scripts/activate
python app.py &
sleep 5

curl http://$HOST:$PORT/BLEconnect/$ADDRESS/$PIXELS
sleep 5

echo "\n\n"
read -p "Press Enter to close" </dev/tty
