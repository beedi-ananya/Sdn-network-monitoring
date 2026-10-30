#!/bin/bash
# One-time setup for Ubuntu with Mininet and Ryu
set -e

sudo apt update

sudo apt install -y \
    mininet \
    openvswitch-switch \
    iperf \
    iptables \
    python3-venv \
    python3-pip \
    python3-matplotlib \
    pandoc \
    software-properties-common

sudo systemctl enable --now openvswitch-switch

PY=python3

if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
    echo ">>> Python >= 3.11 detected; using Python 3.9 for Ryu."

    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install -y python3.9 python3.9-venv python3.9-distutils

    PY=python3.9
fi

echo ">>> Creating Ryu virtual environment"
rm -rf "$HOME/ryuenv"
"$PY" -m venv "$HOME/ryuenv"

source "$HOME/ryuenv/bin/activate"

echo ">>> Installing compatible packaging tools"
python -m pip install --upgrade "pip==20.3.4"
python -m pip install "setuptools==59.6.0" wheel

echo ">>> Installing Ryu dependencies"
python -m pip install "eventlet==0.30.2"
python -m pip install --no-build-isolation ryu

echo ">>> Checking Ryu installation"
ryu-manager --version

echo ">>> Testing Mininet"
sudo mn --test pingall
sudo mn -c

echo ">>> SETUP COMPLETE"
