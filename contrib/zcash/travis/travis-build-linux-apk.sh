#!/bin/bash
set -ev

if [[ -z $TRAVIS_TAG ]]; then
  echo TRAVIS_TAG unset, exiting
  exit 1
fi

BUILD_REPO_URL=https://github.com/zebra-lucky/electrum-zcash

cd build

git clone --branch $TRAVIS_TAG $BUILD_REPO_URL electrum-zcash

docker run --rm \
    -v $(pwd):/opt \
    -w /opt/electrum-zcash \
    -t zebralucky/electrum-dash-winebuild:Linux /opt/build_linux.sh

sudo find . -name '*.po' -delete
sudo find . -name '*.pot' -delete

sudo chown -R 1000 electrum-zcash

docker run --rm \
    -v $(pwd)/electrum-zcash:/home/buildozer/build \
    -t zebralucky/electrum-dash-winebuild:Kivy bash -c \
    'rm -rf packages && ./contrib/make_packages && ./contrib/make_apk'
