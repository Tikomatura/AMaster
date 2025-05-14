FROM python:3.11-slim

RUN apt-get update && apt-get install -y git ffmpeg && apt-get clean

WORKDIR /app

# Pre-install dependencies to avoid runtime install issues
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

CMD ["/startup.sh"]
