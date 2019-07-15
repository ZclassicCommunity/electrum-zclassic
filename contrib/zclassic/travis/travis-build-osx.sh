#!/bin/bash
set -ev

if [[ -z $TRAVIS_TAG ]]; then
  echo TRAVIS_TAG unset, exiting
  exit 1
fi

BUILD_REPO_URL=https://github.com/ZclassicCommunity/electrum-zclassic

cd build

git clone --branch $TRAVIS_TAG $BUILD_REPO_URL electrum-zclassic

cd electrum-zclassic

export PY36BINDIR=/Library/Frameworks/Python.framework/Versions/3.6/bin/
export PATH=$PATH:$PY36BINDIR
source ./contrib/zclassic/travis/electrum_zclassic_version_env.sh;
echo wine build version is $ELECTRUM_ZCL_VERSION

sudo pip3 install --upgrade pip
sudo pip3 install -r contrib/deterministic-build/requirements.txt
sudo pip3 install \
    pycryptodomex==3.6.0 \
    btchip-python==0.1.28 \
    keepkey==4.0.2 \
    trezor==0.9.1

pyrcc5 icons.qrc -o gui/qt/icons_rc.py

export PATH="/usr/local/opt/gettext/bin:$PATH"
./contrib/make_locale
find . -name '*.po' -delete
find . -name '*.pot' -delete

cp contrib/zclassic/osx.spec .
cp contrib/zclassic/pyi_runtimehook.py .
cp contrib/zclassic/pyi_tctl_runtimehook.py .

pyinstaller \
    -y \
    --name electrum-zclassic-$ELECTRUM_ZCL_VERSION.bin \
    osx.spec

sudo hdiutil create -fs HFS+ -volname "Electrum-Zclassic" \
    -srcfolder dist/Electrum-Zclassic.app \
    dist/electrum-zclassic-$ELECTRUM_ZCL_VERSION-macosx.dmg
