#!/bin/sh
set -eu

label="com.pedro.claude-remote-control"
exec launchctl print "gui/$(id -u)/$label"
