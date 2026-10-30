#!/usr/bin/env python3
# Automated demo: runs scenarios A-E against the monitor. Run with sudo.
import time
from topo import build, start_agent

def say(msg):
    print('[DEMO %s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)

net = build()
h1, h2, h3, h4 = [net.get('h%d' % i) for i in range(1, 5)]
s1 = net.get('s1')
agents = {h.name: start_agent(h) for h in net.hosts if h.name != 'monitor'}
say('Agents started; waiting for telemetry to stabilise')
time.sleep(10)

say('SCENARIO A: normal traffic (1 Mbps h1->h4) - expect NO alert')
h4.cmd('iperf -u -s -p 5001 > /dev/null 2>&1 &')
h1.cmd('iperf -u -c 10.0.0.4 -p 5001 -b 1M -t 12 > /dev/null 2>&1 &')
time.sleep(18)

say('SCENARIO B: congestion (9 Mbps on 10 Mbps links) - expect HIGH_UTILIZATION')
h1.cmd('iperf -u -c 10.0.0.4 -p 5001 -b 9M -t 14 > /dev/null 2>&1 &')
time.sleep(22)

say('SCENARIO C: host h3 agent killed - expect HOST_SILENT after ~6s')
agents['h3'].terminate()
time.sleep(14)
say('SCENARIO C: h3 agent restarted - alert clears')
agents['h3'] = start_agent(h3)
time.sleep(10)

say('SCENARIO D: 80%% of h2 telemetry dropped - expect TELEMETRY_LOSS')
h2.cmd('iptables -A OUTPUT -p udp --dport 9999 -m statistic --mode random --probability 0.8 -j DROP')
time.sleep(25)
h2.cmd('iptables -F')
say('SCENARIO D: telemetry loss removed')
time.sleep(25)

say('SCENARIO E: blackhole h1->h4 at s1 while h1 sends 5 Mbps - expect HOST_FLOW_MISMATCH')
h1.cmd('iperf -u -c 10.0.0.4 -p 5001 -b 5M -t 45 > /dev/null 2>&1 &')
time.sleep(10)
s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.4,actions=drop"')
say('SCENARIO E: drop rule installed on s1')
time.sleep(18)
s1.cmd('ovs-ofctl --strict -O OpenFlow13 del-flows s1 "priority=100,ip,nw_src=10.0.0.1,nw_dst=10.0.0.4"')
say('SCENARIO E: drop rule removed')
time.sleep(20)

say('DEMO FINISHED')
for a in agents.values():
    a.terminate()
net.stop()
