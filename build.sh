#!/bin/bash

# example of build script

set -e

HWSWA2dir=/home/akartashov/hwswa2/build/hwswa2

pushd ${HWSWA2dir}

git pull

which rst2pdf >/dev/null && \
{ for d in README.rst CHANGELOG.rst docs/*rst; do rst2pdf $d; done; }

[ -d virtualenv ] || virtualenv --python=/usr/bin/python2 \
                        --quiet --no-site-packages --always-copy \
                        --unzip-setuptools --prompt='(hwswa2)' virtualenv

virtualenv --relocatable virtualenv
source virtualenv/bin/activate

pip install -r requirements.txt
virtualenv --relocatable virtualenv

PDFs=$(find . -type f -name '*.pdf')
git archive --prefix hwswa2/ --format tar --output hwswa2.tar HEAD
tar --append -f hwswa2.tar --transform 's,^\.,hwswa2,' ./virtualenv/ $PDFs
gzip --to-stdout hwswa2.tar > hwswa2.tgz && rm hwswa2.tar

sudo rm -rf /usr/local/share/hwswa2/* && tar zxf ${HWSWA2dir}/hwswa2.tgz -C /usr/local/share/

popd

scp ${HWSWA2dir}/hwswa2.tgz me@gorilych.ru:/var/www/gorilych.ru/me/

echo local copy ${HWSWA2dir}/hwswa2.tgz
echo download from http://gorilych.ru/me/hwswa2.tgz

