FROM python:3.11-slim

# Set environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install required tools
RUN apt-get update && \
    apt-get install -y git ffmpeg curl && \
    pip install --no-cache-dir --upgrade pip

# Install Python requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Prepare app folder
WORKDIR /app
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

CMD ["/app/startup.sh"]
