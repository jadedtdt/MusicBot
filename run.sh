#!/bin/bash
#sudo docker system prune -a -f
#sudo bash build_docker_image.sh
export AWS_ACCESS_KEY_ID=$(aws --profile default configure get aws_access_key_id)
export AWS_SECRET_ACCESS_KEY=$(aws --profile default configure get aws_secret_access_key)
export AWS_DEFAULT_REGION=$(aws --profile default configure get region)
python3.6 run.py

