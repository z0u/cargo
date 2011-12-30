#!/usr/bin/env bash

#
# This script starts the game in GNU/Linux.
#

DIR=$(dirname $0)

exec blenderplayer "$DIR/Cargo.blend"

