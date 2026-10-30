#!/usr/bin/env python3
# UDP telemetry agent. Usage: python3 agent.py <hostname> <server_ip>
import socket, time, json, sys, os
name, server = os.environ.get("HOSTNAME_LABEL", "unknown"), sys.argv[1]
PORT, INTERVAL = 9999, 1.0

def counters():
    # /proc/net/dev is per network namespace, so each Mininet host sees only its own NIC
    for line in open('/proc/net/dev').readlines()[2:]:
        iface, data = line.split(':')
        if iface.strip() == 'lo':
            continue
        f = data.split()
        return int(f[8]), int(f[0])          # tx_bytes, rx_bytes
    return 0, 0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
seq = 0
ptx, prx = counters()
pt = time.time()
while True:
    time.sleep(INTERVAL)
    tx, rx = counters()
    now = time.time()
    dt = now - pt
    msg = {"host": name, "seq": seq, "ts": now,
           "tx_bps": (tx - ptx) * 8 / dt, "rx_bps": (rx - prx) * 8 / dt}
    try:
        sock.sendto(json.dumps(msg).encode(), (server, PORT))
    except OSError:
        pass
    seq += 1
    ptx, prx, pt = tx, rx, now
