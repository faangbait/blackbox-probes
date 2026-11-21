# 03: nginx proxy

What `deploys/nginx.py` does on `make deploy`, after the exporter is up. The run command is in [the README](../README.md).

`blackbox_exporter` stays on loopback. nginx publishes one path per probe and chooses the module and the target from that path.

## Add a probe

Edit [files/nginx/probes.yml](../files/nginx/probes.yml), then `make deploy`.

```yaml
- module: https_2xx
  target: https://example.com
```

`module` must be one of the names in `blackbox.yml`. `target` must be an `http://` or `https://` URL. The public path is the hostname with the dots removed:

| target | path |
|---|---|
| `https://example.com` | `/examplecom` |
| `https://example.org` | `/exampleorg` |

nginx discards the caller's query string. Two targets with the same hostname produce the same path, and the deploy refuses that.

## Ports

| | |
|---|---|
| **blackbox** | `BLACKBOX_LISTEN` (`127.0.0.1:9116`) |
| **nginx** | `NGINX_PORT` (`9115`), rendered from [blackbox.conf.j2](../files/nginx/blackbox.conf.j2) to `/etc/nginx/conf.d/blackbox.conf` |
| **Firewall** | `NGINX_PORT`/tcp open to every source in the `public` zone |

The packaged nginx server on port 80 stays in `/etc/nginx/nginx.conf`. firewalld's `DROP` policy leaves 80 closed. This step does not open it.

## Prometheus

Point a `Probe` at `SSH_HOSTNAME:NGINX_PORT` and at the path from the table. `module` is sent and then discarded. The static target is the instance label. Keep it equal to the URL in `probes.yml`.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: Probe
metadata:
  name: examplecom
spec:
  prober:
    url: 203.0.113.10:9115  # where Prometheus connects (SSH_HOSTNAME:NGINX_PORT from target.py)
    path: /examplecom       # which probe nginx runs
  module: https_2xx         # sent, then discarded
  targets:
    staticConfig:
      static:
        - https://example.com   # instance label; keep it equal to the path's target
```

Replace the address and port with `SSH_HOSTNAME` and `NGINX_PORT` from `target.py`.

## SELinux

nginx runs as `httpd_t`.

| | |
|---|---|
| **Port** | `tcp/NGINX_PORT` labeled `http_port_t` (`semanage`, from `policycoreutils-python-utils`) |
| **Boolean** | `httpd_can_network_connect` on, persistent, so nginx can connect to `BLACKBOX_LISTEN` |

## Check

When the nginx file changes, the step runs `nginx -t` and reloads nginx. It then curls each path on `127.0.0.1:NGINX_PORT` and requires a `probe_success` metric. A down target fails the deploy.

From outside the VM:

```
curl -fsS http://203.0.113.10:9115/examplecom
```
