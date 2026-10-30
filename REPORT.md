---
title: "Project 6: Network Monitoring and Alert System"
subtitle: "SDN (Ryu) + Mininet + UDP telemetry"
---

## 1. Objective

Build a distributed network-monitoring system in which hosts transmit telemetry over UDP sockets and an SDN controller combines that telemetry with OpenFlow flow/port statistics to detect abnormal conditions and raise alerts.

## 2. Topology and architecture

```
 h1 (10.0.0.1) --\                         /-- h3 (10.0.0.3)
                  s1 ======10 Mbps====== s2
 h2 (10.0.0.2) --/   |                     \-- h4 (10.0.0.4)
                     |
      root namespace 10.0.0.254
      Ryu controller + UDP monitoring server (port 9999)
```

All links are 10 Mbps (Mininet `TCLink`), so utilization = bits per second / 10,000,000. Switches are Open vSwitch speaking OpenFlow 1.3 to a Ryu remote controller.

**Data paths.** (1) Each host agent sends one JSON UDP packet per second (host, sequence number, tx/rx bit rate read from its own NIC counters) to the monitoring server. (2) Every 2 s the controller requests flow and port statistics from both switches. (3) The controller correlates both sources every 2 s.

## 3. Requirement-to-implementation mapping

| Requirement | Implementation |
|---|---|
| Implement UDP telemetry agents | `agent.py` (UDP socket, 1 packet/s per host) |
| Develop a centralized monitoring server | `_telemetry_server()` in `monitor_app.py` |
| Collect SDN flow statistics | `_poll_loop()`, `_flow_reply()`, `_port_reply()` (OFPFlowStats / OFPPortStats) |
| Calculate traffic utilization | `port_util` = (byte delta x 8 / interval) / link capacity |
| Define abnormality thresholds | Constants at the top of `monitor_app.py` (section 4) |
| Generate alerts | `_alert()` prints to console and writes `alerts.log` |
| Monitor multiple network nodes | 4 hosts + 2 switches monitored simultaneously |
| Present monitoring results | Console dashboard, `metrics.csv`, `results.png` |

## 4. Thresholds and reasoning

| Alert | Condition | Reasoning |
|---|---|---|
| HIGH_UTILIZATION | link utilization > 70% | Above ~70% queues build up and latency/loss increase |
| HOST_SILENT | no telemetry for 6 s | 6 missed 1 s reports means the host or its agent is down, not just jitter |
| TELEMETRY_LOSS | > 10% sequence-number gaps in last 20 s | Sequence numbers reveal lost UDP packets; 10% separates real loss from noise |
| HOST_FLOW_MISMATCH | host-reported rate and switch-observed rate differ by > 50% (and above 200 kbps) for 2 consecutive polls | Host says it sends traffic that the switches never see: blackhole or silent drop |

## 5. Test scenarios

| Scenario | Action | Expected alert |
|---|---|---|
| A | 1 Mbps UDP flow h1 to h4 | none (normal) |
| B | 9 Mbps UDP flow h1 to h4 | HIGH_UTILIZATION |
| C | Kill h3's agent, then restart it | HOST_SILENT, then cleared |
| D | Drop 80% of h2's telemetry packets with iptables | TELEMETRY_LOSS, then cleared |
| E | h1 sends 5 Mbps; drop rule installed on s1 | HOST_FLOW_MISMATCH |

Short transient mismatch alerts at the start/end of an iperf run are expected because the host (1 s) and controller (2 s) sampling windows are not aligned.
