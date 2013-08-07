#!/usr/bin/env bash

if [ $# -lt 1 -o $# -gt 2 ]; then
    echo "Usage: module_rename.sh <FIND> <REPLACE>"
    echo "This will search through all blend files in the current directory."
    exit 1
fi

FINDSTR=$1
if [ $# -gt 1 ]; then
    REPLACESTR=$2
else
    REPLACESTR='\0'
fi

SCRIPT_DIR=$(dirname $0)
SCRIPT=$SCRIPT_DIR/cgrep.py

echo $FINDSTR $REPLACESTR

for f in *.blend; do
    echo blender --factory-startup -b ${f} -P ${SCRIPT} -- ${FINDSTR} ${REPLACESTR}
    blender --factory-startup -b ${f} -P ${SCRIPT} -- ${FINDSTR} ${REPLACESTR}
done

