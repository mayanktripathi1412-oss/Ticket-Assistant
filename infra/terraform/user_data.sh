#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker awscli
systemctl enable docker
systemctl start docker

cat >/etc/profile.d/ticket-assistant.sh <<EOF
export AWS_REGION="${aws_region}"
export STORAGE_BACKEND="dynamodb"
EOF
