#!/bin/bash

vers=$1

pyinstaller pyinstaller.spec --noconfirm

[ -e package ] && rm -r package
mkdir -p package/opt
mkdir -p package/usr/share/applications
mkdir -p package/usr/share/icons/hicolor/scalable/apps

cp -r dist/ImageCaptureApp package/opt/ImageCaptureApp
cp icons/icon.svg package/usr/share/icons/hicolor/scalable/apps/imagecaptureapp.svg

# Path=/opt/ImCapp
cat > ImageCaptureApp.desktop <<- EOM
	[Desktop Entry]
	
	Type=Application
	Name=ImageCaptureApp
	Comment=Take pictures
	Path=/opt/ImageCaptureApp
	Exec=/opt/ImageCaptureApp/ImageCaptureApp
	Type=Application
	Icon=imagecaptureapp
	Terminal=true
	SingleMainWindow=true
	Categories=Graphics;Other;Photography;
EOM
cp ImageCaptureApp.desktop package/usr/share/applications
rm ImageCaptureApp.desktop

find package/opt/ImageCaptureApp -type f -exec chmod 644 -- {} +
find package/opt/ImageCaptureApp -type d -exec chmod 755 -- {} +
find package/usr/share -type f -exec chmod 644 -- {} +
chmod +x package/opt/ImageCaptureApp/ImageCaptureApp

cat > .fpm <<- EOM
	-C package
	-s dir
	-t deb
	-n "imagecaptureapp"
	-v ${vers}
	-p "imagecaptureapp-v${vers}.deb"
EOM

[ -e "imagecaptureapp-v${vers}.deb" ] && rm "imagecaptureapp-v${vers}.deb"
fpm
rm .fpm
