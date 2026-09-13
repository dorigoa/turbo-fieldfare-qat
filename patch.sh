#!/usr/bin/env bash
set -u

list_file=$(mktemp)

# Costruisce la lista dei file a partire dall'output di grep -r
grep -r "gemma-4" turbo-fieldfare/   | grep '^turbo-fieldfare/Sources'|awk -F":" '{print $1}' | sort -u > "$list_file"

# Se non trova file, termina
if [ ! -s "$list_file" ]; then
  echo "No file found." >&2
  exit 0
fi

while IFS= read -r file; do
  sed -i '' 's+mlx-community/gemma-4-26b-a4b-it-4bit+mlx-community/gemma-4-26B-A4B-it-qat-4bit+' "$file"
  sed -i '' 's+Gemma 4 26B-A4B IT 4-bit+Gemma 4 26B-A4B IT QAT 4-bit+' "$file"
  sed -i '' 's+gemma-4-26b-a4b-it+gemma-4-26b-a4b-it-qat+' "$file"
  sed -i '' 's+0d77464eeb233a2da68ebf9d7dc4edaac7db956d+e70c6b3ba0979b3357dcd2f223ad8bde7787a6b6+' "$file"
  sed -i '' 's+bf198c9f5ea6462addca1966e5dd669c407537a876e82cf06db9084c5c850b13+b87c93774de5d13ca9d0e21b045793e42e5df032fb5e7622212524f56f9695f2+' "$file"
done < "$list_file"

# cleanup
rm -f "$list_file"
