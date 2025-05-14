FROM python:3.11-slim

# Add AMaster system user (UID 999, GID 993 matches Navidrome)
RUN groupadd -g 993 amaster && \
    useradd -u 999 -g amaster -s /sbin/nologin -d /app amaster

# Set environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install required tools & clean up APT
RUN apt-get update && \
    apt-get install -y git ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip

# Copy and install Python requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Prepare application
WORKDIR /app
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

# Set permissions and switch to non-root user
RUN chown -R amaster:amaster /app
USER amaster

# Run the bot
CMD ["/app/startup.sh"]
