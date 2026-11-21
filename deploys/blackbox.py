"""Blackbox exporter state from docs/02-blackbox.md.

No ICMP probe. The process does not get CAP_NET_RAW.
"""

from pyinfra import host
from pyinfra.api.deploy import deploy
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, systemd

from target import BLACKBOX_LISTEN, BLACKBOX_SHA256, BLACKBOX_VERSION

ARCHIVE_NAME = f"blackbox_exporter-{BLACKBOX_VERSION}.linux-amd64.tar.gz"
ARCHIVE = f"/usr/local/src/{ARCHIVE_NAME}"
URL = (
    "https://github.com/prometheus/blackbox_exporter/releases/download/"
    f"v{BLACKBOX_VERSION}/{ARCHIVE_NAME}"
)
BINARY = "/usr/local/bin/blackbox_exporter"
CONFIG_DIR = "/etc/blackbox_exporter"
CONFIG = f"{CONFIG_DIR}/blackbox.yml"
UNIT = "/etc/systemd/system/blackbox_exporter.service"


def _binary_current() -> bool:
    info = host.get_fact(File, path=BINARY)
    if not isinstance(info, dict):
        return False
    version = host.get_fact(
        Command,
        command=f"{BINARY} --version 2>&1 || true",
    )
    return BLACKBOX_VERSION in (version or "")


@deploy("Blackbox exporter")
def apply_blackbox() -> None:
    files.directory(
        name="Ensure /usr/local/src exists",
        path="/usr/local/src",
        mode="755",
        user="root",
        group="root",
    )

    downloaded = files.download(
        name=f"Download blackbox exporter {BLACKBOX_VERSION}",
        src=URL,
        dest=ARCHIVE,
        sha256sum=BLACKBOX_SHA256,
        mode="644",
        user="root",
        group="root",
    )

    binary_current = _binary_current()
    install_binary = (not binary_current) or downloaded.will_change
    if install_binary:
        server.shell(
            name=f"Install blackbox_exporter {BLACKBOX_VERSION}",
            commands=(
                "set -eu; "
                "tmp=$(mktemp -d); "
                f'tar -xzf {ARCHIVE} -C "$tmp"; '
                "install -m 0755 "
                f'"$tmp/blackbox_exporter-{BLACKBOX_VERSION}.linux-amd64/blackbox_exporter" '
                f"{BINARY}; "
                'rm -rf "$tmp"; '
                f"restorecon {BINARY}"
            ),
        )
    elif binary_current:
        context = host.get_fact(
            Command,
            command=f"ls -Z {BINARY} 2>/dev/null || true",
        )
        if "bin_t" not in (context or ""):
            server.shell(
                name="Restore SELinux label on blackbox_exporter",
                commands=f"restorecon {BINARY}",
            )

    server.user(
        name="Ensure blackbox user",
        user="blackbox",
        system=True,
        shell="/sbin/nologin",
        home="/var/lib/blackbox",
        create_home=True,
        comment="Prometheus blackbox exporter",
        password_lock=True,
    )

    files.directory(
        name="Ensure blackbox config directory",
        path=CONFIG_DIR,
        mode="755",
        user="root",
        group="root",
    )
    config = files.put(
        name="Install blackbox.yml",
        src="files/blackbox/blackbox.yml",
        dest=CONFIG,
        mode="644",
        user="root",
        group="root",
    )
    unit = files.template(
        name="Install blackbox_exporter systemd unit",
        src="files/blackbox/blackbox_exporter.service.j2",
        dest=UNIT,
        mode="644",
        user="root",
        group="root",
        blackbox_listen=BLACKBOX_LISTEN,
    )

    systemd.service(
        name="Enable blackbox_exporter",
        service="blackbox_exporter.service",
        running=True,
        enabled=True,
        restarted=install_binary or config.will_change or unit.will_change,
        daemon_reload=unit.will_change,
    )

    server.shell(
        name="Check blackbox exporter health",
        commands=(
            "for _ in 1 2 3 4 5 6 7 8 9 10; do "
            f"curl -fsS http://{BLACKBOX_LISTEN}/-/healthy && exit 0; "
            "sleep 1; "
            "done; "
            "exit 1"
        ),
    )
