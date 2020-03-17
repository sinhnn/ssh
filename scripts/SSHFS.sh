#!/bin/bash
USER="root"
SERVER="34.95.189.211"
IdentityFile="id_rsa"
SRC_DIR="~/.ytv"
DST_DIR="mount/$SERVER/"

mkdir -p $DST_DIR
sshfs.exe -o allow_other,defer_permissions,IdentityFile=$IdentityFile \
	$USER@$SERVER:$SRC_DIR \
	$DST_DIR
