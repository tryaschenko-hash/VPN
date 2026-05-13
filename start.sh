#!/bin/bash
# Render start script - download xray-core and run with config
set -e

if [ ! -f xray ]; then
    curl -L -o xray.zip "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
    unzip -o xray.zip && rm -f xray.zip
    chmod +x xray
fi

PORT=${PORT:-10000}
sed -i "s/10000/$PORT/" xray-config.json

exec ./xray run -c xray-config.json
