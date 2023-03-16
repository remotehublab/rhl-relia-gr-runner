#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Invalid use:"
    echo " $ $0 config-file"
    exit 1
fi

if [ ! -f $1 ]; then
    echo "Configuration file $1 not found"
    echo " $ $0 config-file"
    exit 1
fi

. $1

flask process-tasks
