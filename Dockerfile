FROM python:3.7-stretch

COPY requirements.txt /

COPY . app/
WORKDIR /app

RUN apt-get update && apt-get install -y \
	python-dev \
	default-libmysqlclient-dev \
	libopus0 \
	ffmpeg
RUN python3 -m pip install -r requirements.txt

CMD python3 run.py
