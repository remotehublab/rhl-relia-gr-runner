
# Installation

This project is intended to be deployed in a Raspberry Pi with an ADALM-Pluto.

## ADALM-Pluto IP configuration

When you connect an ADALM Pluto to a Raspberry Pi, it creates a network interface like 192.168.2.0/24 where by default it assigns 192.168.2.1 to the Pluto and 192.168.2.10 to the host (the Raspberry Pi).

You can edit this configuration by changing the content in the config.txt file mounted in /media/pi/PlutoSDR/config.txt and then saving and running:
```
# eject /dev/sda
# sleep 5
# uhubctl -l 1-1 -a cycle
```

The ``eject`` command will trigger [https://wiki.analog.com/university/tools/pluto/users/customizing](the intended effect of Microsoft Windows eject command), instead of just running ``umount``.

## Installer

The repository comes with a script to be run with a ``sudoer`` user (such as pi). You can run it doing (values are just an example):

```
wget https://gitlab.com/relia-project/gr-engine/relia-gr-runner/-/raw/main/installer/relia-installer.py -O relia-installer.py
python relia-installer.py --device-id uw-s1i1 --device-password (password) --device-type r --data-uploader-url https://relia.rhlab.ece.uw.edu/pluto/data-uploader/ --scheduler-url https://relia.rhlab.ece.uw.edu/pluto/ --adalm-pluto-ip-address 192.168.3.1
```

