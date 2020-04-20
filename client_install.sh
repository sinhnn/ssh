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
	&& echo '0' > /root/.done

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


# create service for startup
cat <<EOF > /etc/systemd/system/vncserver.service
#  Install requirements
#  e.g. yum install tigervnc-server org-x11-fonts-Type1
#  e.g. apt install tigervnc* org-x11-fonts-Type1
#
# 1. Run "systemctl daemon-reload"
# 2. Run "systemctl enable vncserver@:<display>.service"
# 3. firewall-cmd --permanent --zone=public --add-port=590X/tcp
# 4. firewall-cmd --reload

# NOTES: "systemctl list-units" to find mount service
[Unit]
Description= Remote desktop service (VNC)
After=syslog.target network.target local-fs.target remote-fs.target

[Service]
Type=forking
User=sinhnn
PIDFile=/home/sinhnn/.vnc/%H:%i.pid
ExecStartPre=/bin/sh -c '/usr/bin/vncserver -kill :%i > /dev/null 2>&1 || :'
ExecStart=/usr/bin/vncserver -geometry 1280x720 --I-KNOW-THIS-IS-INSECURE -securitytypes TLSNone,X509None,None -localhost no -alwaysshared :%i
ExecStop=/usr/bin/vncserver -kill :%i
# Restart=always
# TimeoutSec=900
# RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
