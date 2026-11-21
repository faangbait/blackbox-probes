# blackbox probes

Put a Prometheus blackbox exporter on an AlmaLinux 9 VM and publish one fixed HTTP path per probe.

You run this from a workstation. `make deploy` SSHs to the VM and applies the host. Prometheus config stays in your Prometheus, not in this repo.

## Before you run it

On the workstation:

- [uv](https://docs.astral.sh/uv/) is installed. The first `uv run` builds `.venv` from `uv.lock`.
- Python 3.14 is available to uv. `.python-version` pins 3.14.8.
> _This is probably the first thing you'll want to change. Feel free to fork._
- `ssh-add -L` lists exactly one key whose comment starts with `cardno:`. The deploy writes that line as the admin user's only authorized key. Put no key file in this repo. 

On the VM, before the first deploy:

- AlmaLinux 9, x86_64, SELinux enforcing. Any RHEL-based system should work.
- sshd is already listening on the port you set as `SSH_PORT`. The deploy opens that port in firewalld. It does not change sshd's listen port.
- The user in `SSH_USER` can already log in and sudo. pyinfra connects as that user. It then sets uid `ADMIN_UID`, group `wheel`, a locked password, and passwordless sudo.
- Run `dnf update` and reboot if you want the latest updates. We don't do that for you.

`make deploy` runs `deploys/base.py` every time. Comment out `apply_base()` in `deploy.py` to leave the admin user, sshd, swap, and firewalld alone. The blackbox and nginx steps still run.

## Configure

Edit [target.py](target.py):

| | |
|---|---|
| **HOST** | Name in `~/.ssh/config`, and the pyinfra host name |
| **SSH_HOSTNAME** | Address pyinfra connects to |
| **SSH_PORT** | Port pyinfra connects to, and the port firewalld allows |
| **SSH_USER** | Admin user pyinfra logs in as |
| **ADMIN_UID** | uid of that user |
| **SWAP_GIB** | Swapfile size in gibibytes |
| **BLACKBOX_VERSION** | Pinned `blackbox_exporter` release |
| **BLACKBOX_SHA256** | sha256 of the `linux-amd64` archive |
| **BLACKBOX_LISTEN** | Loopback address the exporter binds |
| **NGINX_PORT** | Public nginx port |

The committed SSH values are placeholders: `probe`, `203.0.113.10`, `2223`, `ec2-user`.

Match them in `~/.ssh/config`.

```
Host probe
  HostName 203.0.113.10
  Port 2223
  User ec2-user
```

Check the login:

```
ssh probe
```

Edit [files/nginx/probes.yml](files/nginx/probes.yml). One entry per site. `module` is a name from [files/blackbox/blackbox.yml](files/blackbox/blackbox.yml): `http_2xx`, `https_2xx`, `tcp_connect`, or `ssh_banner`. `target` is an `http://` or `https://` URL. The public path is the hostname with the dots removed, so `https://example.com` is served at `/examplecom`. Two entries with the same hostname collide.

```yaml
- module: https_2xx
  target: https://example.com
```

## Run

From this directory:

```
ssh-add -L
uv run pyinfra inventory.py deploy.py --dry
make deploy
```

`--dry` connects and prints the changes. It does not apply them.

`make deploy` runs `uv run pyinfra inventory.py deploy.py`. pyinfra prints the change list and waits. Confirm to apply. Skip the prompt with:

```
uv run pyinfra inventory.py deploy.py --yes
```

The run applies three steps:

1. [deploys/base.py](deploys/base.py) — admin user, sudo, sshd password login off, `SWAP_GIB` GiB `/swapfile`, firewalld public zone target `DROP`, `SSH_PORT`/tcp allowed. Details in [docs/01-setup.md](docs/01-setup.md).
2. [deploys/blackbox.py](deploys/blackbox.py) — `blackbox_exporter` `BLACKBOX_VERSION` listening on `BLACKBOX_LISTEN`. No ICMP. No `CAP_NET_RAW`. Details in [docs/02-blackbox.md](docs/02-blackbox.md).
3. [deploys/nginx.py](deploys/nginx.py) — nginx on `NGINX_PORT`, one path per probe. firewalld allows that port from every source. Port 80 stays closed. Details in [docs/03-nginx-proxy.md](docs/03-nginx-proxy.md).

The run fails if `http://<BLACKBOX_LISTEN>/-/healthy` fails, or if any probe path does not return a `probe_success` metric. A target that is down fails the deploy.

Pre-existing firewalld rich rules are left alone. The workstation SSH config is not copied to the VM.

## Check

On the VM, using your path from `probes.yml`:

```
curl -fsS http://127.0.0.1:9116/-/healthy
curl -fsS http://127.0.0.1:9115/examplecom
```

From a host that can reach `SSH_HOSTNAME`:

```
curl -fsS http://203.0.113.10:9115/examplecom
```

A Prometheus `Probe` for that path is in [docs/03-nginx-proxy.md](docs/03-nginx-proxy.md).

## Adding a probe

Edit `files/nginx/probes.yml`, then run `make deploy` again.
