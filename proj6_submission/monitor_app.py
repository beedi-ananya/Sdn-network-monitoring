# Ryu SDN controller + centralized UDP monitoring server (Project 6)
import json, time, socket, os
from collections import defaultdict, deque
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub

# ---------- abnormality thresholds ----------
LINK_CAP        = 10_000_000   # bps, matches bw=10 in topo.py
POLL            = 2            # seconds between SDN stats requests
UTIL_THRESH     = 0.70         # >70% link utilization -> alert
HOST_TIMEOUT    = 6            # seconds without telemetry -> host silent
LOSS_THRESH     = 0.10         # >10% telemetry packets lost (last LOSS_WINDOW s)
LOSS_WINDOW     = 20           # seconds
MISMATCH_THRESH = 0.50         # host-reported vs switch-observed rate differ >50%
MIN_RATE        = 200_000      # ignore mismatch below 200 kbps
UDP_PORT        = 9999


class Monitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mac_to_port = {}
        self.dps = {}
        self.prev_port = {}     # (dpid,port) -> (t, tx, rx)
        self.port_util = {}     # (dpid,port) -> utilization 0..1
        self.prev_flow = {}     # (dpid,src_mac) -> (t, bytes)
        self.dp_rate = {}       # (dpid,src_mac) -> bps seen by switch
        self.tele = {}          # host -> telemetry state
        self.active = set()
        self.mm_count = defaultdict(int)
        hub.spawn(self._telemetry_server)
        hub.spawn(self._telemetry_file_reader)
        hub.spawn(self._poll_loop)
        hub.spawn(self._report_loop)

    # ================= UDP telemetry server =================
    def _telemetry_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(('0.0.0.0', UDP_PORT))
        print('*** Monitoring server listening on UDP %d' % UDP_PORT, flush=True)
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except BlockingIOError:
                hub.sleep(0.05)
                continue
            try:
                m = json.loads(data.decode())
                h, seq = m['host'], m['seq']
            except Exception:
                continue
            t = self.tele.setdefault(h, {'events': deque(), 'last_seq': None,
                                         'tx_bps': 0, 'rx_bps': 0, 'last_seen': 0})
            lost = 0
            if t['last_seq'] is not None and seq > t['last_seq'] + 1:
                lost = seq - t['last_seq'] - 1
            t['last_seq'] = seq
            now = time.time()
            t['events'].append((now, lost))
            t['tx_bps'], t['rx_bps'], t['last_seen'] = m['tx_bps'], m['rx_bps'], now

    def _telemetry_file_reader(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'telemetry.jsonl')
        offset = 0
        while True:
            try:
                with open(path, 'r') as f:
                    f.seek(offset)
                    for line in f:
                        try:
                            m = json.loads(line)
                            h, seq = m['host'], m['seq']
                            t = self.tele.setdefault(h, {
                                'events': deque(), 'last_seq': None,
                                'tx_bps': 0, 'rx_bps': 0, 'last_seen': 0})
                            if seq <= (t['last_seq'] if t['last_seq'] is not None else -1):
                                continue
                            lost = 0
                            if t['last_seq'] is not None and seq > t['last_seq'] + 1:
                                lost = seq - t['last_seq'] - 1
                            t['last_seq'] = seq
                            now = time.time()
                            t['events'].append((now, lost))
                            t['tx_bps'], t['rx_bps'] = m['tx_bps'], m['rx_bps']
                            t['last_seen'] = now
                        except Exception:
                            continue
                    offset = f.tell()
            except FileNotFoundError:
                pass
            hub.sleep(0.2)

    def _loss(self, t):
        now = time.time()
        while t['events'] and now - t['events'][0][0] > LOSS_WINDOW:
            t['events'].popleft()
        recv = len(t['events'])
        lost = sum(e[1] for e in t['events'])
        return lost / (recv + lost) if (recv + lost) else 0.0

    # ================= switch handling (learning switch) =================
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _features(self, ev):
        dp = ev.msg.datapath
        ofp, p = dp.ofproto, dp.ofproto_parser
        self.dps[dp.id] = dp
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, p.OFPMatch(), actions)

    def _add_flow(self, dp, prio, match, actions):
        ofp, p = dp.ofproto, dp.ofproto_parser
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match, instructions=inst))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, p = dp.ofproto, dp.ofproto_parser
        in_port = msg.match['in_port']
        eth = packet.Packet(msg.data).get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == 0x88cc:
            return
        tbl = self.mac_to_port.setdefault(dp.id, {})
        tbl[eth.src] = in_port
        out = tbl.get(eth.dst, ofp.OFPP_FLOOD)
        actions = [p.OFPActionOutput(out)]
        if out != ofp.OFPP_FLOOD:
            self._add_flow(dp, 1, p.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src), actions)
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                   in_port=in_port, actions=actions, data=data))

    # ================= SDN statistics collection =================
    def _poll_loop(self):
        while True:
            for dp in list(self.dps.values()):
                p = dp.ofproto_parser
                dp.send_msg(p.OFPFlowStatsRequest(dp))
                dp.send_msg(p.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY))
            hub.sleep(POLL)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_reply(self, ev):
        dpid, now = ev.msg.datapath.id, time.time()
        for s in ev.msg.body:
            if s.port_no > 0xffffff00:       # skip LOCAL
                continue
            key = (dpid, s.port_no)
            if key in self.prev_port:
                pt, ptx, prx = self.prev_port[key]
                dt = now - pt
                if dt > 0:
                    bps = max(s.tx_bytes - ptx, s.rx_bytes - prx) * 8 / dt
                    self.port_util[key] = bps / LINK_CAP      # traffic utilization
            self.prev_port[key] = (now, s.tx_bytes, s.rx_bytes)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_reply(self, ev):
        dpid, now = ev.msg.datapath.id, time.time()
        totals = defaultdict(int)
        for f in ev.msg.body:
            src = f.match.get('eth_src')
            if src:
                totals[src] += f.byte_count
        for src, b in totals.items():
            key = (dpid, src)
            if key in self.prev_flow:
                pt, pb = self.prev_flow[key]
                if now - pt > 0 and b >= pb:
                    self.dp_rate[key] = (b - pb) * 8 / (now - pt)
            self.prev_flow[key] = (now, b)

    # ================= analysis + alerts =================
    def _alert(self, key, msg):
        if key in self.active:
            return
        self.active.add(key)
        line = '[%s] ALERT %s' % (time.strftime('%H:%M:%S'), msg)
        print('\033[91m' + line + '\033[0m', flush=True)
        with open('alerts.log', 'a') as f:
            f.write(line + '\n')

    def _clear(self, key):
        if key in self.active:
            self.active.discard(key)
            line = '[%s] CLEARED %s' % (time.strftime('%H:%M:%S'), ' '.join(str(x) for x in key))
            print('\033[92m' + line + '\033[0m', flush=True)
            with open('alerts.log', 'a') as f:
                f.write(line + '\n')

    def _host_flow_bps(self, mac):
        r = [v for (d, s), v in self.dp_rate.items() if s == mac]
        return max(r) if r else 0.0

    def _check(self):
        now = time.time()
        for (dpid, port), u in self.port_util.items():
            k = ('util', dpid, port)
            if u > UTIL_THRESH:
                self._alert(k, 'HIGH_UTILIZATION switch s%d port %d at %.0f%%' % (dpid, port, u * 100))
            else:
                self._clear(k)
        for h, t in self.tele.items():
            if now - t['last_seen'] > HOST_TIMEOUT:
                self._alert(('down', h), 'HOST_SILENT %s sent no telemetry for >%ds' % (h, HOST_TIMEOUT))
                continue
            self._clear(('down', h))
            loss = self._loss(t)
            if loss > LOSS_THRESH:
                self._alert(('loss', h), 'TELEMETRY_LOSS %s lost %.0f%% of telemetry packets' % (h, loss * 100))
            else:
                self._clear(('loss', h))
            mac = '00:00:00:00:00:%02x' % int(h[1:])
            tx, fr = t['tx_bps'], self._host_flow_bps(mac)
            big = max(tx, fr)
            if big > MIN_RATE and abs(tx - fr) / big > MISMATCH_THRESH:
                self.mm_count[h] += 1
            else:
                self.mm_count[h] = 0
                self._clear(('mm', h))
            if self.mm_count[h] >= 2:
                self._alert(('mm', h), 'HOST_FLOW_MISMATCH %s reports %.2f Mbps but switches see %.2f Mbps (possible drop/blackhole)'
                            % (h, tx / 1e6, fr / 1e6))

    # ================= presentation =================
    def _report_loop(self):
        while True:
            hub.sleep(POLL)
            self._check()
            ts = time.time()
            print('\n=== %s ===' % time.strftime('%H:%M:%S'), flush=True)
            print('%-5s%10s%10s%12s%10s' % ('HOST', 'TX Mbps', 'RX Mbps', 'FLOW Mbps', 'LOSS %'))
            with open('metrics.csv', 'a') as f:
                for h in sorted(self.tele):
                    t = self.tele[h]
                    fr = self._host_flow_bps('00:00:00:00:00:%02x' % int(h[1:]))
                    loss = 100.0 * self._loss(t)
                    print('%-5s%10.2f%10.2f%12.2f%10.1f' % (h, t['tx_bps'] / 1e6, t['rx_bps'] / 1e6, fr / 1e6, loss))
                    f.write('%f,host_tx_mbps,%s,%f\n' % (ts, h, t['tx_bps'] / 1e6))
                    f.write('%f,flow_mbps,%s,%f\n' % (ts, h, fr / 1e6))
                for (d, p), u in sorted(self.port_util.items()):
                    f.write('%f,link_util_pct,s%d:p%d,%f\n' % (ts, d, p, u * 100))
                    if u > 0.01:
                        print('  link s%d port %d utilization: %.1f%%' % (d, p, u * 100))
            print(flush=True)
