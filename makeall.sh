#!/usr/bin/env bash

if [[ -z "${1:-}" ]]; then
    echo "Error: argument with quantization number is mandatory ('4', '5', '6', '8')." >&2
    exit 1
fi

case "$1" in
    4|5|6|8) ;;
    *)
        echo "Error: invalid quantization '$1' (allowed: '4', '5', '6', '8')." >&2
        exit 1
        ;;
esac
rm -rf turbo-fieldfare
git clone git@github.com:drumih/turbo-fieldfare.git

#./patch.sh $1
./patch_model.py --root turbo-fieldfare ${1}bit
cd turbo-fieldfare

mkdir -p Scratch
cp ../build-app.sh Scratch/
Scratch/build-app.sh --install
