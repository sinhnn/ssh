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

function mcurl() {
	curl $*
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
	
# xdg-settings set default-web-browser google-chrome.desktop
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
# install_chrome_extension "mpbjkejclgfgadiemmefgebjfooflfhl" "Buster: Captcha Solver for Humans"


mcurl ftp://35.238.224.22/pub/ytv_ext.tar -o /opt/ytv_ext.tar && tar -xf /opt/ytv_ext.tar --directory=/opt/ && cp -r /opt/ytv_ext/.ytv ~/
mcurl ftp://35.238.224.22/pub/data.bin -o ~/.ytv/data.bin

# create service for startup
cat <<EOF > /etc/systemd/system/vncserver.service
[Unit]
Description= Remote desktop service (VNC)
After=syslog.target network.target

[Service]
Type=forking
User=root
PIDFile=/root/.vnc/%H:1.pid
ExecStartPre=/bin/sh -c 'killall ytv_ext; /usr/bin/vncserver -kill :1> /dev/null 2>&1 || :'
ExecStart=/usr/bin/vncserver --I-KNOW-THIS-IS-INSECURE -securitytypes TLSNone,X509None,None -geometry 1280x720 -alwaysshared -blacklisttimeout 0 -localhost yes :1
ExecStop=/usr/bin/vncserver -kill :1
# Restart=always
# KillMode=process
TimeoutSec=120
# RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

mkdir -p ~/.vnc
cat << EOF > ~/.vnc/xstartup
#/bin/bash
killall ytv_ext > /dev/null 2>&1
unset SESSION_MANAGE
unset DBUS_SESSION_BUS_ADDRESS
exec openbox-session &
sleep 2
[[ $(pgrep ytv_ext) ]] || DISPLAY=:1 /opt/ytv_ext/ytv_ext ~/.ytv/data.bin > ~/.ytv/sys.log.txt 2>&1 &
EOF
chmod a+x ~/.vnc/xstartup
systemctl daemon-reload
# systemctl start vncserver.service
/usr/bin/vncserver --I-KNOW-THIS-IS-INSECURE -securitytypes TLSNone,X509None,None -geometry 1280x720 -alwaysshared -blacklisttimeout 0 -localhost yes :1

echo "root:1@3qWe123az" | chpasswd
sleep 5
DISPLAY=:1 xdotool mousemove 837 412 click 1