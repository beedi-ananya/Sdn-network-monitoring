import csv, collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

data = collections.defaultdict(lambda: collections.defaultdict(lambda: ([], [])))
rows = list(csv.reader(open('metrics.csv')))
t0 = float(rows[0][0])
for ts, kind, name, val in rows:
    x, y = data[kind][name]
    x.append(float(ts) - t0); y.append(float(val))

fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
for n, (x, y) in sorted(data['host_tx_mbps'].items()): ax[0].plot(x, y, label=n)
for n, (x, y) in sorted(data['flow_mbps'].items()): ax[1].plot(x, y, label=n)
for n, (x, y) in sorted(data['link_util_pct'].items()):
    if max(y) > 5: ax[2].plot(x, y, label=n)
ax[2].axhline(70, color='r', ls='--', label='70% threshold')
ax[0].set_ylabel('Host-reported TX (Mbps)\n(UDP telemetry)')
ax[1].set_ylabel('Switch-observed rate (Mbps)\n(SDN flow stats)')
ax[2].set_ylabel('Link utilization (%)')
ax[2].set_xlabel('time (s)')
ax[0].set_title('Network monitoring: telemetry vs SDN statistics')
for a in ax: a.legend(loc='upper right', fontsize=8); a.grid(alpha=.3)
plt.tight_layout(); plt.savefig('results.png', dpi=130)
print('saved results.png')
