#!/bin/bash

mpr put -r -F src/* /
mpr reboot
sleep 1.2
mpremote
