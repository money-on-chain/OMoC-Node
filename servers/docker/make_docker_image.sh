#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

clean_files () {
    rm -r "$DIR/files/$1/"
    mkdir "$DIR/files/$1/"
    touch "$DIR/files/$1/.placeholder"
}

copy_files () {
    cp -f -r "$DIR/../$1" "$DIR/files/" || exit 1
}

pyclean () {
    find . -type f -name "*.py[co]" -delete
    find . -type d -name "__pycache__" -delete
}

cd "$DIR"

clean_files "common"
clean_files "contracts"
clean_files "oracle"

copy_files "requirements.txt"
copy_files "common"
copy_files "oracle"
copy_files "build/contracts/"

pyclean

sudo docker build -t omoc -f Dockerfile .
