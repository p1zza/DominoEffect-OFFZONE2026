FROM alpine:3.19

RUN apk add --no-cache openssh-server sqlite bash\
    && ssh-keygen -A \
    && mkdir -p /var/run/sshd /data /secrets /home/ctfuser

ARG SSH_PASSWORD=SuperSecret123
RUN adduser -D -s /bin/bash ctfuser \
    && echo "ctfuser:${SSH_PASSWORD}" | chpasswd

# Включаем парольный вход на всякий случай
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Создаём .ssh
RUN mkdir -p /home/ctfuser/.ssh \
    && chmod 700 /home/ctfuser/.ssh \
    && chown ctfuser:ctfuser /home/ctfuser/.ssh

# authorized_keys будет создан при старте через entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN sqlite3 /data/ctf.db "CREATE TABLE flags (id INTEGER PRIMARY KEY, flag TEXT); INSERT INTO flags (flag) VALUES ('ctf{ssh_pivot_to_database}');" \
    && chmod 644 /data/ctf.db

RUN echo "ctf{filesystem_flag_hidden_here}" > /data/.hidden_flag \
    && chmod 600 /data/.hidden_flag \
    && chown ctfuser:ctfuser /data/.hidden_flag

RUN echo "DB_PATH=/data/ctf.db" > /secrets/db.conf \
    && chmod 644 /secrets/db.conf

EXPOSE 22
CMD ["/entrypoint.sh"]