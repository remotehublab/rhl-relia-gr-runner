#
# RELIA Installer for Raspberry Pi
#

import os
import socket
import argparse
import subprocess

from urllib.parse import urlparse

def install_system_packages():
    print("Installing system packages...")
    _run("sudo apt-get update")
    _run("sudo apt-get install -y build-essential python3-dev git python3-venv redis-server supervisor firejail gnuradio gnuradio-dev:armhf libgnuradio-analog*:armhf libgnuradio-audio*:armhf libgnuradio-blocks*:armhf libgnuradio-channels*:armhf libgnuradio-digital*:armhf libgnuradio-dtv*:armhf libgnuradio-fec*:armhf libgnuradio-fft*:armhf libgnuradio-filter*:armhf libgnuradio-iio* libgnuradio-pmt*:armhf libgnuradio-qtgui*:armhf libgnuradio-runtime*:armhf libgnuradio-trellis*:armhf libgnuradio-uhd*:armhf libgnuradio-video-sdl*:armhf libgnuradio-vocoder*:armhf libgnuradio-wavelet*:armhf libgnuradio-zeromq*:armhf")

def _run(cmd, *args, **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {cmd}")
    raise_on_error = kwargs.pop('raise_on_error', True)
    result = subprocess.run(cmd, shell=True, *args, **kwargs)
    if raise_on_error and result.returncode != 0:
        raise Exception(f"Command failed: {cmd}")
    return result

def install(device_id: str, device_password: str, device_type: str, data_uploader_url: str, scheduler_url: str, adalm_pluto_ip_address: str):
    print(f"Installing RELIA GR Runner in device {device_id} ({device_type})")

    install_system_packages()

    if not os.path.exists('/home/relia'):
        _run("sudo adduser --disabled-password relia")

    if not os.path.exists("/home/relia/relia-blocks"):
        print("Downloading relia-blocks...")
        _run("sudo -u relia bash -c 'cd; git clone https://gitlab.com/relia-project/gr-engine/relia-blocks.git'")
    else:
        print("Updating relia-blocks...")
        _run("sudo -u relia bash -c 'cd ~/relia-blocks; git pull'")

    relia_blocks_script = "export RELIA_GR_PYTHON_PATH=/home/relia/relia-blocks/python"
    if relia_blocks_script not in open("/home/relia/.bashrc").read():
        print("Adding RELIA_GR_PYTHON_PATH to .bashrc...")
        _run(f"sudo -u relia bash -c 'echo {relia_blocks_script} >> /home/relia/.bashrc'")

    _run("sudo -u relia bash -c 'cd ~/relia-blocks; python install_blocks.py'")

    if not os.path.exists("/home/relia/relia-gr-runner"):
        print("Downloading relia-gr-runner...")
        _run("sudo -u relia bash -c 'cd; git clone https://gitlab.com/relia-project/gr-engine/relia-gr-runner.git'")
    else:
        print("Updating relia-gr-runner...")
        _run("sudo -u relia bash -c 'cd ~/relia-gr-runner; git pull'")

    if "restricted-network no" not in open("/etc/firejail/firejail.config").read():
        print("Enabling restricted network in firejail..")
        _run("sudo bash -c 'sed -i \"s/restricted-network no/restricted-network yes/\" /etc/firejail/firejail.config'")

    print(f"Data uploader URL: {data_uploader_url}")
    data_uploader_hostname = urlparse(data_uploader_url).netloc
    print(f"Data uploader hostname: {data_uploader_hostname}")
    data_uploader_ip_address = socket.gethostbyname(data_uploader_hostname)
    print(f"Data uploader IP address: {data_uploader_ip_address}")
    adalm_pluto_ip_address_parts = adalm_pluto_ip_address.split('.')
    if len(adalm_pluto_ip_address_parts) != 4:
        raise ValueError(f"Invalid IP address format for ADALM Pluto: {adalm_pluto_ip_address}")

    adalm_pluto_ip_address_parts[-1] = '0'  # Replace the last part with '0'
    adalm_pluto_ip_network = '.'.join(adalm_pluto_ip_address_parts) + '/24'
    print(f"ADALM Pluto IP address: {data_uploader_ip_address}")

    iptables_script = f"""
brctl addbr br0
ifconfig br0 10.10.20.1/24 up
sysctl -w net.ipv4.ip_forward=1

iptables --flush
iptables -t nat -F
iptables -X
iptables -Z
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -P FORWARD ACCEPT

# netfilter network address translation
iptables -t nat -A POSTROUTING -o eth0 -s 10.10.20.0/24 -j MASQUERADE
iptables -t nat -A POSTROUTING -o eth1 -s 10.10.20.0/24 -j MASQUERADE

# Allow communication from firejail to the server and to the pluto
iptables -A FORWARD -s 10.10.20.2 -d {data_uploader_ip_address} -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s {data_uploader_ip_address} -j ACCEPT
iptables -A FORWARD -s 10.10.20.2 -d {adalm_pluto_ip_network} -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s {adalm_pluto_ip_network} -j ACCEPT

# But disallow any other communication
iptables -A FORWARD -s 10.10.20.2 -j REJECT
iptables -A FORWARD -d 10.10.20.2 -j REJECT
"""
    print("Writing iptables script...")
    open("/usr/local/bin/iptables.sh", 'w').write(iptables_script)
    os.chmod("/usr/local/bin/iptables.sh", 0o755)

    print("Writing RELIA crontab configuration...")
    open("/etc/cron.d/relia-iptables", 'w').write("@reboot /usr/local/bin/iptables.sh\n")
    os.chmod("/etc/cron.d/relia-iptables", 0o755)

    # TODO: generate the prodrc and firejail

    supervisor_config = """[program:relia]
command=/home/relia/relia-gr-runner/start.sh prodrc
directory=/home/relia/relia-gr-runner/
user=relia
stdout_logfile=/var/tmp/backend-gunicorn.log
stderr_logfile=/var/tmp/backend-gunicorn.err
stdout_logfile_maxbytes=50MB
stderr_logfile_maxbytes=50MB
stdout_logfile_backups=3
stderr_logfile_backups=3
autostart=true
autorestart=true
stopwaitsecs=5
stopasgroup=true
killasgroup=true
"""
    print("Writing supervisor configuration...")
    open("/etc/supervisor/conf.d/relia.conf", 'w').write(supervisor_config)

    _run("sudo supervisorctl update")

    print("Setup completed")

def main():
    parser = argparse.ArgumentParser("RELIA Installer")
    parser.add_argument("--device-id", required=True, help="Device identifier")
    parser.add_argument("--device-password", required=True, help="Device password")
    parser.add_argument("--device-type", choices=('r', 'receiver', 't', 'transmitter'), help="Device type (r or t, receiver or transmitter)")
    parser.add_argument("--data-uploader-url", required=True, help="Data uploader URL")
    parser.add_argument("--scheduler-url", required=True, help="Scheduler URL")
    parser.add_argument("--adalm-pluto-ip-address", default="192.168.2.1", help="Adalm Pluto IP address.")

    args = parser.parse_args()

    device_type = args.device_type.lower()
    if device_type == 'receiver':
        device_type = 'r'
    if device_type == 'transmitter':
        device_type = 't'

    install(args.device_id, args.device_password, device_type, args.data_uploader_url, args.scheduler_url, args.adalm_pluto_ip_address)

    


if __name__ == '__main__':
    main()


