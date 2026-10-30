#!/usr/bin/env python3
import socket
from pathlib import Path

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("10.0.0.254", 9999))
path = Path(__file__).resolve().parent / "telemetry.jsonl"

print("Telemetry file receiver running on 10.0.0.254:9999", flush=True)

while True:
    data, addr = sock.recvfrom(2048)
    with path.open("a") as f:
        f.write(data.decode() + "\n")
