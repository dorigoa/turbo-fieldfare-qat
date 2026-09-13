#!/usr/bin/env bash
set -u

#if [[ -z "$1" ]]; then
if [[ -z "${1:-}" ]]; then
    echo "Error: argument with quantization number is mandatory ('4', '5', '6', '8')." >&2
    #usage >&2
    exit 1
fi

case "$1" in
    4|5|6|8) ;;
    *)
        echo "Error: invalid quantization '$1' (allowed: '4', '5', '6', '8')." >&2
        exit 1
        ;;
esac

if ! command -v hf >/dev/null 2>&1; then
    echo "Error: 'hf' command not found in PATH." >&2
    exit 1
fi

REPO="mlx-community/gemma-4-26B-A4B-it-qat-${1}bit"
REV=$(hf models info "${REPO}" --expand sha | jq -r .sha)
URL="https://huggingface.co/${REPO}/resolve/${REV}/model.safetensors.index.json"
sourceIndexSHA256=$(curl -fsSL "$URL" | sha256sum | awk '{print $1}')

echo $REPO
echo $REV
echo $URL
echo $sourceIndexSHA256

list_file=$(mktemp)

# Costruisce la lista dei file a partire dall'output di grep -r
grep -rE "gemma-4|0d77464eeb233a2da68ebf9d7dc4edaac7db956d|bf198c9f5ea6462addca1966e5dd669c407537a876e82cf06db9084c5c850b13" turbo-fieldfare/   | grep '^turbo-fieldfare/Sources'|awk -F":" '{print $1}' | sort -u > "$list_file"

# Se non trova file, termina
if [ ! -s "$list_file" ]; then
  echo "No file found." >&2
  exit 0
fi

while IFS= read -r file; do
  sed -i '' 's+gemma-4-26b-a4b-it+gemma-4-26b-a4b-it-qat-q'"${1}"'+' "$file"
  sed -i '' 's+mlx-community/gemma-4-26b-a4b-it-4bit+'"${REPO}"'+' "$file"
  sed -i '' 's+Gemma 4 26B-A4B IT 4-bit+Gemma 4 26B-A4B IT QAT '"${1}"'-bit+' "$file"
  sed -i '' 's+0d77464eeb233a2da68ebf9d7dc4edaac7db956d+'"${REV}"'+' "$file"
  sed -i '' 's+bf198c9f5ea6462addca1966e5dd669c407537a876e82cf06db9084c5c850b13+'"${sourceIndexSHA256}"'+' "$file"

done < "$list_file"

# cleanup
rm -f "$list_file"
