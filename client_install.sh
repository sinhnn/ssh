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

sudo apt update \
	&& sudo apt install -y xorg xserver-xorg openbox obmenu tigervnc* wget curl firefox cifs-utils caja mate-terminal caja-open-terminal ffmpeg scrot xclip xsel xdotool fonts-ubuntu* fonts-noto*  fonts-indic \
	&& echo '0' > .done

wget $url -O $ofile \
	&& sudo apt install -y ./$ofile \

install_chrome_extension () {
  preferences_dir_path="/opt/google/chrome/extensions"
  pref_file_path="$preferences_dir_path/$1.json"
  upd_url="https://clients2.google.com/service/update2/crx"
  mkdir -p "$preferences_dir_path"
  echo "{" > "$pref_file_path"
  echo "  \"external_update_url\": \"$upd_url\"" >> "$pref_file_path"
  echo "}" >> "$pref_file_path"
  echo Added \""$pref_file_path"\" ["$2"]
}

install_chrome_extension "mpbjkejclgfgadiemmefgebjfooflfhl" "Buster: Captcha Solver for Humans"
