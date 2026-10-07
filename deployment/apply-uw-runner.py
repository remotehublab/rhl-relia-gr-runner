#!/usr/bin/env python3
"""Apply a published UW runner release, preserving secrets and local profiles.

Run as root after staging this release's Git bundle in /tmp. Caller must drain
the pair and check scheduler occupancy before invoking --apply. No apt/pip,
firmware, OS, camera, VPN, or global firewall reinstalls are performed.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from uw_recovery_state import validate_recovery, RECOVERY_BACKUP

parser = argparse.ArgumentParser()
parser.add_argument('--host', required=True)
parser.add_argument('--commit', required=True)
parser.add_argument('--bundle', default='/tmp/uw-relia-runner.bundle')
parser.add_argument('--apply', action='store_true')
parser.add_argument('--reconcile-uw-recovery', action='store_true',
                    help='Accept only the verified 2026-10-07 Unit 4 address/firewall repair')
args = parser.parse_args()
root = Path('/home/relia/relia-gr-runner')
git = ['git', '-c', 'safe.directory=' + str(root), '-C', str(root)]
def run(command):
    return subprocess.check_output(command, text=True).strip()
assert re.fullmatch(r's[1-4]i[12][rt]', args.host)
assert re.fullmatch(r'[0-9a-f]{40}', args.commit)
prior_recovery = None
before = run(git + ['rev-parse', 'HEAD'])
for ledger in (root / 'drift-status.yaml', Path('/drift-status.yaml')):
    if ledger.exists():
        import yaml
        record = yaml.safe_load(ledger.read_text())
        if record.get('status') != 'clean':
            assert args.reconcile_uw_recovery and ledger == root / 'drift-status.yaml', 'Unreconciled drift: ' + str(ledger)
            backup = Path(RECOVERY_BACKUP)
            validate_recovery(args.host, record, before,
                              (root / 'prodrc').read_text(), (backup / 'prodrc').read_text(),
                              Path('/usr/local/bin/iptables.sh').read_text(), (backup / 'iptables.sh').read_text(),
                              Path('/etc/supervisor/conf.d/relia.conf').read_bytes(), (backup / 'relia.conf').read_bytes())
            prior_recovery = record
assert not run(git + ['diff', '--name-only']), 'Tracked hot patch must be reconciled'
assert not run(git + ['diff', '--cached', '--name-only']), 'Staged hot patch must be reconciled'
manifest = json.loads((Path(__file__).parent / 'uw-pluto-fleet.json').read_text())
address = manifest['hosts'][args.host]
profile = root / 'prodrc'
assert profile.exists()
original = profile.read_text()
overrides = dict(manifest['profile_overrides'], ADALM_PLUTO_IP_ADDRESS=address)
updated = original
for key, value in overrides.items():
    pattern = r'(?m)^\s*(?:export\s+)?' + key + r'\s*=.*$'
    matches = re.findall(pattern, updated)
    assert len(matches) <= 1, 'Ambiguous profile ' + key
    line = 'export {}={}'.format(key, value)
    updated = re.sub(pattern, line, updated) if matches else updated.rstrip() + '\n' + line + '\n'
firewall = Path('/usr/local/bin/iptables.sh')
old_firewall = firewall.read_text()
new_firewall = old_firewall
rules = [
    ['-s', '10.10.20.2', '-d', address, '-j', 'ACCEPT'],
    ['-d', '10.10.20.2', '-s', address, '-j', 'ACCEPT'],
]
if address == '192.168.2.1':
    marker = 'iptables -A FORWARD -s 10.10.20.2 -j REJECT'
    assert marker in old_firewall, 'Unexpected firewall startup source'
    lines = '\n'.join('iptables -A FORWARD ' + ' '.join(rule) for rule in rules)
    if lines not in new_firewall:
        new_firewall = new_firewall.replace(marker, lines + '\n\n' + marker)
plan = dict(host=args.host, before=before, after=args.commit, address=address,
            profile_changed=updated != original, firewall_changed=new_firewall != old_firewall,
            reconciles_dated_recovery=prior_recovery is not None)
if not args.apply:
    print(json.dumps(plan)); raise SystemExit(0)
backup = Path('/root/uw-relia-recovery-20261007')
backup.mkdir(mode=0o700, exist_ok=False)
shutil.copy2(profile, backup / 'prodrc')
shutil.copy2(firewall, backup / 'iptables.sh')
(backup / 'old-head').write_text(before + '\n')
ledger = root / 'drift-status.yaml'
if ledger.exists(): shutil.copy2(ledger, backup / 'drift-status.yaml')
record = dict(status='active', scope='UW RELIA runner update and address repair',
              source_commit=args.commit, authoritative_source='remotehublab/rhl-relia-gr-runner',
              backup=str(backup), utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), **plan)
if prior_recovery is not None:
    record['prior_recovery'] = prior_recovery
ledger.write_text(json.dumps(record, indent=2))
run(git + ['fetch', args.bundle, 'main'])
assert run(git + ['rev-parse', 'FETCH_HEAD']) == args.commit
run(git + ['merge', '--ff-only', args.commit])
profile.write_text(updated)
firewall.write_text(new_firewall)
if new_firewall != old_firewall:
    for rule in rules:
        if subprocess.run(['iptables', '-C', 'FORWARD'] + rule, capture_output=True).returncode:
            run(['iptables', '-I', 'FORWARD', '1'] + rule)
assert run(git + ['rev-parse', 'HEAD']) == args.commit
assert not run(git + ['diff', '--name-only'])
record.update(status='clean', reason='Published source and authoritative fleet overrides applied; local credentials preserved',
              profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest())
ledger.write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
