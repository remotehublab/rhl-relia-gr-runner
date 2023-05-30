brctl addbr br0
ifconfig br0 10.10.20.1/24 up
echo "1" > /proc/sys/net/ipv4/ip_forward

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

# relia.test.rhlab.ece.uw.edu
iptables -A FORWARD -s 10.10.20.2 -d 192.168.2.1 -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s 192.168.2.1 -j ACCEPT
iptables -A FORWARD -s 10.10.20.2 -d 128.95.205.61 -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s 128.95.205.61 -j ACCEPT
iptables -A FORWARD -s 10.10.20.2 -d 192.168.3.0/24 -j ACCEPT
iptables -A FORWARD -d 10.10.20.2 -s 192.168.3.0/24 -j ACCEPT


iptables -A FORWARD -s 10.10.20.2 -j REJECT
iptables -A FORWARD -d 10.10.20.2 -j REJECT

