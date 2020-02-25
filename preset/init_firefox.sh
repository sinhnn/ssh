
mkdir -p ~/.mozilla/firefox/gbgwlb7y.default-release  \
	&& mkdir -p ~/.mozilla/firefox/ytv.default \
	&& echo -e "[Install4F96D1932A9F858E]
Default=gbgwlb7y.default-release
Locked=1

[Profile1]
Name=default
IsRelative=1
Path=ytv.default
Default=1

[Profile0]
Name=default-release
IsRelative=1
Path=ytv.default-release

[General]
StartWithLastProfile=1
Version=2" > ~/.mozilla/firefox/profiles.in \
	&& echo 'user_pref(\"general.useragent.override\",\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36\");' >> ~/.mozilla/firefox/ytv.default/user.jsx \
	&& echo 'user_pref(\"general.useragent.override\",\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36\");' >> ~/.mozilla/firefox/ytv.default-release/user.jsx \
