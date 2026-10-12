"""
Xbox-Controller-To-Lovense — core layer
=======================================
UI-agnostic building blocks:

  * Gamepad       — XInput polling via ctypes (all buttons, sticks, triggers)
  * LovenseClient — local Lovense Remote API client with a background sender
  * Engine        — maps controller input to device state (speed / stroke window,
                    patterns, presets) according to the configurable mapping
  * config helpers

No external dependencies, no Tk imports here.
"""

import ctypes
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'redirect blocked', headers, fp)

import lovense_action

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------


def app_dir():
    """
    Directory the config lives in: next to the .exe when frozen (PyInstaller
    unpacks to a temp dir that is deleted on exit), else next to the script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(app_dir(), 'config.json')

# Physical inputs -----------------------------------------------------------

BUTTON_NAMES = [
    'A', 'B', 'X', 'Y',
    'LB', 'RB',
    'Back', 'Start',
    'LThumb', 'RThumb',
    'DPadUp', 'DPadDown', 'DPadLeft', 'DPadRight',
]

AXIS_NAMES = ['LT', 'RT', 'LStickX', 'LStickY', 'RStickX', 'RStickY']

# Axes that only travel 0..1 (triggers); sticks are -1..1
UNIPOLAR_AXES = {'LT', 'RT'}

# Assignable actions --------------------------------------------------------

BUTTON_ACTIONS = [
    ('none', '—'),
    ('stop', 'STOP'),
    ('hold_to_run', 'Run only while held'),
    # speed
    ('speed_up', 'Speed +1'),
    ('speed_down', 'Speed -1'),
    ('speed_25', 'Speed 25%'),
    ('speed_50', 'Speed 50%'),
    ('speed_75', 'Speed 75%'),
    ('speed_100', 'Speed 100%'),
    # stroke window as a whole
    ('stroke_shift_up', 'Stroke window +5'),
    ('stroke_shift_down', 'Stroke window -5'),
    ('stroke_widen', 'Stroke wider'),
    ('stroke_narrow', 'Stroke narrower'),
    ('stroke_reset', 'Stroke reset'),
    # each end on its own
    ('stroke_min_up', 'Stroke min +5'),
    ('stroke_min_down', 'Stroke min -5'),
    ('stroke_max_up', 'Stroke max +5'),
    ('stroke_max_down', 'Stroke max -5'),
    # patterns
    ('pattern_next', 'Next pattern'),
    ('pattern_prev', 'Previous pattern'),
    ('pattern_1', 'Pattern 1'),
    ('pattern_2', 'Pattern 2'),
    ('pattern_3', 'Pattern 3'),
    ('pattern_4', 'Pattern 4'),
    ('pattern_5', 'Pattern 5'),
    ('pattern_6', 'Pattern 6'),
    ('tempo_up', 'Pattern tempo +'),
    ('tempo_down', 'Pattern tempo -'),
    # presets / modes
    ('preset_next', 'Next Lovense preset'),
    ('preset_prev', 'Previous Lovense preset'),
    ('mode_live', 'Live mode'),
]

SPEED_PRESETS = {'speed_25': 0.25, 'speed_50': 0.50, 'speed_75': 0.75, 'speed_100': 1.0}

AXIS_ACTIONS = [
    ('none', '—'),
    ('speed', 'Speed (0-max)'),
    ('stroke_shift', 'Shift stroke window'),
    ('stroke_width', 'Stroke width'),
    ('stroke_pos_abs', 'Stroke position (absolute)'),
    ('stroke_width_abs', 'Stroke width (absolute)'),
]

# Button actions that auto-repeat while held
REPEATING_ACTIONS = {
    'speed_up', 'speed_down',
    'stroke_shift_up', 'stroke_shift_down',
    'stroke_widen', 'stroke_narrow',
    'stroke_min_up', 'stroke_min_down',
    'stroke_max_up', 'stroke_max_down',
    'tempo_up', 'tempo_down',
}

LOVENSE_PRESETS = ['pulse', 'wave', 'fireworks', 'earthquake']

CONFIG_VERSION = 2

DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "lovense_ip": "127.0.0.1",
    "lovense_port": 30010,
    "controller_index": 0,
    "send_interval_ms": 150,
    "stick_deadzone": 0.25,
    "trigger_threshold": 0.05,
    "max_speed": 20,
    "stroke_min_gap": 20,
    "speed_latch": True,
    # Calibration for the motion view only — the device reports no position,
    # so the motion is reconstructed from the command against these figures.
    # Solace Pro: 3.1 in of travel (78.7 mm), up to 300 strokes per minute.
    "strokes_per_min_at_max": 300,
    "stroke_length_mm": 78.7,
    "buttons": {
        "A": "pattern_next",
        "B": "preset_next",
        "X": "pattern_prev",
        "Y": "mode_live",
        "LB": "tempo_down",
        "RB": "tempo_up",
        "Back": "none",
        "Start": "stop",
        "LThumb": "stroke_reset",
        "RThumb": "none",
        "DPadUp": "speed_up",
        "DPadDown": "speed_down",
        "DPadLeft": "stroke_narrow",
        "DPadRight": "stroke_widen",
    },
    "axes": {
        "LT": "none",
        "RT": "speed",
        "LStickX": "stroke_width",
        "LStickY": "stroke_shift",
        "RStickX": "none",
        "RStickY": "none",
    },
    "patterns": [],
}

DEFAULT_CONFIG["patterns"] = lovense_action.shared_patterns()


def _migrate(cfg, from_version):
    """
    Bring an older config up to date. Returns True if anything changed.

    v1 -> v2: D-Pad left/right used to shift the stroke window, which does
    nothing while the window spans the full 0-100 (the default). Only remap
    them if they still hold that old default, so custom mappings survive.
    """
    changed = False
    if from_version < 2:
        buttons = cfg.get('buttons', {})
        if (buttons.get('DPadLeft') == 'stroke_shift_down'
                and buttons.get('DPadRight') == 'stroke_shift_up'):
            buttons['DPadLeft'] = 'stroke_narrow'
            buttons['DPadRight'] = 'stroke_widen'
        changed = True
    cfg['config_version'] = CONFIG_VERSION
    return changed


def load_config():
    """Load config.json, filling in anything missing from the defaults."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if not os.path.exists(CONFIG_FILE):
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            user = json.load(f)
    except (OSError, ValueError):
        return cfg
    for key, value in user.items():
        if key in ('buttons', 'axes') and isinstance(value, dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    # Check the version the file was written with, not the merged default
    if _migrate(cfg, int(user.get('config_version', 1))):
        save_config(cfg)
    return cfg


def save_config(cfg):
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


# ---------------------------------------------------------------------------
# XInput
# ---------------------------------------------------------------------------

class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('wButtons', ctypes.c_ushort),
        ('bLeftTrigger', ctypes.c_ubyte),
        ('bRightTrigger', ctypes.c_ubyte),
        ('sThumbLX', ctypes.c_short),
        ('sThumbLY', ctypes.c_short),
        ('sThumbRX', ctypes.c_short),
        ('sThumbRY', ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('dwPacketNumber', ctypes.c_ulong),
        ('Gamepad', XINPUT_GAMEPAD),
    ]


BUTTON_MASKS = {
    'DPadUp': 0x0001,
    'DPadDown': 0x0002,
    'DPadLeft': 0x0004,
    'DPadRight': 0x0008,
    'Start': 0x0010,
    'Back': 0x0020,
    'LThumb': 0x0040,
    'RThumb': 0x0080,
    'LB': 0x0100,
    'RB': 0x0200,
    'A': 0x1000,
    'B': 0x2000,
    'X': 0x4000,
    'Y': 0x8000,
}


def load_xinput():
    for dll in ('xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll'):
        try:
            return ctypes.windll.LoadLibrary(dll)
        except OSError:
            continue
    return None


class Gamepad:
    """Polls one XInput controller and exposes normalized, named values."""

    def __init__(self, index=0, deadzone=0.25):
        self.xinput = load_xinput()
        self.index = int(index)
        self.deadzone = float(deadzone)
        self.connected = False
        self.buttons = {name: False for name in BUTTON_NAMES}
        self.prev_buttons = dict(self.buttons)
        self.axes = {name: 0.0 for name in AXIS_NAMES}
        self.raw_axes = dict(self.axes)   # without deadzone, for the display

    def _norm_stick(self, value):
        v = max(-1.0, value / 32767.0)
        if abs(v) < self.deadzone:
            return 0.0
        sign = 1.0 if v > 0 else -1.0
        return sign * (abs(v) - self.deadzone) / (1.0 - self.deadzone)

    def poll(self):
        """Read the controller. Returns True if the connection state changed."""
        was_connected = self.connected
        self.prev_buttons = dict(self.buttons)

        state = XINPUT_STATE()
        res = 1
        if self.xinput is not None:
            res = self.xinput.XInputGetState(self.index, ctypes.byref(state))
        self.connected = (res == 0)

        if not self.connected:
            self.buttons = {name: False for name in BUTTON_NAMES}
            self.axes = {name: 0.0 for name in AXIS_NAMES}
            self.raw_axes = dict(self.axes)
            return was_connected != self.connected

        gp = state.Gamepad
        for name, mask in BUTTON_MASKS.items():
            self.buttons[name] = bool(gp.wButtons & mask)
        self.raw_axes = {
            'LT': gp.bLeftTrigger / 255.0,
            'RT': gp.bRightTrigger / 255.0,
            'LStickX': max(-1.0, gp.sThumbLX / 32767.0),
            'LStickY': max(-1.0, gp.sThumbLY / 32767.0),
            'RStickX': max(-1.0, gp.sThumbRX / 32767.0),
            'RStickY': max(-1.0, gp.sThumbRY / 32767.0),
        }
        self.axes = {
            'LT': self.raw_axes['LT'],
            'RT': self.raw_axes['RT'],
            'LStickX': self._norm_stick(gp.sThumbLX),
            'LStickY': self._norm_stick(gp.sThumbLY),
            'RStickX': self._norm_stick(gp.sThumbRX),
            'RStickY': self._norm_stick(gp.sThumbRY),
        }
        return was_connected != self.connected

    def pressed(self, name):
        """True on the frame the button goes down (edge trigger)."""
        return self.buttons.get(name, False) and not self.prev_buttons.get(name, False)

    def held(self, name):
        return self.buttons.get(name, False)


# ---------------------------------------------------------------------------
# Lovense client
# ---------------------------------------------------------------------------

class LovenseClient:
    """
    Sends commands to the local Lovense Remote API.

    Runs its own sender thread so slow HTTP round-trips never block the input
    loop or the UI. The main loop only updates `_pending`; the thread always
    sends the *latest* desired command (intermediate states are dropped).
    """

    def __init__(self, ip, port, send_interval_ms=150):
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        self.base_url = None
        self.online = False
        self.toys = {}
        self.last_error = ''
        self._lock = threading.Condition()
        self._pending = None
        self._stop = False
        self.configure(ip, port, send_interval_ms)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def configure(self, ip, port, send_interval_ms=None):
        """Change connection settings; forces a reconnect on the next send."""
        self.ip = str(ip).strip()
        self.port = int(port)
        if send_interval_ms is not None:
            self.send_interval = float(send_interval_ms) / 1000.0
        self.base_url = None
        self.online = False

    # -- low level ----------------------------------------------------------

    def _candidate_urls(self):
        urls = []
        for host in lovense_action.candidate_hosts(self.ip):
            url = lovense_action.command_url(host, self.port)
            if url:
                urls.append(url)
        return urls

    def _post(self, url, payload, timeout=5):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or parsed.path != '/command':
            raise ValueError('Lovense URL is not allowed')
        if lovense_action.command_url(parsed.hostname, parsed.port) != url:
            raise ValueError('Lovense URL is not allowed')
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json', 'X-platform': 'XboxToLovense'},
            method='POST')
        handlers = [_NoRedirect()]
        if parsed.scheme == 'https':
            handlers.append(urllib.request.HTTPSHandler(context=self.ssl_ctx))
        opener = urllib.request.build_opener(*handlers)
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    # -- public API ---------------------------------------------------------

    def connect(self):
        """Find a reachable URL and fetch the toy list. Returns True on success."""
        last_err = 'no response'
        for url in self._candidate_urls():
            try:
                data = self._post(url, {'command': 'GetToys'})
            except Exception as exc:
                last_err = str(exc)
                continue
            code = data.get('code')
            if code == 200:
                toys = data.get('data', {}).get('toys', {})
                if isinstance(toys, str):
                    toys = json.loads(toys) if toys else {}
                self.base_url = url
                self.toys = toys
                self.online = True
                self.last_error = ''
                return True
            if code in (401, 402):
                # App reachable but no toy paired / not connected
                self.base_url = url
                self.toys = {}
                self.online = False
                self.last_error = ('No toy found — pair it in the Lovense app'
                                   if code == 401 else
                                   'Toy found but not connected (check Bluetooth)')
                return False
            last_err = f'API code {code}'
        self.base_url = None
        self.online = False
        self.toys = {}
        self.last_error = last_err
        return False

    def connect_async(self, callback=None):
        """Connect on a worker thread so the UI stays responsive."""
        def run():
            ok = self.connect()
            if callback:
                callback(ok)
        threading.Thread(target=run, daemon=True).start()

    def toy_summary(self):
        """Names and battery levels. The app omits battery for some toys, so
        only show a percentage when there actually is one."""
        parts = []
        for toy in self.toys.values():
            name = toy.get('name') or toy.get('nickName') or 'toy'
            battery = toy.get('battery')
            parts.append(f'{name} ({battery}%)' if battery not in (None, '', '-1', -1)
                         else str(name))
        return ', '.join(parts)

    def queue_function(self, action):
        """Queue a Function command (e.g. 'Thrusting:12,Stroke:20-80' or 'Stop')."""
        self._queue({'command': 'Function', 'action': action, 'timeSec': 0, 'apiVer': 1})

    def queue_preset(self, name):
        self._queue({'command': 'Preset', 'name': name, 'timeSec': 0, 'apiVer': 1})

    def stop_device(self):
        self.queue_function('Stop')

    def shutdown(self):
        with self._lock:
            self._stop = True
            self._lock.notify()
        self._thread.join(timeout=3)

    # -- worker -------------------------------------------------------------

    def _queue(self, payload):
        with self._lock:
            self._pending = payload
            self._lock.notify()

    def _worker(self):
        last_send = 0.0
        while True:
            with self._lock:
                while self._pending is None and not self._stop:
                    self._lock.wait()
                if self._stop and self._pending is None:
                    return
                payload = self._pending
                self._pending = None
            # Rate limit (Stop goes out immediately)
            wait = self.send_interval - (time.monotonic() - last_send)
            if wait > 0 and payload.get('action') != 'Stop':
                time.sleep(wait)
                with self._lock:
                    if self._pending is not None:
                        payload = self._pending
                        self._pending = None
            if not self.base_url:
                self.connect()
            if not self.base_url:
                continue
            try:
                result = self._post(self.base_url, payload)
                self.online = (result.get('code') == 200)
                if not self.online:
                    self.last_error = f'API code {result.get("code")}'
            except Exception as exc:
                self.online = False
                self.last_error = str(exc)
                self.base_url = None      # force rediscovery next time
            last_send = time.monotonic()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

MODE_STOPPED = 'STOPPED'
MODE_LIVE = 'LIVE'
MODE_PATTERN = 'PATTERN'
MODE_PRESET = 'PRESET'

SHIFT_RATE = 60.0   # stroke units per second at full stick deflection
WIDTH_RATE = 50.0


class Engine:
    """
    Turns controller input into device state. UI-agnostic: the GUI polls the
    public attributes for display and calls update() every frame.
    """

    def __init__(self, cfg, client, log=None):
        self.client = client
        self.log = log or (lambda msg: None)
        self.apply_config(cfg)

        self.mode = MODE_STOPPED
        self.speed = 0.0
        self.stroke_min = 0.0
        self.stroke_max = 100.0

        self.pattern_idx = 0
        self.step_idx = 0
        self.step_started = 0.0
        self.tempo = 1.0
        self.preset_idx = 0

        self.repeat_at = {}
        self.last_action_sent = None
        self.hold_active = False      # deadman switch currently held?
        self.hold_speed = 0.0         # speed to resume with when it is pressed

    # -- config -------------------------------------------------------------

    def apply_config(self, cfg):
        self.cfg = cfg
        self.max_speed = int(cfg.get('max_speed', 20))
        self.min_gap = int(cfg.get('stroke_min_gap', 20))
        self.trigger_threshold = float(cfg.get('trigger_threshold', 0.05))
        self.speed_latch = bool(cfg.get('speed_latch', True))
        self.button_map = dict(cfg.get('buttons', {}))
        self.axis_map = dict(cfg.get('axes', {}))
        self.patterns = cfg.get('patterns') or []

    # -- device state -------------------------------------------------------

    def action_string(self):
        return lovense_action.build_thrust_action(self.speed, self.stroke_min, self.stroke_max, self.min_gap)

    def push_device_state(self, force=False):
        action = self.action_string()
        if force or action != self.last_action_sent:
            self.client.queue_function(action)
            self.last_action_sent = action

    def clamp_stroke(self):
        self.stroke_min = max(0.0, min(100.0 - self.min_gap, self.stroke_min))
        self.stroke_max = max(self.stroke_min + self.min_gap, min(100.0, self.stroke_max))

    def shift_stroke(self, delta):
        """Move the whole window, keeping its width when hitting 0/100."""
        width = self.stroke_max - self.stroke_min
        lo = max(0.0, min(100.0 - width, self.stroke_min + delta))
        self.stroke_min = lo
        self.stroke_max = lo + width

    def change_width(self, delta):
        center = (self.stroke_min + self.stroke_max) / 2
        width = max(self.min_gap, min(100.0, (self.stroke_max - self.stroke_min) + delta))
        self.stroke_min = center - width / 2
        self.stroke_max = center + width / 2
        self.clamp_stroke()

    def move_min(self, delta):
        """Move only the retracted end, keeping the minimum gap."""
        self.stroke_min = max(0.0, min(self.stroke_max - self.min_gap,
                                       self.stroke_min + delta))

    def move_max(self, delta):
        """Move only the deep end, keeping the minimum gap."""
        self.stroke_max = min(100.0, max(self.stroke_min + self.min_gap,
                                         self.stroke_max + delta))

    def _stroke_step(self, kind, delta):
        """
        Apply a stroke change and say so when it cannot move — shifting a
        window that already spans 0-100 has nowhere to go, which otherwise
        just looks like a dead button.
        """
        before = (round(self.stroke_min, 2), round(self.stroke_max, 2))
        {'shift': self.shift_stroke, 'width': self.change_width,
         'min': self.move_min, 'max': self.move_max}[kind](delta)
        if (round(self.stroke_min, 2), round(self.stroke_max, 2)) != before:
            return
        lo, hi = int(round(before[0])), int(round(before[1]))
        if kind == 'shift':
            reason = (f'window {lo}-{hi} spans the full range — narrow it first'
                      if hi - lo >= 100 else
                      f'window {lo}-{hi} is already at the {"top" if delta > 0 else "bottom"}')
        elif kind == 'width':
            reason = (f'window {lo}-{hi} is already at maximum width' if delta > 0 else
                      f'window {lo}-{hi} is already at the minimum gap of {self.min_gap}')
        elif kind == 'min':
            reason = (f'min {lo} is already {self.min_gap} below max {hi}' if delta > 0
                      else 'min is already at 0')
        else:
            reason = ('max is already at 100' if delta > 0 else
                      f'max {hi} is already {self.min_gap} above min {lo}')
        self.log(f'No change: {reason}')

    # -- modes --------------------------------------------------------------

    def enter_live(self, announce=True):
        self.mode = MODE_LIVE
        if announce:
            self.log('Live mode')
        self.push_device_state(force=True)

    def enter_pattern(self, idx):
        if not self.patterns:
            self.log('No patterns defined')
            return
        self.pattern_idx = idx % len(self.patterns)
        self.mode = MODE_PATTERN
        self.step_idx = 0
        self.step_started = time.monotonic()
        name = self.patterns[self.pattern_idx].get('name', '?')
        self.log(f'Pattern "{name}" ({self.pattern_idx + 1}/{len(self.patterns)})')
        self.apply_pattern_step(force=True)

    def enter_preset(self, idx):
        self.preset_idx = idx % len(LOVENSE_PRESETS)
        self.mode = MODE_PRESET
        name = LOVENSE_PRESETS[self.preset_idx]
        self.client.queue_preset(name)
        self.last_action_sent = None    # device no longer matches our Function state
        self.log(f'Preset "{name}"')

    def enter_stopped(self, announce=True):
        self.mode = MODE_STOPPED
        self.speed = 0.0
        self.client.stop_device()
        self.last_action_sent = 'Stop'
        if announce:
            self.log('Stopped')

    # -- pattern engine -----------------------------------------------------

    def current_pattern(self):
        if not self.patterns:
            return None
        return self.patterns[self.pattern_idx % len(self.patterns)]

    def apply_pattern_step(self, force=False):
        p = self.current_pattern()
        if not p or not p.get('steps'):
            return
        step = p['steps'][self.step_idx % len(p['steps'])]
        self.speed = float(step.get('speed', 0))
        stroke = step.get('stroke', [0, 100])
        self.stroke_min = float(stroke[0])
        self.stroke_max = float(stroke[1])
        self.clamp_stroke()
        self.push_device_state(force=force)

    def tick_pattern(self):
        p = self.current_pattern()
        if not p or not p.get('steps'):
            return
        step = p['steps'][self.step_idx % len(p['steps'])]
        duration = float(step.get('sec', 3)) / max(0.25, self.tempo)
        if time.monotonic() - self.step_started >= duration:
            self.step_idx = (self.step_idx + 1) % len(p['steps'])
            self.step_started = time.monotonic()
            self.apply_pattern_step()

    # -- input --------------------------------------------------------------

    def _repeat(self, pad, name, action):
        """Edge trigger, plus auto-repeat (400ms delay, then every 180ms)."""
        now = time.monotonic()
        if pad.pressed(name):
            self.repeat_at[name] = now + 0.4
            return True
        if action in REPEATING_ACTIONS and pad.held(name):
            if now >= self.repeat_at.get(name, float('inf')):
                self.repeat_at[name] = now + 0.18
                return True
        if not pad.held(name):
            self.repeat_at.pop(name, None)
        return False

    def do_action(self, action):
        """Run one button action. Also usable from the GUI (buttons/hotkeys)."""
        if action == 'stop':
            self.enter_stopped()
        elif action == 'speed_up':
            self.speed = min(self.max_speed, int(round(self.speed)) + 1)
            if self.mode == MODE_STOPPED and self.speed > 0:
                self.enter_live(announce=False)
        elif action == 'speed_down':
            self.speed = max(0, int(round(self.speed)) - 1)
        elif action in ('stroke_shift_up', 'stroke_shift_down'):
            self._stroke_step('shift', 5 if action == 'stroke_shift_up' else -5)
        elif action in ('stroke_widen', 'stroke_narrow'):
            self._stroke_step('width', 10 if action == 'stroke_widen' else -10)
        elif action in ('stroke_min_up', 'stroke_min_down'):
            self._stroke_step('min', 5 if action == 'stroke_min_up' else -5)
        elif action in ('stroke_max_up', 'stroke_max_down'):
            self._stroke_step('max', 5 if action == 'stroke_max_up' else -5)
        elif action in SPEED_PRESETS:
            self.speed = SPEED_PRESETS[action] * self.max_speed
            if self.mode != MODE_LIVE:
                self.enter_live(announce=False)
            self.log(f'Speed {int(round(self.speed))}/{self.max_speed}')
        elif action.startswith('pattern_') and action[8:].isdigit():
            idx = int(action[8:]) - 1
            if 0 <= idx < len(self.patterns):
                self.enter_pattern(idx)
            else:
                self.log(f'No pattern {idx + 1} — only {len(self.patterns)} defined')
        elif action == 'stroke_reset':
            self.stroke_min, self.stroke_max = 0.0, 100.0
        elif action == 'pattern_next':
            self.enter_pattern(self.pattern_idx + 1 if self.mode == MODE_PATTERN
                               else self.pattern_idx)
        elif action == 'pattern_prev':
            self.enter_pattern(self.pattern_idx - 1 if self.mode == MODE_PATTERN
                               else self.pattern_idx)
        elif action == 'tempo_up':
            self.tempo = min(3.0, round(self.tempo + 0.1, 2))
        elif action == 'tempo_down':
            self.tempo = max(0.3, round(self.tempo - 0.1, 2))
        elif action == 'preset_next':
            self.enter_preset(self.preset_idx + 1 if self.mode == MODE_PRESET
                              else self.preset_idx)
        elif action == 'preset_prev':
            self.enter_preset(self.preset_idx - 1 if self.mode == MODE_PRESET
                              else self.preset_idx)
        elif action == 'mode_live':
            self.enter_live()

    def update(self, pad, dt):
        """Poll-driven update; call once per frame with the elapsed time."""
        if not pad.connected:
            if self.mode != MODE_STOPPED:
                self.enter_stopped(announce=False)
                self.log('Controller disconnected — stopped')
            return

        # ---- deadman switch ----
        # If any button is mapped to hold_to_run it gates everything: the
        # device only runs while it is held, and every other input is ignored
        # while it is released.
        gates = [n for n, a in self.button_map.items() if a == 'hold_to_run']
        if gates:
            held = any(pad.held(n) for n in gates)
            if held != self.hold_active:
                self.hold_active = held
                if held:
                    self.speed = self.hold_speed or (self.max_speed / 2)
                    self.enter_live(announce=False)
                    self.log(f'Held — running at {int(round(self.speed))}')
                else:
                    self.hold_speed = self.speed
                    self.enter_stopped(announce=False)
                    self.log('Released — stopped')
            if not held:
                return

        # ---- buttons ----
        for name in BUTTON_NAMES:
            action = self.button_map.get(name, 'none')
            if action in ('none', 'hold_to_run'):
                continue
            if self._repeat(pad, name, action):
                self.do_action(action)

        # ---- axes ----
        for name in AXIS_NAMES:
            action = self.axis_map.get(name, 'none')
            if action == 'none':
                continue
            value = pad.axes.get(name, 0.0)
            unipolar = name in UNIPOLAR_AXES

            if action == 'speed':
                magnitude = value if unipolar else abs(value)
                if magnitude > self.trigger_threshold:
                    if self.mode != MODE_LIVE:
                        self.enter_live(announce=(self.mode != MODE_STOPPED))
                    self.speed = magnitude * self.max_speed
                elif not self.speed_latch and self.mode == MODE_LIVE:
                    self.speed = 0.0
            elif action == 'stroke_shift':
                if value:
                    self.shift_stroke(value * SHIFT_RATE * dt)
            elif action == 'stroke_width':
                if value:
                    self.change_width(value * WIDTH_RATE * dt)
            elif action == 'stroke_pos_abs':
                pos = value if unipolar else (value + 1.0) / 2.0
                width = self.stroke_max - self.stroke_min
                self.stroke_min = pos * (100.0 - width)
                self.stroke_max = self.stroke_min + width
                self.clamp_stroke()
            elif action == 'stroke_width_abs':
                pos = value if unipolar else (value + 1.0) / 2.0
                width = self.min_gap + pos * (100.0 - self.min_gap)
                center = (self.stroke_min + self.stroke_max) / 2
                self.stroke_min = center - width / 2
                self.stroke_max = center + width / 2
                self.clamp_stroke()

        # ---- push ----
        if self.mode == MODE_LIVE:
            self.push_device_state()
        elif self.mode == MODE_PATTERN:
            self.tick_pattern()
