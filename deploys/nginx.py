"""Public probe paths from files/nginx/probes.yml.

blackbox_exporter stays on loopback. nginx publishes one path per probe.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import yaml
from pyinfra import host
from pyinfra.api import DeployError
from pyinfra.api.deploy import deploy
from pyinfra.facts.server import Command, Which
from pyinfra.operations import dnf, files, selinux, server, systemd
from pyinfra.operations.selinux import Boolean

from deploys.firewall import ensure_port
from target import BLACKBOX_LISTEN, NGINX_PORT

UPSTREAM = f"http://{BLACKBOX_LISTEN}"
PROXY_CONF = "/etc/nginx/conf.d/blackbox.conf"
PROBES_FILE = Path("files/nginx/probes.yml")

# Exact tcp port only. unreserved_port_t's 1024-32767 range also covers
# NGINX_PORT, and semanage port -m cannot retarget a range.
_PORT_TYPE = (
    "semanage port -l | awk -v p="
    + str(NGINX_PORT)
    + " '$2==\"tcp\" {for(i=3;i<=NF;i++){gsub(/,/,\"\",$i);"
    " if($i !~ /-/ && $i+0==p){print $1; exit}}}'"
)


@dataclass(frozen=True)
class Probe:
    module: str
    target: str
    path: str
    target_query: str


def load_probes(path: Path = PROBES_FILE) -> list[Probe]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list) or not data:
        raise DeployError(f"{path} must list at least one probe")

    probes: list[Probe] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise DeployError(f"{path} entries must be module/target mappings")
        module = item.get("module")
        target = item.get("target")
        if not isinstance(module, str) or not module.isidentifier():
            raise DeployError(f"invalid module in {path}: {module!r}")
        parsed = urlparse(target) if isinstance(target, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DeployError(f"invalid target in {path}: {target!r}")
        probe_path = "/" + parsed.hostname.replace(".", "")
        if probe_path in seen:
            raise DeployError(f"duplicate probe path {probe_path}")
        seen.add(probe_path)
        probes.append(
            Probe(
                module=module,
                target=target,
                path=probe_path,
                target_query=quote(target, safe=""),
            )
        )
    return probes


def _tcp_port_type() -> str:
    if not host.get_fact(Which, command="semanage"):
        return ""
    output = host.get_fact(Command, command=_PORT_TYPE)
    return (output or "").strip()


@deploy("nginx probe proxy")
def apply_nginx() -> None:
    dnf.packages(
        name="Ensure nginx and semanage",
        packages=["nginx", "policycoreutils-python-utils"],
    )

    if _tcp_port_type() != "http_port_t":
        server.shell(
            name=f"Label tcp/{NGINX_PORT} as http_port_t",
            commands=(
                "set -eu; "
                f"port_type=$({_PORT_TYPE}); "
                'if [ "$port_type" = http_port_t ]; then exit 0; fi; '
                'if [ -n "$port_type" ]; then '
                f"semanage port -m -t http_port_t -p tcp {NGINX_PORT}; "
                "else "
                f"semanage port -a -t http_port_t -p tcp {NGINX_PORT}; "
                "fi"
            ),
        )

    selinux.boolean(
        name="Allow nginx to connect to blackbox",
        bool_name="httpd_can_network_connect",
        value=Boolean.ON,
        persistent=True,
    )

    probes = load_probes()
    config = files.template(
        name="Install nginx probe paths",
        src="files/nginx/blackbox.conf.j2",
        dest=PROXY_CONF,
        mode="644",
        user="root",
        group="root",
        listen_port=NGINX_PORT,
        upstream=UPSTREAM,
        probes=probes,
    )
    server.shell(
        name="Validate nginx config",
        commands="nginx -t",
        _if=config.did_change,
    )

    systemd.service(
        name="Enable nginx",
        service="nginx.service",
        running=True,
        enabled=True,
        reloaded=config.will_change,
    )

    ensure_port(str(NGINX_PORT))

    for probe in probes:
        server.shell(
            name=f"Check {probe.path} probe route",
            commands=(
                "for _ in 1 2 3 4 5 6 7 8 9 10; do "
                f"if curl -fsS http://127.0.0.1:{NGINX_PORT}{probe.path} "
                "| grep probe_success >/dev/null; then exit 0; fi; "
                "sleep 1; "
                "done; "
                "exit 1"
            ),
        )
