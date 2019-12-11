sudo apt-get update
sudo apt-get remove -y docker docker-engine docker.io
sudo apt install -y docker.io awscli
sudo systemctl start docker
sudo systemctl enable docker
