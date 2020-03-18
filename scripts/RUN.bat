@ECHO Off
set PORT=30000
set PROXY="127.0.0.1"
echo "Creating new ssh tunnel on %PORT%...."
rem ssh.exe -ie

echo "Openning browser ..."
REM "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --user-data-dir=%~dp0\chrome  --proxy-server="socks5://127.0.0.1:%PORT%" https://youtube.com





REM echo user_pref("network.proxy.ftp", "127.0.0.1"); >> %~dp0\user.js
REM echo user_pref("network.proxy.ftp_port", %PORT%); >>%~dp0\user.js
REM echo user_pref("network.proxy.http", "127.0.0.1"); >>%~dp0\user.js
REM echo user_pref("network.proxy.http_port", %PORT%); >>%~dp0\user.js
echo user_pref("network.proxy.share_proxy_settings", true); > %~dp0\firefox\user.js
echo user_pref("network.proxy.socks", "127.0.0.1"); >> %~dp0\firefox\user.js
echo user_pref("network.proxy.socks_port", %PORT%); >> %~dp0\firefox\user.js
echo user_pref("media.peerconnection.enabled", false); >> %~dp0\firefox\user.js
REM echo user_pref("network.proxy.ssl", "127.0.0.1"); >> %~dp0\user.js
REM echo user_pref("network.proxy.ssl_port", %PORT%); >> %~dp0\user.js
echo user_pref("network.proxy.type", 1); >>%~dp0\firefox\user.js


"C:\Program Files\Mozilla Firefox\firefox.exe" --profile %~dp0\firefox
