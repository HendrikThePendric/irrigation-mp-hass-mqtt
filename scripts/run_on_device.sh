#!/bin/bash

mpr put -r -F src/* config.json certs/* /
mpr reboot
sleep 1.2
mpremote
