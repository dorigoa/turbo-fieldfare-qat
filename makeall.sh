#!/usr/bin/env bash

git clone git@github.com:drumih/turbo-fieldfare.git

python3 ./pin_model.py --repo-path ./turbo-fieldfare/
rc=$?
if [ "$rc" -ne 0 ]; then
    echo "ERRORE: pin_model.py terminated with code $rc. Stop." >&2
    return "$rc" 2>/dev/null || exit "$rc" #exit 1
fi

cd turbo-fieldfare
mkdir -p Scratch
cp ../build-app.sh Scratch/
Scratch/build-app.sh --install