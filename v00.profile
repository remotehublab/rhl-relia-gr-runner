blacklist /boot/*
blacklist /home/*
blacklist /lost+found/*
blacklist /media/*
blacklist /mnt/*
blacklist /opt/*
blacklist /root/.gnuradio
read-only /root/.gnuradio
blacklist /sbin/*
blacklist /srv/*
blacklist /sys/*
whitelist /tmp/relia-*
blacklist /usr/games/*
blacklist /usr/include/*
blacklist /usr/libexec/*
blacklist /usr/sbin/*
blacklist /usr/src/*
whitelist /var/tmp/systemd-private-*
read-only /var/tmp/systemd-private-*

blacklist /dev/autofs/*
blacklist /dev/b*
blacklist /dev/c*
blacklist /dev/d*
blacklist /dev/fb0*
blacklist /dev/fd/*
blacklist /dev/fu*
blacklist /dev/gpi*
blacklist /dev/h*
blacklist /dev/i*
blacklist /dev/kmsg/*
blacklist /dev/lo*
blacklist /dev/m*
blacklist /dev/n*
blacklist /dev/p*
blacklist /dev/r*
blacklist /dev/sda*
blacklist /dev/serial*
blacklist /dev/sg0/*
blacklist /dev/shm/*
blacklist /dev/snd/*
blacklist /dev/std*
blacklist /dev/tty*
blacklist /dev/u*
blacklist /dev/v*
blacklist /dev/v*
blacklist /dev/watchdog*
blacklist /dev/zero/*

blacklist /run/a*
blacklist /run/blkid/*
blacklist /run/c*
blacklist /run/d*
blacklist /run/initctl/*
blacklist /run/l*
blacklist /run/m*
blacklist /run/network/*
blacklist /run/plymouth/*
blacklist /run/r*
blacklist /run/sendsigs.omit.d/*
blacklist /run/shm/*
blacklist /run/ssh*
blacklist /run/su*
blacklist /run/sysconfig/*
blacklist /run/systemd/*
blacklist /run/t*
blacklist /run/udev/*
blacklist /run/udisks2/*
blacklist /run/utmp/*
blacklist /run/v*
blacklist /run/wpa_supplicant/*
blacklist /run/x*

# blacklist /bin
# blacklist /etc
# blacklist /lib
# blacklist /proc
# blacklist /usr/bin/*
# blacklist /usr/lib/*
# blacklist /usr/local/*
# blacklist /usr/share/*