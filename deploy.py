"""Apply the state in docs/01-setup.md, docs/02-blackbox.md, and docs/03-nginx-proxy.md."""

from deploys.base import apply_base
from deploys.blackbox import apply_blackbox
from deploys.nginx import apply_nginx

apply_base()
apply_blackbox()
apply_nginx()
