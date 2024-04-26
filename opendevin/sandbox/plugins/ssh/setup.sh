#!/bin/bash

set -e

if which apt; then
  apt update
  apt install -y openssh-server
elif which yum; then
  yum install -y openssh-server
elif which apk; then
  apk add openssh-server
else
  echo "Package manager not found. You must manually install OpenSSH."
  exit 1
fi

mkdir -p -m0755 /var/run/sshd

