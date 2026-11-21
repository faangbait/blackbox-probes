# Workstation SSH config. Keep it in step with target.py.
#
# Host probe
#   HostName 203.0.113.10
#   Port 2223
#   User ec2-user

.PHONY: deploy

deploy:
	uv run pyinfra inventory.py deploy.py
