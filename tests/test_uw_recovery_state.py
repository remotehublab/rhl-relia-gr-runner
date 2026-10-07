import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deployment'))
from uw_recovery_state import validate_recovery, PUBLISHED_RUNNER, RECOVERY_BACKUP


class RecoveryStateTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(host='s4i1r', head=PUBLISHED_RUNNER,
            record=dict(status='active', scope='UW RELIA published runner update and recovery',
                        host='s4i1r', source_commit=PUBLISHED_RUNNER, backup=RECOVERY_BACKUP, address='192.168.2.1'),
            old_profile='export USE_FIREJAIL=0\nexport ADALM_PLUTO_IP_ADDRESS=192.168.3.1\nexport TOKEN=private\n',
            profile='export USE_FIREJAIL=0\nexport ADALM_PLUTO_IP_ADDRESS=192.168.2.1\nexport TOKEN=private\n',
            old_firewall='iptables -A FORWARD -s 10.10.20.2 -j REJECT\n',
            firewall='iptables -A FORWARD -s 10.10.20.2 -d 192.168.2.1 -j ACCEPT\niptables -A FORWARD -d 10.10.20.2 -s 192.168.2.1 -j ACCEPT\n\niptables -A FORWARD -s 10.10.20.2 -j REJECT\n',
            old_supervisor=b'autostart=true\n', supervisor=b'autostart=true\n')

    def test_dated_recovery_is_recognized(self):
        validate_recovery(**self.args)

    def test_profile_hot_patch_is_preserved_by_rejecting_reconciliation(self):
        self.args['profile'] += 'export NEW_SETTING=1\n'
        with self.assertRaises(AssertionError): validate_recovery(**self.args)

    def test_firewall_or_supervisor_hot_patch_is_rejected(self):
        for key, extra in [('firewall', '\niptables -A FORWARD -j ACCEPT\n'), ('supervisor', b'command=other\n')]:
            with self.subTest(key=key):
                changed = dict(self.args); changed[key] += extra
                with self.assertRaises(AssertionError): validate_recovery(**changed)

    def test_unrelated_or_quarantined_drift_is_rejected(self):
        for changes in [{'scope':'Other recovery'}, {'host':'s4i2t'}, {'quarantined':'Receiver missing'}]:
            with self.subTest(changes=changes):
                changed = dict(self.args, record=dict(self.args['record'], **changes))
                with self.assertRaises(AssertionError): validate_recovery(**changed)


if __name__ == '__main__': unittest.main()
