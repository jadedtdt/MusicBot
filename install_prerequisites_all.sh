#!/bin/bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.6 python3.6-dev python3 python3-dev python3-pip build-essential libmysqlclient-dev libopus0 ffmpeg awscli libssl-dev libffi-dev
python3.6 -m pip install -r requirements.txt

