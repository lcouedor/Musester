# start.sh
#!/bin/bash

cd "$(dirname "$0")/api"
myenv/bin/python3.13 app.py