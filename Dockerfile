FROM python:3.11-slim

# Add AMaster system user
RUN groupadd -g 993 amaster && \
    useradd -u 999 -g amaster -s /sbin/nologin -d /app amaster

# Environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install required tools (no git!)
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Add app
WORKDIR /app
COPY bot.py /app/AMaster.py

# Set permissions and switch user
RUN chown -R amaster:amaster /app
USER amaster

CMD ["python", "/app/AMaster.py"]
