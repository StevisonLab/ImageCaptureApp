#!/bin/bash

[ -e package ] && rm -r package
mkdir -p package/opt
mkdir -p package/usr/share/applications

cp -r dist/ImCapp package/opt/ImCapp

cat > ImCapp.desktop <<- EOM
	[Desktop Entry]
	
	Type=Application
	Name=ImCapp
	Path=/opt/ImCapp
	Exec=/opt/ImCapp/ImCapp
EOM
cp ImCapp.desktop package/usr/share/applications

find package/opt/ImCapp -type f -exec chmod 644 -- {} +
find package/opt/ImCapp -type d -exec chmod 755 -- {} +
find package/usr/share -type f -exec chmod 644 -- {} +
chmod +x package/opt/ImCapp/ImCapp
