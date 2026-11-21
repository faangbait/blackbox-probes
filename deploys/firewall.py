"""firewalld rules this repo owns. Pre-existing rich rules are left alone."""

from pyinfra import host
from pyinfra.facts.server import Command
from pyinfra.operations import server

ZONE = "public"


def _query(port: str, permanent: bool) -> str:
    flag = "--permanent " if permanent else ""
    output = host.get_fact(
        Command,
        command=(
            f"firewall-cmd {flag}--zone={ZONE} --query-port={port}/tcp || true"
        ),
    )
    return (output or "").strip()


def ensure_port(port: str) -> None:
    """Allow tcp/port from every source in the public zone."""

    permanent_open = _query(port, permanent=True) == "yes"
    runtime_open = _query(port, permanent=False) == "yes"
    if permanent_open and runtime_open:
        return

    commands = []
    if not permanent_open:
        commands.append(
            f"firewall-cmd --permanent --zone={ZONE} --add-port={port}/tcp"
        )
    commands.append("firewall-cmd --reload")
    server.shell(
        name=f"Allow {port}/tcp from every source",
        commands=" && ".join(commands),
    )


def ensure_drop_target() -> None:
    """public zone target is DROP, matching the host policy."""

    target = host.get_fact(
        Command,
        command=f"firewall-cmd --permanent --zone={ZONE} --get-target || true",
    )
    if (target or "").strip() == "DROP":
        return

    server.shell(
        name="Set firewalld public zone target to DROP",
        commands=(
            f"firewall-cmd --permanent --zone={ZONE} --set-target=DROP"
            " && firewall-cmd --reload"
        ),
    )
