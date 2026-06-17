#!/bin/sh

if [ -f /shared/id_ctf.pub ]; then
    cp /shared/id_ctf.pub /home/ctfuser/.ssh/authorized_keys
    chmod 600 /home/ctfuser/.ssh/authorized_keys
    chown ctfuser:ctfuser /home/ctfuser/.ssh/authorized_keys
fi

exec /usr/sbin/sshd -D