"""Desktop mirror of shared/action-vectors.json. Run from the repo root."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desktop'))
import lovense_action  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
VECTORS = json.load(open(os.path.join(ROOT, 'shared', 'action-vectors.json'), encoding='utf-8'))


def check(condition, message):
    if not condition:
        raise SystemExit(message)


for row in VECTORS['actions']:
    got = lovense_action.build_thrust_action(row['speed'], row['strokeMin'], row['strokeMax'])
    check(got == row['action'], f"{row['action']}: {got}")

for raw in VECTORS['rejectedActions']:
    check(lovense_action.sanitize_function_action(raw) is None, f'rejected {raw}')

for row in VECTORS['acceptedActions']:
    got = lovense_action.sanitize_function_action(row['in'])
    check(got == row['out'], f"{row['in']}: {got} != {row['out']}")

for row in VECTORS['hosts']:
    got = lovense_action.is_allowed_host_port(row['host'], row['port'])
    check(got is row['ok'], f"{row['host']}:{row['port']} -> {got}")

patterns = lovense_action.shared_patterns()
check(len(patterns) == 6, f'expected 6 patterns, got {len(patterns)}')
check(patterns[0]['name'] == 'Slow Deep', patterns[0]['name'])
print('desktop lovense action: passed')
