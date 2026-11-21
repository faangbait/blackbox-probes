# 02: Blackbox exporter

`deploys/blackbox.py` installs Prometheus blackbox exporter and keeps it on loopback. Public probe paths are nginx's job, in [03-nginx-proxy.md](03-nginx-proxy.md).

## Install

EL9 AppStream, BaseOS, and EPEL have no blackbox exporter package, so the deploy downloads a pinned upstream build and checks its sha256. The archive is `linux-amd64`, so the host is x86_64.

| | |
|---|---|
| **Version** | `BLACKBOX_VERSION` (`0.29.1`) |
| **Archive** | `blackbox_exporter-<BLACKBOX_VERSION>.linux-amd64.tar.gz` |
| **sha256** | `BLACKBOX_SHA256` |
| **Install** | `/usr/local/bin/blackbox_exporter` |

`BLACKBOX_VERSION` and `BLACKBOX_SHA256` live in [target.py](../target.py). The hash is the `linux-amd64` line from that release's `sha256sums.txt`. Change both, then `make deploy`.

The tarball lands in `/usr/local/src`. The binary is installed to `/usr/local/bin` and `restorecon` labels it. The service account is `blackbox`: a locked system user, shell `/sbin/nologin`, home `/var/lib/blackbox`.

## Listen

The unit is [files/blackbox/blackbox_exporter.service.j2](../files/blackbox/blackbox_exporter.service.j2). It listens on `BLACKBOX_LISTEN` from [target.py](../target.py) (`127.0.0.1:9116`).

`GET /probe?target=` will probe any URL it is handed. A public listener would be an open prober, so the process stays on loopback and nginx is the only path in from outside.

Config is [files/blackbox/blackbox.yml](../files/blackbox/blackbox.yml), installed at `/etc/blackbox_exporter/blackbox.yml`. This file defines modules. The URLs to check live in `files/nginx/probes.yml`.

The HTTP modules prefer IPv4, follow redirects, and fall back to the other address family. `https_2xx` also fails the probe unless the target speaks TLS.

| Module | What it checks |
|---|---|
| `http_2xx` | HTTP status 2xx |
| `https_2xx` | HTTP status 2xx over TLS |
| `tcp_connect` | A TCP connection |
| `ssh_banner` | A TCP connection whose banner matches `SSH-2.0-` |

ICMP is left out. An ICMP probe needs `CAP_NET_RAW`, and the unit sets `NoNewPrivileges` with no extra capabilities.

## Check

The deploy enables `blackbox_exporter.service`. It restarts the service when the binary, the config, or the unit changes, and reloads systemd when the unit file changes. It then curls `http://<BLACKBOX_LISTEN>/-/healthy` and fails the run if that does not succeed.
