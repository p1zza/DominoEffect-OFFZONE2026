FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Инвалидация кеша при необходимости
ARG CACHE_BUST=1

RUN mkdir -m 700 -p /root/.ssh /shared \
    && ssh-keygen -t ed25519 -f /shared/id_ctf -N "" \
    && cp /shared/id_ctf /root/.ssh/id_ctf \
    && cp /shared/id_ctf.pub /root/.ssh/id_ctf.pub \
    && chmod 600 /root/.ssh/id_ctf \
    && chmod 644 /root/.ssh/id_ctf.pub \
    && chmod 644 /shared/id_ctf.pub

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000
CMD ["python", "app.py"]