Project 6 - Network Monitoring and Alert System (Mininet + Ryu SDN controller)

Files
  agent.py        UDP telemetry agent run on every host
  topo.py         Mininet topology (4 hosts, 2 switches, 10 Mbps links)
  monitor_app.py  Ryu controller + centralized UDP monitoring server
  demo.py         Automated scenarios A-E
  plot.py         Graph from metrics.csv
  setup.sh        One-time Ubuntu setup
  run_demo.sh     Runs everything and builds the submission zip
  run_manual.sh   Interactive mode (ryu / mininet)
Outputs: alerts.log, metrics.csv, results.png, results/, FINAL_REPORT.md, REPORT.docx

How to run:   bash setup.sh   (once)   then   bash run_demo.sh
