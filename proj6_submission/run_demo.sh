#!/bin/bash
# Runs the full automated demo (~4 min) and builds proj6_submission.zip. Run: bash run_demo.sh
cd "$(dirname "$0")"
[ -f ~/ryuenv/bin/activate ] && source ~/ryuenv/bin/activate
sudo mn -c >/dev/null 2>&1
rm -rf results alerts.log metrics.csv results.png
mkdir -p results
export PYTHONUNBUFFERED=1
ryu-manager monitor_app.py > results/ryu_output.txt 2>&1 &
RYU=$!
sleep 6
sudo /usr/bin/python3 demo.py 2>&1 | tee results/demo_timeline.txt
sleep 3
kill $RYU 2>/dev/null; wait $RYU 2>/dev/null
sudo mn -c >/dev/null 2>&1
/usr/bin/python3 plot.py
bash build_zip.sh
