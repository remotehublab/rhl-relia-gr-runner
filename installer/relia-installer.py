#
# RELIA Installer for Raspberry Pi
#

import os
import sys
import socket
import argparse
import subprocess

from textwrap import dedent

from urllib.parse import urlparse

def install_system_packages():
    print("Installing system packages...")
    _run("sudo apt-get update")
    _run("sudo apt-get install -y bridge-utils build-essential python3-dev git python3-venv redis-server supervisor firejail gnuradio gnuradio-dev:armhf libgnuradio-analog*:armhf libgnuradio-audio*:armhf libgnuradio-blocks*:armhf libgnuradio-channels*:armhf libgnuradio-digital*:armhf libgnuradio-dtv*:armhf libgnuradio-fec*:armhf libgnuradio-fft*:armhf libgnuradio-filter*:armhf libgnuradio-iio* libgnuradio-pmt*:armhf libgnuradio-qtgui*:armhf libgnuradio-runtime*:armhf libgnuradio-trellis*:armhf libgnuradio-uhd*:armhf libgnuradio-video-sdl*:armhf libgnuradio-vocoder*:armhf libgnuradio-wavelet*:armhf libgnuradio-zeromq*:armhf")

def _run(cmd, *args, **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {cmd}", flush=True)
    raise_on_error = kwargs.pop('raise_on_error', True)
    result = subprocess.run(cmd, shell=True, *args, **kwargs)
    if raise_on_error and result.returncode != 0:
        raise Exception(f"Command failed: {cmd}")
    return result

def install(device_id: str, device_password: str, device_type: str, data_uploader_url: str, scheduler_url: str, adalm_pluto_ip_address: str, redpitaya_ip_address: str, redpitaya_version: str, use_firejail: str = '1'):
    print(f"Installing RELIA GR Runner in device {device_id} ({device_type})")

    if redpitaya_ip_address:
        if not redpitaya_version:
            print(f"Error: redpitaya version must be provided")
            sys.exit(1)
            return

    install_system_packages()

    if not os.path.exists('/home/relia'):
        _run("sudo adduser --gecos \"\" --disabled-password relia")

    if not os.path.exists("/home/relia/relia-blocks"):
        print(f"Downloading relia-blocks in {device_id} ({device_type})...")
        _run("sudo -u relia bash -c 'cd; git clone https://github.com/remotehublab/rhl-relia-gr-blocks.git'")
    else:
        print(f"Updating relia-blocks in {device_id} ({device_type})...")
        _run("sudo -u relia bash -c 'cd ~/relia-blocks; git pull'")

    relia_blocks_script = "export RELIA_GR_PYTHON_PATH=/home/relia/relia-blocks/python"
    if relia_blocks_script not in open("/home/relia/.bashrc").read():
        print("Adding RELIA_GR_PYTHON_PATH to .bashrc...")
        _run(f"sudo -u relia bash -c 'echo {relia_blocks_script} >> /home/relia/.bashrc'")

    _run("sudo -u relia bash -c 'cd ~/relia-blocks; python install_blocks.py'")

    if not os.path.exists("/home/relia/relia-gr-runner"):
        print(f"Downloading relia-gr-runner in {device_id} ({device_type})...")
        _run("sudo -u relia bash -c 'cd; git clone https://github.com/remotehublab/rhl-relia-gr-runner.git'")
    else:
        print(f"Updating relia-gr-runner in {device_id} ({device_type})...")
        _run("sudo -u relia bash -c 'cd ~/relia-gr-runner; git pull'")

    if "restricted-network no" not in open("/etc/firejail/firejail.config").read():
        print("Enabling restricted network in firejail..")
        _run("sudo bash -c 'sed -i \"s/restricted-network no/restricted-network yes/\" /etc/firejail/firejail.config'")

    if "\nrestricted-network yes" in open("/etc/firejail/firejail.config").read():
        print("Fixing firejail.config..")
        _run("sudo bash -c 'sed -i \"s/restricted-network yes/# restricted-network yes/\" /etc/firejail/firejail.config'")

    print("")
    print(f"Network summary for {device_id} ({device_type}):")
    print(f" + Data uploader URL: {data_uploader_url}")
    data_uploader_hostname = urlparse(data_uploader_url).netloc
    print(f" + Data uploader hostname: {data_uploader_hostname}")
    data_uploader_ip_address = socket.gethostbyname(data_uploader_hostname)
    print(f" + Data uploader IP address: {data_uploader_ip_address}")
    if adalm_pluto_ip_address is not None:
        adalm_pluto_ip_address_parts = adalm_pluto_ip_address.split('.')
        if len(adalm_pluto_ip_address_parts) != 4:
            raise ValueError(f"Invalid IP address format for ADALM Pluto: {adalm_pluto_ip_address}")

        adalm_pluto_ip_address_parts[-1] = '0'  # Replace the last part with '0'
        sdr_device_ip_network = '.'.join(adalm_pluto_ip_address_parts) + '/24'
        print(f" + ADALM Pluto network: {sdr_device_ip_network}")
        print("", flush=True)

    elif redpitaya_ip_address is not None:
        sdr_device_ip_network = redpitaya_ip_address + '/32'
    else:
        print(f"Error: adalm pluto or redpitaya IP must be provided")
        sys.exit(1)
        return

    if data_uploader_hostname not in open("/etc/hosts").read():
        hosts_content = open("/etc/hosts").read()
        hosts_content = hosts_content + f"\n\n{data_uploader_ip_address}    {data_uploader_hostname}"
        open("/etc/hosts", 'w').write(hosts_content)

    iptables_script = f"""#!/bin/bash
# Do not edit this file. It is automatically generated by the relia-installer.py

# In cron, PATH is miniaml (e.g., /bin:/usr/bin)
export PATH=$PATH:/usr/sbin:/sbin:/usr/local/bin:/usr/local/sbin

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
iptables -A FORWARD -s 10.10.20.2 -d {sdr_device_ip_network} -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s {sdr_device_ip_network} -j ACCEPT

# But disallow any other communication
iptables -A FORWARD -s 10.10.20.2 -j REJECT
iptables -A FORWARD -d 10.10.20.2 -j REJECT
"""
    print("Writing iptables script...")
    open("/usr/local/bin/iptables.sh", 'w').write(iptables_script)
    os.chmod("/usr/local/bin/iptables.sh", 0o755)

    try:
        _run("sudo ifconfig br0")
    except Exception as err:
        print("br0 does not exist. Calling iptables.sh")
        _run("/usr/local/bin/iptables.sh")

    print("Writing RELIA crontab configuration...")
    open("/etc/cron.d/relia-iptables", 'w').write("@reboot root /usr/local/bin/iptables.sh\n")
    os.chmod("/etc/cron.d/relia-iptables", 0o755)

    if redpitaya_ip_address:
        # Add the external gnuradio blocks for redpitaya
        if not os.path.exists("/home/relia/red-pitaya-notes"):
            _run("git clone https://github.com/pavel-demin/red-pitaya-notes /home/relia/red-pitaya-notes")

    if adalm_pluto_ip_address:
        sdr_configuration = f"export ADALM_PLUTO_IP_ADDRESS={adalm_pluto_ip_address}"
    elif redpitaya_ip_address:
        sdr_configuration = f"export RED_PITAYA_IP_ADDRESS={redpitaya_ip_address}\n"
        if redpitaya_version == '125':
            sdr_configuration += "export GRC_BLOCKS_PATH=$GRC_BLOCKS_PATH:/home/relia/red-pitaya-notes/projects/sdr_transceiver/gnuradio\n"
            sdr_configuration += "export PYTHONPATH=$PYTHONPATH:/home/relia/red-pitaya-notes/projects/sdr_transceiver/gnuradio\n"
            sdr_configuration += "export RED_PITAYA_RATE=100000\n"
        elif redpitaya_version == '122':
            sdr_configuration += "export GRC_BLOCKS_PATH=$GRC_BLOCKS_PATH:/home/relia/red-pitaya-notes/projects/sdr_transceiver_122_88/gnuradio\n"
            sdr_configuration += "export PYTHONPATH=$PYTHONPATH:/home/relia/red-pitaya-notes/projects/sdr_transceiver_122_88/gnuradio\n"
            sdr_configuration += "export RED_PITAYA_RATE=96000\n"
        else:
            print(f"Error: {redpitaya_version} is not currently supported")
            sys.exit(1)
            return
    else:
        print(f"Error: adalm pluto or redpitaya IP must be provided")
        sys.exit(1)
        return

    device_type_map = {'r': 'receiver', 't': 'transmitter'}
    prodrc = dedent(f"""\
        # Do not edit this file. It is automatically generated by the relia-installer.py
        export FLASK_DEBUG=0
        export FLASK_RUN_PORT=6007
        export FLASK_APP=autoapp
        export FLASK_CONFIG=production
        export DEVICE_ID='{device_id}:{device_type}'
        export DEVICE_TYPE='{device_type_map[device_type]}'
        export PASSWORD='{device_password}'
        export DATA_UPLOADER_BASE_URL='{data_uploader_url}'
        export SCHEDULER_BASE_URL='{scheduler_url}'
        export RELIA_GR_PYTHON_PATH=/home/relia/relia-blocks/python
        export USE_FIREJAIL={use_firejail}
        export HOME=/home/relia
        export LOGNAME=relia
        export USER=relia

        """) + "\n" + sdr_configuration
    if use_firejail == '1':
        prodrc += dedent("""\
        FIREJAIL_IP_ADDRESS=10.10.20.2
        FIREJAIL_INTERFACE=br0
        """)
    print("Writing prodrc configuration...")
    open("/home/relia/relia-gr-runner/prodrc", 'w').write(prodrc)

    supervisor_config = """# Do not edit this file. It is automatically generated by the relia-installer.py
[program:relia]
command=/home/relia/relia-gr-runner/start.sh prodrc
directory=/home/relia/relia-gr-runner/
user=relia
stdout_logfile=/dev/shm/relia-gr-runner.log
stderr_logfile=/dev/shm/relia-gr-runner.err
stdout_logfile_maxbytes=5MB
stderr_logfile_maxbytes=5MB
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
    _run("sudo supervisorctl restart relia")

    print(f"Setup of device {device_id} ({device_type}) completed", flush=True)

def main():
    parser = argparse.ArgumentParser("RELIA Installer")
    parser.add_argument("--device-id", required=True, help="Device identifier")
    parser.add_argument("--device-password", required=True, help="Device password")
    parser.add_argument("--device-type", choices=('r', 'receiver', 't', 'transmitter'), help="Device type (r or t, receiver or transmitter)")
    parser.add_argument("--data-uploader-url", required=True, help="Data uploader URL")
    parser.add_argument("--scheduler-url", required=True, help="Scheduler URL")
    parser.add_argument("--adalm-pluto-ip-address", default=None, help="Adalm Pluto IP address.")
    parser.add_argument("--redpitaya-ip-address", default=None, help="Red Pitaya IP address.")
    parser.add_argument("--redpitaya-version", default=None, help="Red Pitaya version (must be 122 or 125)")
    parser.add_argument("--use-firejail", default="1", help="Use firejail (1 or 0).")

    args = parser.parse_args()

    device_type = args.device_type.lower()
    if device_type == 'receiver':
        device_type = 'r'
    if device_type == 'transmitter':
        device_type = 't'

    if args.redpitaya_version is not None and args.redpitaya_version not in ('122', '125'):
        print(f"Error: redpitaya version must be 122 or 125")
        sys.exit(1)
        return

    install(args.device_id, args.device_password, device_type, args.data_uploader_url, args.scheduler_url, args.adalm_pluto_ip_address, args.redpitaya_ip_address, args.redpitaya_version, args.use_firejail)


if __name__ == '__main__':
    main()


