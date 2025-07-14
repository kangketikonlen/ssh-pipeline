#!/bin/bash

echo "+++++++++++++++++++ STARTING PIPELINES +++++++++++++++++++"

# Use 'python' and the new path from our modern Dockerfile
python /home/appuser/app.py
RET=$?

echo "++++++++++++++++++++ END PIPELINES +++++++++++++++++++++"

exit $RET
