#!/usr/bin/env bash
# Clone upstream turbo-fieldfare, pin one of the checkpoints known to
# patch_model.py, build the Mac app and install it into /Applications.
#
# Only 4-bit checkpoints are offered: the runtime's Metal kernels decode
# 4-bit weights only (router and shared expert may be 8-bit), so a 5/6/8-bit
# checkpoint installs but fails the app's metadata validation. See the
# docstring of patch_model.py.

usage() {
    echo "Usage: $0 MODEL" >&2
    echo "  MODEL  '4bit'     stock mlx-community/gemma-4-26b-a4b-it-4bit (upstream default)" >&2
    echo "         'qat4bit'  mlx-community/gemma-4-26B-A4B-it-qat-4bit (quantization-aware trained)" >&2
}

if [[ -z "${1:-}" ]]; then
    echo "Error: MODEL argument is mandatory." >&2
    usage
    exit 1
fi

case "$1" in
    4bit|qat4bit) ;;
    *)
        echo "Error: invalid model '$1' (allowed: '4bit', 'qat4bit')." >&2
        usage
        exit 1
        ;;
esac
MODEL="$1"

rm -rf turbo-fieldfare
git clone git@github.com:drumih/turbo-fieldfare.git

./patch_model.py --root turbo-fieldfare "${MODEL}"
cd turbo-fieldfare

mkdir -p Scratch
cp ../build-app.sh Scratch/
Scratch/build-app.sh --install
