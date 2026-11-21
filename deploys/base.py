"""Base host state from docs/01-setup.md.

The one-time dnf update and reboot are not repeated. The workstation SSH
config is not applied here. Rich rules that were already on the host are
not managed.
"""

import subprocess

from pyinfra import host
from pyinfra.api import DeployError
from pyinfra.api.deploy import deploy
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import dnf, files, server

from deploys.firewall import ensure_drop_target, ensure_port
from target import ADMIN_UID, SSH_PORT, SSH_USER, SWAP_GIB

SWAPFILE = "/swapfile"
SWAP_BYTES = SWAP_GIB * 1024 * 1024 * 1024
FSTAB_LINE = "/swapfile none swap sw 0 0"


def _swapfile_ready() -> bool:
    info = host.get_fact(File, path=SWAPFILE)
    if not isinstance(info, dict):
        return False
    if int(info["size"]) != SWAP_BYTES or info["mode"] != 600:
        return False
    kind = host.get_fact(
        Command,
        command=f"blkid -o value -s TYPE {SWAPFILE} 2>/dev/null || true",
    )
    return (kind or "").strip() == "swap"


def _swap_active() -> bool:
    output = host.get_fact(
        Command,
        command=f"grep -q '^{SWAPFILE}' /proc/swaps && echo yes || echo no",
    )
    return (output or "").strip() == "yes"


def _yubikey_public_key() -> str:
    """Public half of the YubiKey, from the agent. No key file required."""

    try:
        result = subprocess.run(
            ["ssh-add", "-L"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DeployError("ssh-add is not installed") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise DeployError(f"ssh-add -L failed: {detail or 'agent has no keys'}")

    card_keys = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[-1].startswith("cardno:"):
            card_keys.append(line.strip())

    if len(card_keys) != 1:
        found = [line.split()[-1] for line in result.stdout.splitlines() if line.split()]
        raise DeployError(
            "Need exactly one agent key whose comment starts with cardno:. "
            f"Agent comments: {found or 'none'}"
        )
    return card_keys[0]


@deploy("Base system")
def apply_base() -> None:
    yubikey = _yubikey_public_key()

    dnf.packages(
        name="Ensure firewalld and curl are installed",
        packages=["firewalld", "curl"],
    )

    admin = server.user(
        name=f"Ensure {SSH_USER}",
        user=SSH_USER,
        uid=ADMIN_UID,
        groups=["wheel"],
        append=True,
        shell="/bin/bash",
        home=f"/home/{SSH_USER}",
        create_home=True,
        password_lock=True,
        public_keys=[yubikey],
        delete_keys=True,
    )

    ssh_context = host.get_fact(
        Command,
        command=(
            f"ls -Zd /home/{SSH_USER}/.ssh/authorized_keys 2>/dev/null || true"
        ),
    )
    if admin.will_change or "ssh_home_t" not in (ssh_context or ""):
        server.shell(
            name=f"Restore SELinux labels on {SSH_USER} .ssh",
            commands=f"restorecon -R /home/{SSH_USER}/.ssh",
        )

    sudoers = files.template(
        name=f"Install {SSH_USER} sudoers",
        src="files/sudoers/admin.j2",
        dest=f"/etc/sudoers.d/{SSH_USER}",
        mode="440",
        user="root",
        group="root",
        ssh_user=SSH_USER,
    )
    server.shell(
        name=f"Validate {SSH_USER} sudoers",
        commands=f"visudo -cf /etc/sudoers.d/{SSH_USER}",
        _if=sudoers.did_change,
    )

    lockdown = files.put(
        name="Install sshd lockdown",
        src="files/sshd/00-lockdown.conf",
        dest="/etc/ssh/sshd_config.d/00-lockdown.conf",
        mode="644",
        user="root",
        group="root",
    )
    server.shell(
        name="Validate and reload sshd",
        commands=(
            "restorecon /etc/ssh/sshd_config.d/00-lockdown.conf"
            " && sshd -t && systemctl reload sshd"
        ),
        _if=lockdown.did_change,
    )

    if not _swapfile_ready():
        server.shell(
            name=f"Create {SWAP_GIB}G /swapfile",
            commands=(
                "set -eu; "
                f"swapoff {SWAPFILE} 2>/dev/null || true; "
                f"fallocate -l {SWAP_GIB}G {SWAPFILE}; "
                f"chmod 600 {SWAPFILE}; "
                f"mkswap {SWAPFILE}; "
                f"swapon {SWAPFILE}"
            ),
        )
    elif not _swap_active():
        server.shell(
            name="Enable /swapfile",
            commands=f"swapon {SWAPFILE}",
        )

    fstab = files.line(
        name="Ensure /swapfile is in fstab",
        path="/etc/fstab",
        line=r"^/swapfile[[:space:]]",
        replace=FSTAB_LINE,
        present=True,
    )
    server.shell(
        name="Reload systemd after fstab change",
        commands="systemctl daemon-reload",
        _if=fstab.did_change,
    )

    ensure_drop_target()
    ensure_port(str(SSH_PORT))
