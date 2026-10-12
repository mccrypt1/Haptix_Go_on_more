"""Lovense action and host rules. Kept in step with shared/lovense-action.mjs."""

import json
import os
import re

SPEED_MAX = 20
STROKE_GAP = 20
FUNCTION_RANGES = {
    'Vibrate': (0, 20),
    'Rotate': (0, 20),
    'Thrusting': (0, 20),
    'Fingering': (0, 20),
    'Suction': (0, 20),
    'Oscillate': (0, 20),
    'All': (0, 20),
    'Pump': (0, 3),
    'Depth': (0, 3),
}
LOVENSE_SUFFIX = '.lovense.club'


def clamp_int(value, lo, hi):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return lo
    if number != number or number in (float('inf'), float('-inf')):
        return lo
    return max(lo, min(hi, int(round(number))))


def clamp_speed(value):
    return clamp_int(value, 0, SPEED_MAX)


def clamp_stroke(min_value, max_value, gap=STROKE_GAP):
    span = clamp_int(gap, 1, 100)
    lo = clamp_int(min_value, 0, 100)
    hi = clamp_int(max_value, 0, 100)
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo < span:
        hi = min(100, lo + span)
        lo = hi - span
    return lo, hi


def build_thrust_action(speed=0, stroke_min=0, stroke_max=100, gap=STROKE_GAP):
    level = clamp_speed(speed)
    if level <= 0:
        return 'Stop'
    lo, hi = clamp_stroke(stroke_min, stroke_max, gap)
    return f'Thrusting:{level},Stroke:{lo}-{hi}'


def sanitize_function_action(raw):
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text == 'Stop':
        return 'Stop'
    if not re.fullmatch(r'[A-Za-z0-9:,-]+', text):
        return None
    parts = text.split(',')
    if not parts or len(parts) > 8:
        return None
    cleaned = []
    for part in parts:
        stroke = re.fullmatch(r'Stroke:(\d{1,3})-(\d{1,3})', part)
        if stroke:
            lo, hi = clamp_stroke(stroke.group(1), stroke.group(2))
            cleaned.append(f'Stroke:{lo}-{hi}')
            continue
        match = re.fullmatch(r'([A-Za-z]+):(\d{1,3})', part)
        if not match or match.group(1) not in FUNCTION_RANGES:
            return None
        lo, hi = FUNCTION_RANGES[match.group(1)]
        cleaned.append(f'{match.group(1)}:{clamp_int(match.group(2), lo, hi)}')
    return ','.join(cleaned)


def is_allowed_host_port(host, port):
    if not isinstance(host, str):
        return False
    name = host.strip().lower()
    if not name or len(name) > 253 or not re.fullmatch(r'[a-z0-9.-]+', name):
        return False
    try:
        port_num = int(port)
    except (TypeError, ValueError):
        return False
    if isinstance(port, bool) or port_num != float(port):
        return False
    http_band = 20000 <= port_num <= 20099
    https_band = 30000 <= port_num <= 30099
    if not http_band and not https_band:
        return False
    if name.endswith(LOVENSE_SUFFIX):
        label = name[:-len(LOVENSE_SUFFIX)]
        return bool(re.fullmatch(r'[a-z0-9-]+', label)) and not label.startswith('-') and not label.endswith('-')
    parts = name.split('.')
    if len(parts) != 4:
        return False
    nums = []
    for part in parts:
        if not re.fullmatch(r'\d{1,3}', part) or (len(part) > 1 and part.startswith('0')):
            return False
        number = int(part)
        if number > 255:
            return False
        nums.append(number)
    first, second = nums[0], nums[1]
    if first == 0 or first >= 224:
        return False
    if first == 169 and second == 254:
        return False
    return True


def protocol_for_port(port):
    return 'https' if int(port) >= 30000 else 'http'


def command_url(host, port):
    if not is_allowed_host_port(host, port):
        return None
    name = host.strip().lower()
    return f'{protocol_for_port(port)}://{name}:{int(port)}/command'


def candidate_hosts(raw):
    host = (raw or '').strip().lower()
    if not host or host == 'localhost':
        host = '127.0.0.1'
    if host.endswith(LOVENSE_SUFFIX):
        return [host] if is_allowed_host_port(host, 30010) or is_allowed_host_port(host, 20010) else []
    if not re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', host):
        return []
    if not (is_allowed_host_port(host, 30010) or is_allowed_host_port(host, 20010)):
        return []
    return [host, host.replace('.', '-') + LOVENSE_SUFFIX]


def shared_patterns():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, 'patterns.json'),
        os.path.join(here, '..', 'shared', 'patterns.json'),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data
    return []
