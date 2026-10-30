#!/bin/bash
# Interactive mode for live demo / screenshots.
# Terminal 1: bash run_manual.sh ryu     Terminal 2: bash run_manual.sh mininet
cd "$(dirname "$0")"
if [ "$1" == "ryu" ]; then
  [ -f ~/ryuenv/bin/activate ] && source ~/ryuenv/bin/activate
  rm -f alerts.log metrics.csv
  PYTHONUNBUFFERED=1 ryu-manager monitor_app.py
else
  sudo mn -c
  sudo python3 topo.py
fi
