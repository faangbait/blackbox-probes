"""Target from target.py, reached with the workstation SSH config and agent."""

from target import HOST, SSH_HOSTNAME, SSH_PORT, SSH_USER

probes = [
    (
        HOST,
        {
            "ssh_hostname": SSH_HOSTNAME,
            "ssh_port": SSH_PORT,
            "ssh_user": SSH_USER,
            "_sudo": True,
        },
    ),
]
