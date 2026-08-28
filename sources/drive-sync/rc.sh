#!/bin/zsh
# rclone wrapper pinned to the Hospital Registers Drive root folder.
ROOT=0B1TlfouSwHTnfmNWZ0JFdGdodHRqYnBpYkRjVnNmU19WS0NUTVdybDg1V2pSckpYemhDNlE
exec rclone "$@" --drive-root-folder-id="$ROOT"
