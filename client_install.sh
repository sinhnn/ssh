#!/bin/bash

function mwget() {
	wget $*
	_pid=$!

	if [[ $_pid ]]; then
		while [[ ( -d /proc/$_pid  ) && ( -z `grep zombie /proc/$_pid/status`  ) ]]; do
			sleep 1
		done
		echo "DONE!!!!!!!!"
	fi
}

url="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
ofile=`basename $url`
wget $url -O $ofile \
	&& sudo apt install -y ./$ofile \
	&& sudo apt install -y xorg xserver-xorg openbox obmenu tigervnc* wget curl firefox cifs-utils caja mate-terminal caja-open-terminal ffmpeg scrot xsel xdotool \
	&& echo '0' > .done
