
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

The repository comes with a script to be run with a ``sudoer`` user (such as pi).


```
sudo apt install build-essential python3-dev git python3-venv
sudo apt install firejail 
sudo apt install supervisor
sudo apt install gnuradio gnuradio-dev:armhf libgnuradio-analog3.8.2:armhf libgnuradio-audio3.8.2:armhf libgnuradio-blocks3.8.2:armhf libgnuradio-channels3.8.2:armhf libgnuradio-digital3.8.2:armhf libgnuradio-dtv3.8.2:armhf libgnuradio-fec3.8.2:armhf libgnuradio-fft3.8.2:armhf libgnuradio-filter3.8.2:armhf libgnuradio-iio1 libgnuradio-pmt3.8.2:armhf libgnuradio-qtgui3.8.2:armhf libgnuradio-runtime3.8.2:armhf libgnuradio-trellis3.8.2:armhf libgnuradio-uhd3.8.2:armhf libgnuradio-video-sdl3.8.2:armhf libgnuradio-vocoder3.8.2:armhf libgnuradio-wavelet3.8.2:armhf libgnuradio-zeromq3.8.2:armhf


adduser --disabled-password relia


as relia:

git clone https://gitlab.com/relia-project/gr-engine/relia-gr-runner.git
git clone https://gitlab.com/relia-project/gr-engine/relia-blocks.git
```

In the /etc/firejail/firejail.config add:

change:

restricted-network yes

for:

restricted-network no


Then copy and adapt security/iptable.sh to /usr/local/bin/ and run it, and run:

crontab -e 

Append:

@reboot /usr/local/bin/iptables.sh

