#!/bin/bash
set -ev

if [[ -z $TRAVIS_TAG ]]; then
  echo TRAVIS_TAG unset, exiting
  exit 1
fi

BUILD_REPO_URL=https://github.com/zebra-lucky/electrum-zcash

cd build

git clone --branch $TRAVIS_TAG $BUILD_REPO_URL electrum-zcash

cd electrum-zcash

export PY36BINDIR=/Library/Frameworks/Python.framework/Versions/3.6/bin/
export PATH=$PATH:$PY36BINDIR
source ./contrib/zcash/travis/electrum_zcash_version_env.sh;
echo wine build version is $ELECTRUM_ZCASH_VERSION

sudo pip3 install --upgrade pip
sudo pip3 install -r contrib/deterministic-build/requirements.txt
sudo pip3 install \
    x11_hash>=1.4 \
    pycryptodomex==3.6.0 \
    btchip-python==0.1.26 \
    keepkey==4.0.2 \
    trezor==0.9.1

pyrcc5 icons.qrc -o gui/qt/icons_rc.py

export PATH="/usr/local/opt/gettext/bin:$PATH"
./contrib/make_locale
find . -name '*.po' -delete
find . -name '*.pot' -delete

cp contrib/zcash/osx.spec .
cp contrib/zcash/pyi_runtimehook.py .
cp contrib/zcash/pyi_tctl_runtimehook.py .

pyinstaller \
    -y \
    --name electrum-zcash-$ELECTRUM_ZCASH_VERSION.bin \
    osx.spec

sudo hdiutil create -fs HFS+ -volname "Electrum-Zcash" \
    -srcfolder dist/Electrum-Zcash.app \
    dist/electrum-zcash-$ELECTRUM_ZCASH_VERSION-macosx.dmg
