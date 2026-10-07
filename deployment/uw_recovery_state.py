"""Recognize only the dated Unit 4 repair, preserving all other local changes."""
import re

PUBLISHED_RUNNER = 'aaac6833eef0cfb868ac0b3fb72c601d3c7a734c'
RECOVERY_BACKUP = '/root/uw-relia-recovery-published-20261007'


def validate_recovery(host, record, head, profile, old_profile,
                      firewall, old_firewall, supervisor, old_supervisor):
    assert host in ('s4i1r', 's4i1t', 's4i2r', 's4i2t'), 'Not a Unit 4 repair'
    assert record.get('status') == 'active'
    assert record.get('scope') == 'UW RELIA published runner update and recovery'
    assert record.get('host') == host and record.get('backup') == RECOVERY_BACKUP
    assert record.get('source_commit') == head == PUBLISHED_RUNNER
    assert record.get('address') == '192.168.2.1' and not record.get('quarantined')
    strip_address = lambda s: re.sub(r'(?m)^export ADALM_PLUTO_IP_ADDRESS=.*$', '', s)
    assert strip_address(profile) == strip_address(old_profile), 'Unrelated profile change'
    assert re.findall(r'(?m)^export ADALM_PLUTO_IP_ADDRESS=(.*)$', profile) == ['192.168.2.1']
    additions = {
        'iptables -A FORWARD -s 10.10.20.2 -d 192.168.2.1 -j ACCEPT',
        'iptables -A FORWARD -d 10.10.20.2 -s 192.168.2.1 -j ACCEPT',
    }
    # Blank-line placement varied between the two recorded recovery steps.
    lines = lambda s: [line for line in s.splitlines() if line.strip()]
    assert lines(firewall) == lines(old_firewall.replace(
        'iptables -A FORWARD -s 10.10.20.2 -j REJECT',
        '\n'.join(sorted(additions)) + '\niptables -A FORWARD -s 10.10.20.2 -j REJECT'
    )) or lines(firewall) == lines(old_firewall.replace(
        'iptables -A FORWARD -s 10.10.20.2 -j REJECT',
        '\n'.join(sorted(additions, reverse=True)) + '\niptables -A FORWARD -s 10.10.20.2 -j REJECT'
    )), 'Unrelated firewall change'
    assert supervisor == old_supervisor, 'Unrelated Supervisor change'

