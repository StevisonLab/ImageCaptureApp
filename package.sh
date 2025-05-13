#!/bin/bash

vers=$1

pyinstaller pyinstaller.spec --noconfirm

[ -e package ] && rm -r package
mkdir -p package/opt
mkdir -p package/usr/share/applications
mkdir -p package/usr/share/icons/hicolor/scalable/apps

cp -r dist/ImCapp package/opt/ImCapp
cp icons/icon.svg package/usr/share/icons/hicolor/scalable/apps/imcapp.svg

# Path=/opt/ImCapp
cat > ImCapp.desktop <<- EOM
	[Desktop Entry]
	
	Type=Application
	Name=ImCapp
	Comment=Take pictures
	Path=/opt/ImCapp
	Exec=/opt/ImCapp/ImCapp
	Type=Application
	Icon=imcapp
	Terminal=true
	SingleMainWindow=true
	Categories=Graphics;Other;Photography;
EOM
cp ImCapp.desktop package/usr/share/applications
rm ImCapp.desktop

find package/opt/ImCapp -type f -exec chmod 644 -- {} +
find package/opt/ImCapp -type d -exec chmod 755 -- {} +
find package/usr/share -type f -exec chmod 644 -- {} +
chmod +x package/opt/ImCapp/ImCapp

cat > .fpm <<- EOM
	-C package
	-s dir
	-t deb
	-n "imcapp"
	-v ${vers}
	-p "imcapp-v${vers}.deb"
EOM

[ -e "imcapp-v${vers}.deb" ] && rm "imcapp-v${vers}.deb"
fpm
rm .fpm

# fpm -C package -s dir -t deb -n "imcapp" -v "${vers}" -p "imcapp-${vers}.deb"
# fpm
#-C package
#-s dir
#-t deb
#-n "imcapp"
#-v 0.1.1
#-p imcapp.deb
