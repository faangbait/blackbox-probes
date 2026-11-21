# 01: Base system

What `deploys/base.py` applies on `make deploy`. Host, address, port, and admin user come from [target.py](../target.py).

## Packages

`firewalld` and `curl`.

## Admin user

`SSH_USER`, uid `ADMIN_UID` (`1001`), group `wheel`, password locked. The only authorized key is the `ssh-add -L` line whose comment starts with `cardno:`.

Sudoers comes from [files/sudoers/admin.j2](../files/sudoers/admin.j2) and is installed at `/etc/sudoers.d/<SSH_USER>`:

```
<SSH_USER> ALL=(ALL) NOPASSWD:ALL
```

`visudo -cf` checks that file when it changes. `restorecon` labels `~/.ssh` as `ssh_home_t`.

## SSH

[files/sshd/00-lockdown.conf](../files/sshd/00-lockdown.conf) is installed as `/etc/ssh/sshd_config.d/00-lockdown.conf`. The `00-` name sorts before `50-cloud-init.conf`, so these settings win. When the file changes, the deploy runs `sshd -t` and reloads sshd.

## Swap

`SWAP_GIB` gibibytes (`2`) at `/swapfile`, mode 600. `/etc/fstab` gets:

```
/swapfile none swap sw 0 0
```

## Firewall

`public` zone target `DROP`. `SSH_PORT`/tcp is allowed from every source.
