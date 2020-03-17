#!/bin/bash
USER="root"
SERVER="34.95.189.211"
IdentityFile="id_rsa"
SRC_DIR="~/.ytv"
DST_DIR="rsync/$SERVER/"

mkdir -p $DST_DIR
rsync -avz \
	-e "ssh -i $IdentityFile" \
	$USER@$SERVER:$SRC_DIR \
	$DST_DIR

