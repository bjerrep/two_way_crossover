#!/bin/bash

# Helper script for RPI 1B optionally executed by the two_way_crossover service script.
# Waits 30 sec to see if there is a user logged in (as over ssh) and if there isn't then
# remount the filesystem readonly to prevent corruption due to overclocking and also bring
# the network interface down since it seems like a good idea to do that as well. When this
# happens there unfortunately is a short audio dropout as there will be whenever there is
# too much (network traffic) going on.
#
# Ideally the cpu frequency should be increased by this script (say from 700 to 900 MHz) after
# remounting the filesystem but this seems impossible on a standard Arch as of current (?).
# Rumors have it that this feature might come to RPI with kernel 5.13.
#
# Capture the ACT led (normally hooked up to SD card activity). The ACT led is
# flashing while in the 30 sec window for a remote ssh session.
echo none >/sys/class/leds/led0/trigger

for i in {1..15}
do
   sleep 1
   echo 1 >/sys/class/leds/led0/brightness
   sleep 1
   echo 0 >/sys/class/leds/led0/brightness
done

users=$(users)

if [ -n "$(users)" ] 
then
    echo "there are user(s) logged in, bailing out"
    echo 1 >/sys/class/leds/led0/brightness
    exit 0
fi

echo bringing ethernet down
ip link set eth0 down

sleep 1

echo "mounting / read-only (use 'mount -o remount,rw /' to get it writable)"
mount -o remount,ro /

echo done

# Restore normal ACT led operation
echo mmc0 /sys/class/leds/led0/trigger

exit 0
