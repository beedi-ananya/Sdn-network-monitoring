import csv
import collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

data = collections.defaultdict(lambda: collections.defaultdict(lambda: ([], [])))

with open('metrics.csv', newline='') as f:
    rows = list(csv.reader(f))

if not rows:
    raise SystemExit("metrics.csv is empty")

latest = max(float(r[0]) for r in rows if len(r) == 4)
start = latest - 120

for row in rows:
    if len(row) != 4:
        continue
    ts, kind, name, val = row
    ts, val = float(ts), float(val)
    if ts < start:
        continue
    x, y = data[kind][name]
    x.append(ts - start)
    y.append(val)

fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

for n, (x, y) in sorted(data['host_tx_mbps'].items()):
    ax[0].plot(x, y, label=n)

for n, (x, y) in sorted(data['flow_mbps'].items()):
    ax[1].plot(x, y, label=n)

for n, (x, y) in sorted(data['link_util_pct'].items()):
    if y:
        ax[2].plot(x, y, label=n)

ax[2].axhline(70, color='r', ls='--', label='70% threshold')
ax[0].set_ylabel('Host TX (Mbps)\n(UDP telemetry)')
ax[1].set_ylabel('Flow rate (Mbps)\n(SDN flow stats)')
ax[2].set_ylabel('Link utilization (%)')
ax[2].set_xlabel('Time in latest 120 seconds')
ax[0].set_title('Network Monitoring: Telemetry vs SDN Statistics')

for a in ax:
    a.legend(loc='upper right', fontsize=8)
    a.grid(alpha=0.3)

ax[2].set_ylim(bottom=0)
ax[2].set_xlim(0, 120)

plt.tight_layout()
plt.savefig('results.png', dpi=150)
print('Saved results.png using the latest 120 seconds of data')
