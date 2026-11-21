"""Probe target. Edit these, then match them in ~/.ssh/config."""

# SSH config Host alias. Also the pyinfra host name.
HOST = "probe"

# Address pyinfra dials. 203.0.113.10 is a documentation placeholder.
SSH_HOSTNAME = "203.0.113.10"

# sshd is assumed to already listen here. The base deploy opens this port
# in firewalld and does not change sshd's listen port.
SSH_PORT = 2223

# Admin account the base deploy creates.
SSH_USER = "ec2-user"

"""Server config"""

# uid of SSH_USER.
ADMIN_UID = 1001

# Swapfile size in gibibytes.
SWAP_GIB = 2

"""Blackbox config"""

# Pinned blackbox_exporter linux-amd64 release.
# BLACKBOX_SHA256 is the linux-amd64 line from that release's sha256sums.txt.
BLACKBOX_VERSION = "0.29.1"
BLACKBOX_SHA256 = "b82b81839e6317e84fdd367f46d7ddd3b773fa09cbe2e3d5633a59171d741e76"

# Exporter listen address. Loopback. nginx proxies to it.
BLACKBOX_LISTEN = "127.0.0.1:9116"

# Public nginx port.
NGINX_PORT = 9115
