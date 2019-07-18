#!/bin/bash

# Helper script for RPI 1B optionally executed by the two_way_crossover service script.
# Waits 30 sec to see if there is a user logged in (as over ssh) and if there isn't then
# remount the filesystem readonly to prevent corruption due to overclocking and also bring
# the network interface down since it seems like a good idea to do that as well.
# Ideally the cpu frequency should be increased by this script (say from 700 to 900 MHz) after
# remounting the filesystem but this seems impossible on a standard Arch as of current (?).
# Rumors have it that this feature might come to RPI with kernel 5.13.

sleep 30

users=$(users)

if [ -n "$(users)" ] 
then
    echo "there are user(s) logged in, exiting..."
    exit 0
fi

echo bringing ethernet down
ip link set eth0 down

echo mounting / read-only (use 'mount -o remount,rw /' to get it writable)
mount -o remount,ro /

echo done

exit 0
