"""
Vector drawing of an Xbox controller on a Tk canvas.

Everything is drawn from coordinates (no image files), so the widget scales
freely and every element can be recoloured live when it is pressed.
"""

import tkinter as tk

from core import AXIS_ACTIONS, BUTTON_ACTIONS

# Design canvas the geometry below is authored in; scaled at draw time.
BASE_W, BASE_H = 480, 340

# Colours -------------------------------------------------------------------
COL_BG = '#f5f6f8'
COL_BODY = '#e3e7ed'
COL_BODY_LINE = '#9aa4b2'
COL_BTN = '#c6cdd8'
COL_BTN_LINE = '#8c95a3'
COL_ACTIVE = '#2f7fed'
COL_ACTIVE_LINE = '#1b4fa8'
COL_TEXT = '#2b313a'
COL_TEXT_DIM = '#6b7480'
COL_LEADER = '#b6bec9'
COL_TRIGGER_FILL = '#2f7fed'

FACE_COLOURS = {
    'A': '#7cbf6b',
    'B': '#d4635f',
    'X': '#5b8fd4',
    'Y': '#dcc25c',
}

# Geometry ------------------------------------------------------------------
BODY = [
    (160, 86), (240, 98), (320, 86), (398, 100), (438, 158), (428, 223),
    (406, 290), (368, 318), (330, 290), (303, 243), (278, 214), (240, 208),
    (202, 214), (177, 243), (150, 290), (112, 318), (74, 290), (52, 223),
    (42, 158), (82, 100),
]

STICKS = {           # name: (cx, cy, outer_r, knob_r, x_axis, y_axis)
    'LThumb': (140, 158, 31, 22, 'LStickX', 'LStickY'),
    'RThumb': (285, 233, 31, 22, 'RStickX', 'RStickY'),
}

DPAD_CENTER = (200, 233)
DPAD_ARM = 31        # centre to tip
DPAD_THICK = 21      # width of the cross arms

FACE_BUTTONS = {     # name: (cx, cy, r)
    'Y': (330, 130, 15),
    'X': (302, 158, 15),
    'B': (358, 158, 15),
    'A': (330, 186, 15),
}

SMALL_BUTTONS = {    # name: (cx, cy, r)
    'Back': (203, 146, 9),
    'Start': (277, 146, 9),
}

GUIDE = (240, 124, 14)

BUMPERS = {          # name: (x1, y1, x2, y2)
    'LB': (92, 62, 172, 81),
    'RB': (308, 62, 388, 81),
}

TRIGGERS = {         # name: (x1, y1, x2, y2)
    'LT': (96, 22, 168, 56),
    'RT': (312, 22, 384, 56),
}

# Label layout: (element, side, y in base coords). Leader lines run from the
# element out to a text in the margin, like a datasheet diagram. The four
# D-Pad directions share one block so the left margin stays readable.
LABELS = [
    ('LT', 'left', 22),
    ('LB', 'left', 66),
    ('LThumb', 'left', 145),
    ('DPad', 'left', 258),
    ('RT', 'right', 22),
    ('RB', 'right', 66),
    ('Y', 'right', 112),
    ('X', 'right', 148),
    ('B', 'right', 184),
    ('A', 'right', 220),
    ('RThumb', 'right', 288),
]

# Labels that sit above the controller, with a vertical leader line
TOP_LABELS = [('Back', 138), ('Start', 342)]
TOP_LABEL_Y = -24

# Where a leader line attaches to each element (base coords)
ANCHORS = {
    'LT': (96, 39), 'LB': (92, 71),
    'RT': (384, 39), 'RB': (388, 71),
    'LThumb': (110, 148), 'RThumb': (314, 241),
    'Back': (203, 137), 'Start': (277, 137),
    'A': (345, 186), 'B': (373, 158), 'X': (302, 173), 'Y': (330, 115),
    'DPad': (169, 240),
}

DPAD_DIRS = [('DPadUp', '↑'), ('DPadDown', '↓'), ('DPadLeft', '←'), ('DPadRight', '→')]

PRETTY_NAME = {
    'LThumb': 'L-Stick', 'RThumb': 'R-Stick',
    'DPadUp': 'D-Pad ↑', 'DPadDown': 'D-Pad ↓',
    'DPadLeft': 'D-Pad ←', 'DPadRight': 'D-Pad →',
    'Back': 'Back', 'Start': 'Start',
}

# Stick elements carry both a button action (the click) and two axis actions
STICK_AXES = {'LThumb': ('LStickX', 'LStickY'), 'RThumb': ('RStickX', 'RStickY')}

BUTTON_ACTION_LABELS = dict(BUTTON_ACTIONS)
AXIS_ACTION_LABELS = dict(AXIS_ACTIONS)


def _round_rect_points(x1, y1, x2, y2, r):
    """Corner points for a rounded rectangle drawn as a smoothed polygon."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def _dpad_points(cx, cy, arm, thick):
    h = thick / 2
    return [
        cx - h, cy - arm, cx + h, cy - arm, cx + h, cy - h, cx + arm, cy - h,
        cx + arm, cy + h, cx + h, cy + h, cx + h, cy + arm, cx - h, cy + arm,
        cx - h, cy + h, cx - arm, cy + h, cx - arm, cy - h, cx - h, cy - h,
    ]


class ControllerCanvas(tk.Canvas):
    """
    Draws the controller and reflects live input.

    show_labels=True adds the datasheet-style callouts with the currently
    assigned action next to every control.
    """

    def __init__(self, parent, scale=1.0, show_labels=True, margin_left=130,
                 margin_right=130, margin_top=0, **kw):
        self.scale = scale
        self.show_labels = show_labels
        self.ml = margin_left if show_labels else 10
        self.mr = margin_right if show_labels else 10
        self.mt = margin_top if show_labels else 0
        width = int((BASE_W + self.ml + self.mr) * scale)
        height = int((BASE_H + self.mt) * scale)
        super().__init__(parent, width=width, height=height, bg=COL_BG,
                         highlightthickness=0, **kw)
        self.items = {}
        self.knobs = {}
        self.label_items = {}
        self.trigger_fills = {}
        self._active = set()
        self._emphasis = None
        self._build()

    # -- coordinate helpers -------------------------------------------------

    def _sx(self, x):
        return (x + self.ml) * self.scale

    def _sy(self, y):
        return (y + self.mt) * self.scale

    def _pts(self, flat):
        out = []
        for i in range(0, len(flat), 2):
            out.append(self._sx(flat[i]))
            out.append(self._sy(flat[i + 1]))
        return out

    def _oval(self, cx, cy, r, **kw):
        return self.create_oval(self._sx(cx - r), self._sy(cy - r),
                                self._sx(cx + r), self._sy(cy + r), **kw)

    def _font(self, size, bold=False):
        px = max(7, int(size * self.scale))
        return ('Segoe UI', px, 'bold') if bold else ('Segoe UI', px)

    # -- drawing ------------------------------------------------------------

    def _build(self):
        lw = max(1, int(1.6 * self.scale))

        # Triggers (drawn first, they sit "behind" the body top edge)
        for name, (x1, y1, x2, y2) in TRIGGERS.items():
            self.items[name] = self.create_polygon(
                self._pts(_round_rect_points(x1, y1, x2, y2, 10)),
                smooth=True, fill=COL_BTN, outline=COL_BTN_LINE, width=lw)
            # Fill bar that grows with the analog value
            self.trigger_fills[name] = self.create_rectangle(
                self._sx(x1 + 3), self._sy(y2 - 3), self._sx(x1 + 3), self._sy(y2 - 3),
                fill=COL_TRIGGER_FILL, outline='')
            self.create_text(self._sx((x1 + x2) / 2), self._sy((y1 + y2) / 2 + 8),
                             text=name, fill=COL_TEXT_DIM, font=self._font(8, True))

        for name, (x1, y1, x2, y2) in BUMPERS.items():
            self.items[name] = self.create_polygon(
                self._pts(_round_rect_points(x1, y1, x2, y2, 9)),
                smooth=True, fill=COL_BTN, outline=COL_BTN_LINE, width=lw)
            self.create_text(self._sx((x1 + x2) / 2), self._sy((y1 + y2) / 2),
                             text=name, fill=COL_TEXT_DIM, font=self._font(8, True))

        # Body
        self.create_polygon(self._pts([c for p in BODY for c in p]),
                            smooth=True, splinesteps=24,
                            fill=COL_BODY, outline=COL_BODY_LINE, width=lw)

        # Guide button
        gx, gy, gr = GUIDE
        self._oval(gx, gy, gr, fill='#f0f2f5', outline=COL_BTN_LINE, width=lw)
        self._oval(gx, gy, gr * 0.45, fill=COL_BODY_LINE, outline='')

        # D-Pad — one polygon for the cross plus four invisible arm regions
        cx, cy = DPAD_CENTER
        self.items['DPad'] = self.create_polygon(
            self._pts(_dpad_points(cx, cy, DPAD_ARM, DPAD_THICK)),
            fill=COL_BTN, outline=COL_BTN_LINE, width=lw, joinstyle='miter')
        h = DPAD_THICK / 2
        arms = {
            'DPadUp': (cx - h, cy - DPAD_ARM, cx + h, cy - h),
            'DPadDown': (cx - h, cy + h, cx + h, cy + DPAD_ARM),
            'DPadLeft': (cx - DPAD_ARM, cy - h, cx - h, cy + h),
            'DPadRight': (cx + h, cy - h, cx + DPAD_ARM, cy + h),
        }
        for name, (x1, y1, x2, y2) in arms.items():
            self.items[name] = self.create_rectangle(
                self._sx(x1), self._sy(y1), self._sx(x2), self._sy(y2),
                fill=COL_BTN, outline='')

        # Sticks
        for name, (sx, sy, outer, knob, _ax, _ay) in STICKS.items():
            self._oval(sx, sy, outer, fill='#cfd6df', outline=COL_BTN_LINE, width=lw)
            self.items[name] = self._oval(sx, sy, knob, fill=COL_BTN,
                                          outline=COL_BTN_LINE, width=lw)
            self.knobs[name] = (sx, sy, outer - knob)

        # Face buttons
        for name, (bx, by, r) in FACE_BUTTONS.items():
            self.items[name] = self._oval(bx, by, r, fill=FACE_COLOURS[name],
                                          outline=COL_BTN_LINE, width=lw)
            self.create_text(self._sx(bx), self._sy(by), text=name,
                             fill='#ffffff', font=self._font(10, True))

        # Back / Start
        for name, (bx, by, r) in SMALL_BUTTONS.items():
            self.items[name] = self._oval(bx, by, r, fill=COL_BTN,
                                          outline=COL_BTN_LINE, width=lw)

        if self.show_labels:
            self._build_labels()

    def _build_labels(self):
        lw = max(1, int(self.scale))
        for name, side, y in LABELS:
            ax, ay = ANCHORS[name]
            # The stub always approaches the text from the controller side, so
            # it never runs across a multi-line label.
            if side == 'left':
                tx, stub, anchor, justify = -14, 8, 'e', 'right'
            else:
                tx, stub, anchor, justify = BASE_W + 14, -8, 'w', 'left'
            # elbow: out to the margin, then a short horizontal stub to the text
            self.create_line(self._sx(ax), self._sy(ay),
                             self._sx(tx + stub), self._sy(y),
                             self._sx(tx), self._sy(y),
                             fill=COL_LEADER, width=lw)
            self.label_items[name] = self.create_text(
                self._sx(tx), self._sy(y), text=name, anchor=anchor,
                fill=COL_TEXT, font=self._font(9), justify=justify)

        for name, tx in TOP_LABELS:
            ax, ay = ANCHORS[name]
            self.create_line(self._sx(ax), self._sy(ay),
                             self._sx(ax), self._sy(TOP_LABEL_Y + 16),
                             self._sx(tx), self._sy(TOP_LABEL_Y + 16),
                             fill=COL_LEADER, width=lw)
            self.label_items[name] = self.create_text(
                self._sx(tx), self._sy(TOP_LABEL_Y + 12), text=name, anchor='s',
                fill=COL_TEXT, font=self._font(9), justify='center')

    # -- live updates -------------------------------------------------------

    def refresh_labels(self, cfg):
        """Show '<control> — <assigned action>' next to every element."""
        if not self.show_labels:
            return
        buttons = cfg.get('buttons', {})
        axes = cfg.get('axes', {})
        for name, item in self.label_items.items():
            pretty = PRETTY_NAME.get(name, name)
            if name == 'DPad':
                lines = ['D-Pad']
                for key, arrow in DPAD_DIRS:
                    label = BUTTON_ACTION_LABELS.get(buttons.get(key, 'none'), '—')
                    lines.append(f'{arrow} {label}')
                text = '\n'.join(lines)
            elif name in STICK_AXES:
                ax, ay = STICK_AXES[name]
                parts = []
                for axis in (ay, ax):
                    label = AXIS_ACTION_LABELS.get(axes.get(axis, 'none'), '—')
                    if label != '—':
                        parts.append(label)
                click = BUTTON_ACTION_LABELS.get(buttons.get(name, 'none'), '—')
                if click != '—':
                    parts.append(f'click: {click}')
                text = f'{pretty}\n' + ('\n'.join(parts) if parts else '—')
            elif name in ('LT', 'RT'):
                text = f'{pretty}\n{AXIS_ACTION_LABELS.get(axes.get(name, "none"), "—")}'
            else:
                text = f'{pretty}\n{BUTTON_ACTION_LABELS.get(buttons.get(name, "none"), "—")}'
            self.itemconfigure(item, text=text)

    def emphasize(self, name):
        """Highlight one element (used when its mapping row has focus)."""
        if name == self._emphasis:
            return
        self._emphasis = name
        self._repaint_idle()

    def _idle_fill(self, name):
        if name in FACE_COLOURS:
            return FACE_COLOURS[name]
        if name in self.knobs:
            return COL_BTN
        return COL_BTN

    def _repaint_idle(self):
        for name, item in self.items.items():
            if name in self._active:
                continue
            if name == self._emphasis:
                self.itemconfigure(item, fill='#ffd48a')
            else:
                self.itemconfigure(item, fill=self._idle_fill(name))

    def update_from_pad(self, pad):
        """Recolour pressed elements and move the stick knobs."""
        active = set()
        for name, item in self.items.items():
            if name == 'DPad':
                continue
            if pad.buttons.get(name, False):
                active.add(name)

        # Buttons
        for name in set(self.items) - {'DPad'}:
            item = self.items[name]
            if name in active:
                self.itemconfigure(item, fill=COL_ACTIVE, outline=COL_ACTIVE_LINE)
            else:
                outline = '' if name.startswith('DPad') else COL_BTN_LINE
                fill = '#ffd48a' if name == self._emphasis else self._idle_fill(name)
                self.itemconfigure(item, fill=fill, outline=outline)
        self._active = active

        # Triggers: fill bar proportional to travel
        for name, (x1, y1, x2, y2) in TRIGGERS.items():
            value = pad.axes.get(name, 0.0)
            top = y2 - 3 - (y2 - y1 - 6) * value
            self.coords(self.trigger_fills[name],
                        self._sx(x1 + 3), self._sy(top),
                        self._sx(x2 - 3), self._sy(y2 - 3))

        # Sticks: move the knob within its travel radius
        for name, (sx, sy, travel) in self.knobs.items():
            ax, ay = STICK_AXES[name]
            dx = pad.raw_axes.get(ax, 0.0) * travel
            dy = -pad.raw_axes.get(ay, 0.0) * travel
            _cx, _cy, _outer, knob, _a, _b = STICKS[name]
            self.coords(self.items[name],
                        self._sx(sx + dx - knob), self._sy(sy + dy - knob),
                        self._sx(sx + dx + knob), self._sy(sy + dy + knob))
