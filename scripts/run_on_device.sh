#!/bin/bash

mpr put -r -F src/* config.json /
mpr reboot
sleep 1.2
mpremote
