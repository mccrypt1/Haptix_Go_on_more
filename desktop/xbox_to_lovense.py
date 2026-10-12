#!/usr/bin/env python3
"""
Xbox-Controller-To-Lovense — GUI
================================
Tk window that shows the controller live, lets every control be reassigned
like a gamepad mapper, and edits the stroke patterns.

Run:  python xbox_to_lovense.py      (or build XboxToLovense.exe, see README)
"""

import time
import tkinter as tk
from tkinter import messagebox, ttk

import core
from controller_canvas import ControllerCanvas
from stroke_visual import StrokeVisualizer

POLL_MS = 16          # ~60 Hz input polling
TOY_REFRESH_S = 30    # battery / toy list refresh

# Mapping tab rows: (display name, kind, config key, canvas element)
LEFT_ROWS = [
    ('Left Trigger (LT)', 'axis', 'LT', 'LT'),
    ('Left Bumper (LB)', 'button', 'LB', 'LB'),
    ('Back', 'button', 'Back', 'Back'),
    ('L-Stick  ↕', 'axis', 'LStickY', 'LThumb'),
    ('L-Stick  ↔', 'axis', 'LStickX', 'LThumb'),
    ('L-Stick  click', 'button', 'LThumb', 'LThumb'),
    ('D-Pad  ↑', 'button', 'DPadUp', 'DPadUp'),
    ('D-Pad  ↓', 'button', 'DPadDown', 'DPadDown'),
    ('D-Pad  ←', 'button', 'DPadLeft', 'DPadLeft'),
    ('D-Pad  →', 'button', 'DPadRight', 'DPadRight'),
]

RIGHT_ROWS = [
    ('Right Trigger (RT)', 'axis', 'RT', 'RT'),
    ('Right Bumper (RB)', 'button', 'RB', 'RB'),
    ('Start', 'button', 'Start', 'Start'),
    ('R-Stick  ↕', 'axis', 'RStickY', 'RThumb'),
    ('R-Stick  ↔', 'axis', 'RStickX', 'RThumb'),
    ('R-Stick  click', 'button', 'RThumb', 'RThumb'),
    ('A Button', 'button', 'A', 'A'),
    ('B Button', 'button', 'B', 'B'),
    ('X Button', 'button', 'X', 'X'),
    ('Y Button', 'button', 'Y', 'Y'),
]

BUTTON_LABELS = [label for _id, label in core.BUTTON_ACTIONS]
AXIS_LABELS = [label for _id, label in core.AXIS_ACTIONS]
BUTTON_BY_LABEL = {label: _id for _id, label in core.BUTTON_ACTIONS}
AXIS_BY_LABEL = {label: _id for _id, label in core.AXIS_ACTIONS}
BUTTON_BY_ID = dict(core.BUTTON_ACTIONS)
AXIS_BY_ID = dict(core.AXIS_ACTIONS)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Xbox-Controller-To-Lovense')
        self.geometry('1340x720')
        self.minsize(1180, 660)
        self.configure(bg='#f5f6f8')

        self.cfg = core.load_config()
        self.client = core.LovenseClient(
            self.cfg['lovense_ip'], self.cfg['lovense_port'], self.cfg['send_interval_ms'])
        self.engine = core.Engine(self.cfg, self.client, log=self.log)
        self.pad = core.Gamepad(self.cfg['controller_index'], self.cfg['stick_deadzone'])

        self._last_frame = time.monotonic()
        self._last_toy_refresh = 0.0
        self._pad_was_connected = False

        self._build_style()
        self._build_ui()

        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(POLL_MS, self._tick)
        self.reconnect()

    # -- styling -------------------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('.', font=('Segoe UI', 9))
        style.configure('Head.TLabel', font=('Segoe UI', 11, 'bold'))
        style.configure('Sub.TLabel', foreground='#6b7480')
        style.configure('Stop.TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('Sig.TLabel', foreground='#6b7480', font=('Segoe UI', 9, 'italic'))
        style.configure('Value.TLabel', font=('Consolas', 11))

    # -- layout --------------------------------------------------------------

    def _build_ui(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=8, pady=(8, 4))

        self.tab_control = ttk.Frame(self.nb, padding=8)
        self.tab_mapping = ttk.Frame(self.nb, padding=8)
        self.tab_patterns = ttk.Frame(self.nb, padding=8)
        self.tab_settings = ttk.Frame(self.nb, padding=8)
        self.nb.add(self.tab_control, text='  Control  ')
        self.nb.add(self.tab_mapping, text='  Mapping  ')
        self.nb.add(self.tab_patterns, text='  Patterns  ')
        self.nb.add(self.tab_settings, text='  Settings  ')

        self._build_control_tab()
        self._build_mapping_tab()
        self._build_patterns_tab()
        self._build_settings_tab()
        self._build_statusbar()

        self.canvas_control.refresh_labels(self.cfg)

    # ---- Control tab -------------------------------------------------------

    def _build_control_tab(self):
        right = ttk.Frame(self.tab_control, width=270)
        right.pack(side='right', fill='y', padx=(12, 0))
        right.pack_propagate(False)
        mid = ttk.Frame(self.tab_control, width=222)
        mid.pack(side='right', fill='y', padx=(8, 0))
        mid.pack_propagate(False)
        left = ttk.Frame(self.tab_control)
        left.pack(side='left', fill='both', expand=True)

        self.canvas_control = ControllerCanvas(left, scale=0.95, show_labels=True,
                                               margin_left=182, margin_right=148,
                                               margin_top=44)
        self.canvas_control.pack(anchor='n')

        self.stroke_view = StrokeVisualizer(mid, width=222, relief='solid', borderwidth=1)
        self.stroke_view.pack(fill='both', expand=True)

        # Live readout under the controller, full width
        ttk.Label(left, text='Speed').pack(anchor='w', pady=(10, 0))
        self.bar_speed = tk.Canvas(left, height=26, bg='#e9ecf1', highlightthickness=1,
                                   highlightbackground='#c3cbd6')
        self.bar_speed.pack(fill='x', pady=(2, 8))
        ttk.Label(left, text='Stroke window  (0 = fully retracted, 100 = fully extended)').pack(anchor='w')
        self.bar_stroke = tk.Canvas(left, height=46, bg='#e9ecf1', highlightthickness=1,
                                    highlightbackground='#c3cbd6')
        self.bar_stroke.pack(fill='x', pady=(2, 0))
        ttk.Frame(left).pack(fill='both', expand=True)   # absorbs extra height

        ttk.Label(right, text='Device state', style='Head.TLabel').pack(anchor='w')
        ttk.Separator(right).pack(fill='x', pady=(2, 8))
        self.lbl_mode = ttk.Label(right, text='STOPPED', font=('Segoe UI', 15, 'bold'))
        self.lbl_mode.pack(anchor='w')
        self.lbl_mode_detail = ttk.Label(right, text='', style='Sub.TLabel', wraplength=270)
        self.lbl_mode_detail.pack(anchor='w', pady=(0, 12))

        ttk.Button(right, text='STOP', style='Stop.TButton',
                   command=lambda: self.engine.do_action('stop')).pack(fill='x', pady=(0, 12))

        ttk.Label(right, text='Activity', style='Head.TLabel').pack(anchor='w')
        ttk.Separator(right).pack(fill='x', pady=(2, 4))
        self.log_box = tk.Text(right, height=10, width=32, state='disabled',
                               font=('Consolas', 8), bg='#ffffff', relief='solid',
                               borderwidth=1, wrap='none')
        self.log_box.pack(fill='both', expand=True)

    def _draw_speed_bar(self):
        c = self.bar_speed
        c.delete('all')
        w = c.winfo_width() or 280
        h = int(c['height'])
        frac = self.engine.speed / max(1, self.engine.max_speed)
        c.create_rectangle(0, 0, w * frac, h, fill='#2f7fed', outline='')
        c.create_text(w - 6, h / 2, anchor='e', font=('Consolas', 9),
                      text=f'{int(round(self.engine.speed))} / {self.engine.max_speed}')

    def _draw_stroke_bar(self):
        c = self.bar_stroke
        c.delete('all')
        w = c.winfo_width() or 280
        h = c.winfo_height() or 40
        lo = self.engine.stroke_min / 100.0
        hi = self.engine.stroke_max / 100.0
        pad = max(3, h * 0.12)
        for i in range(1, 10):
            c.create_line(w * i / 10, 0, w * i / 10, h, fill='#d3d9e1', dash=(2, 3))
        c.create_rectangle(w * lo, pad, w * hi, h - pad, fill='#7cbf6b', outline='#4d8f3f')
        c.create_text(w / 2, h / 2, font=('Consolas', 10),
                      text=f'{int(round(self.engine.stroke_min))} – '
                           f'{int(round(self.engine.stroke_max))}')

    # ---- Mapping tab -------------------------------------------------------

    def _build_mapping_tab(self):
        head = ttk.Frame(self.tab_mapping)
        head.pack(fill='x')
        ttk.Label(head, text='Assign a function to every control',
                  style='Head.TLabel').pack(side='left')
        ttk.Button(head, text='Restore defaults',
                   command=self.restore_default_mapping).pack(side='right')
        ttk.Separator(self.tab_mapping).pack(fill='x', pady=(4, 8))

        body = ttk.Frame(self.tab_mapping)
        body.pack(fill='both', expand=True)

        col_l = ttk.Frame(body)
        col_l.pack(side='left', anchor='n')
        mid = ttk.Frame(body)
        mid.pack(side='left', anchor='n', padx=12)
        col_r = ttk.Frame(body)
        col_r.pack(side='left', anchor='n')

        self.canvas_mapping = ControllerCanvas(mid, scale=0.66, show_labels=False)
        self.canvas_mapping.pack()
        ttk.Label(mid, text='Highlighted: the control you are editing',
                  style='Sub.TLabel').pack(pady=(6, 0))

        self.map_widgets = {}
        for parent, rows, side in ((col_l, LEFT_ROWS, 'e'), (col_r, RIGHT_ROWS, 'w')):
            for display, kind, key, element in rows:
                row = ttk.Frame(parent)
                row.pack(fill='x', pady=3)
                if side == 'e':
                    ttk.Label(row, text=display, width=17, anchor='e').pack(side='left')
                combo = ttk.Combobox(row, state='readonly', width=24,
                                     values=AXIS_LABELS if kind == 'axis' else BUTTON_LABELS)
                combo.pack(side='left', padx=6)
                if side == 'w':
                    ttk.Label(row, text=display, width=17, anchor='w').pack(side='left')
                combo.bind('<<ComboboxSelected>>',
                           lambda _e, k=kind, key=key, c=combo: self.on_map_changed(k, key, c))
                combo.bind('<Enter>', lambda _e, el=element: self.canvas_mapping.emphasize(el))
                combo.bind('<FocusIn>', lambda _e, el=element: self.canvas_mapping.emphasize(el))
                combo.bind('<Leave>', lambda _e: self.canvas_mapping.emphasize(None))
                self.map_widgets[key] = (kind, combo)
        self.refresh_mapping_widgets()

    def refresh_mapping_widgets(self):
        for key, (kind, combo) in self.map_widgets.items():
            if kind == 'axis':
                action = self.cfg['axes'].get(key, 'none')
                combo.set(AXIS_BY_ID.get(action, '—'))
            else:
                action = self.cfg['buttons'].get(key, 'none')
                combo.set(BUTTON_BY_ID.get(action, '—'))

    def on_map_changed(self, kind, key, combo):
        label = combo.get()
        if kind == 'axis':
            self.cfg['axes'][key] = AXIS_BY_LABEL.get(label, 'none')
        else:
            self.cfg['buttons'][key] = BUTTON_BY_LABEL.get(label, 'none')
        self.engine.apply_config(self.cfg)
        self.canvas_control.refresh_labels(self.cfg)
        core.save_config(self.cfg)
        self.log(f'{key} → {label}')

    def restore_default_mapping(self):
        self.cfg['buttons'] = dict(core.DEFAULT_CONFIG['buttons'])
        self.cfg['axes'] = dict(core.DEFAULT_CONFIG['axes'])
        self.engine.apply_config(self.cfg)
        self.refresh_mapping_widgets()
        self.canvas_control.refresh_labels(self.cfg)
        core.save_config(self.cfg)
        self.log('Mapping restored to defaults')

    # ---- Patterns tab ------------------------------------------------------

    def _build_patterns_tab(self):
        left = ttk.Frame(self.tab_patterns, width=210)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        right = ttk.Frame(self.tab_patterns)
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        ttk.Label(left, text='Patterns', style='Head.TLabel').pack(anchor='w')
        ttk.Separator(left).pack(fill='x', pady=(2, 6))
        self.pattern_list = tk.Listbox(left, exportselection=False, font=('Segoe UI', 9),
                                       activestyle='none')
        self.pattern_list.pack(fill='both', expand=True)
        self.pattern_list.bind('<<ListboxSelect>>', lambda _e: self.on_pattern_selected())

        pb = ttk.Frame(left)
        pb.pack(fill='x', pady=6)
        ttk.Button(pb, text='New', width=8, command=self.pattern_new).pack(side='left')
        ttk.Button(pb, text='Copy', width=8, command=self.pattern_copy).pack(side='left', padx=4)
        ttk.Button(pb, text='Delete', width=8, command=self.pattern_delete).pack(side='left')

        nm = ttk.Frame(left)
        nm.pack(fill='x')
        ttk.Label(nm, text='Name').pack(side='left')
        self.var_pattern_name = tk.StringVar()
        ttk.Entry(nm, textvariable=self.var_pattern_name).pack(side='left', fill='x',
                                                               expand=True, padx=(6, 0))
        ttk.Button(left, text='Rename', command=self.pattern_rename).pack(fill='x', pady=(4, 0))
        ttk.Button(left, text='▶  Play this pattern',
                   command=self.pattern_play).pack(fill='x', pady=(10, 0))

        ttk.Label(right, text='Steps', style='Head.TLabel').pack(anchor='w')
        ttk.Separator(right).pack(fill='x', pady=(2, 6))
        cols = ('idx', 'speed', 'min', 'max', 'sec')
        self.step_tree = ttk.Treeview(right, columns=cols, show='headings', height=12)
        for col, text, width in (('idx', '#', 40), ('speed', 'Speed', 70),
                                 ('min', 'Stroke min', 90), ('max', 'Stroke max', 90),
                                 ('sec', 'Seconds', 80)):
            self.step_tree.heading(col, text=text)
            self.step_tree.column(col, width=width, anchor='center')
        self.step_tree.pack(fill='both', expand=True)
        self.step_tree.bind('<<TreeviewSelect>>', lambda _e: self.on_step_selected())

        ed = ttk.LabelFrame(right, text='Selected step', padding=8)
        ed.pack(fill='x', pady=8)
        self.var_speed = tk.StringVar(value='10')
        self.var_min = tk.StringVar(value='0')
        self.var_max = tk.StringVar(value='100')
        self.var_sec = tk.StringVar(value='3')
        for i, (label, var) in enumerate((('Speed (0-20)', self.var_speed),
                                          ('Stroke min', self.var_min),
                                          ('Stroke max', self.var_max),
                                          ('Seconds', self.var_sec))):
            ttk.Label(ed, text=label).grid(row=0, column=i * 2, padx=(0 if i == 0 else 10, 4))
            ttk.Entry(ed, textvariable=var, width=7).grid(row=0, column=i * 2 + 1)

        sb = ttk.Frame(right)
        sb.pack(fill='x')
        ttk.Button(sb, text='Add step', command=self.step_add).pack(side='left')
        ttk.Button(sb, text='Apply to selected', command=self.step_apply).pack(side='left', padx=4)
        ttk.Button(sb, text='Delete step', command=self.step_delete).pack(side='left')
        ttk.Button(sb, text='▲', width=3, command=lambda: self.step_move(-1)).pack(side='left', padx=(10, 2))
        ttk.Button(sb, text='▼', width=3, command=lambda: self.step_move(1)).pack(side='left')
        ttk.Label(right, text='Speed 0 = pause. Stroke min/max are 0-100, '
                              'the gap must be at least the configured minimum.',
                  style='Sub.TLabel').pack(anchor='w', pady=(8, 0))

        self.refresh_pattern_list()

    def refresh_pattern_list(self, select=0):
        self.pattern_list.delete(0, 'end')
        for p in self.cfg['patterns']:
            self.pattern_list.insert('end', p.get('name', 'unnamed'))
        if self.cfg['patterns']:
            idx = max(0, min(select, len(self.cfg['patterns']) - 1))
            self.pattern_list.selection_set(idx)
            self.on_pattern_selected()

    def selected_pattern_index(self):
        sel = self.pattern_list.curselection()
        return sel[0] if sel else None

    def on_pattern_selected(self):
        idx = self.selected_pattern_index()
        if idx is None:
            return
        pattern = self.cfg['patterns'][idx]
        self.var_pattern_name.set(pattern.get('name', ''))
        self.refresh_step_tree()

    def refresh_step_tree(self):
        self.step_tree.delete(*self.step_tree.get_children())
        idx = self.selected_pattern_index()
        if idx is None:
            return
        for i, step in enumerate(self.cfg['patterns'][idx].get('steps', [])):
            stroke = step.get('stroke', [0, 100])
            self.step_tree.insert('', 'end', iid=str(i), values=(
                i + 1, step.get('speed', 0), stroke[0], stroke[1], step.get('sec', 3)))

    def on_step_selected(self):
        pidx = self.selected_pattern_index()
        sel = self.step_tree.selection()
        if pidx is None or not sel:
            return
        step = self.cfg['patterns'][pidx]['steps'][int(sel[0])]
        stroke = step.get('stroke', [0, 100])
        self.var_speed.set(str(step.get('speed', 0)))
        self.var_min.set(str(stroke[0]))
        self.var_max.set(str(stroke[1]))
        self.var_sec.set(str(step.get('sec', 3)))

    def _read_step_fields(self):
        try:
            speed = max(0, min(self.engine.max_speed, int(float(self.var_speed.get()))))
            lo = max(0, min(100, int(float(self.var_min.get()))))
            hi = max(0, min(100, int(float(self.var_max.get()))))
            sec = max(0.1, float(self.var_sec.get()))
        except ValueError:
            messagebox.showerror('Invalid step', 'Speed, stroke and seconds must be numbers.')
            return None
        if hi - lo < self.engine.min_gap:
            hi = min(100, lo + self.engine.min_gap)
            if hi - lo < self.engine.min_gap:
                lo = hi - self.engine.min_gap
            self.var_min.set(str(lo))
            self.var_max.set(str(hi))
        return {'speed': speed, 'stroke': [lo, hi], 'sec': sec}

    def step_add(self):
        pidx = self.selected_pattern_index()
        step = self._read_step_fields()
        if pidx is None or step is None:
            return
        self.cfg['patterns'][pidx].setdefault('steps', []).append(step)
        self.save_patterns()
        self.refresh_step_tree()

    def step_apply(self):
        pidx = self.selected_pattern_index()
        sel = self.step_tree.selection()
        step = self._read_step_fields()
        if pidx is None or not sel or step is None:
            return
        self.cfg['patterns'][pidx]['steps'][int(sel[0])] = step
        self.save_patterns()
        self.refresh_step_tree()
        self.step_tree.selection_set(sel[0])

    def step_delete(self):
        pidx = self.selected_pattern_index()
        sel = self.step_tree.selection()
        if pidx is None or not sel:
            return
        steps = self.cfg['patterns'][pidx]['steps']
        if len(steps) <= 1:
            messagebox.showinfo('Steps', 'A pattern needs at least one step.')
            return
        del steps[int(sel[0])]
        self.save_patterns()
        self.refresh_step_tree()

    def step_move(self, delta):
        pidx = self.selected_pattern_index()
        sel = self.step_tree.selection()
        if pidx is None or not sel:
            return
        steps = self.cfg['patterns'][pidx]['steps']
        i = int(sel[0])
        j = i + delta
        if not 0 <= j < len(steps):
            return
        steps[i], steps[j] = steps[j], steps[i]
        self.save_patterns()
        self.refresh_step_tree()
        self.step_tree.selection_set(str(j))

    def pattern_new(self):
        self.cfg['patterns'].append(
            {'name': 'New pattern', 'steps': [{'speed': 8, 'stroke': [0, 100], 'sec': 3}]})
        self.save_patterns()
        self.refresh_pattern_list(select=len(self.cfg['patterns']) - 1)

    def pattern_copy(self):
        idx = self.selected_pattern_index()
        if idx is None:
            return
        src = self.cfg['patterns'][idx]
        copy = {'name': src.get('name', 'pattern') + ' copy',
                'steps': [dict(s, stroke=list(s.get('stroke', [0, 100])))
                          for s in src.get('steps', [])]}
        self.cfg['patterns'].insert(idx + 1, copy)
        self.save_patterns()
        self.refresh_pattern_list(select=idx + 1)

    def pattern_delete(self):
        idx = self.selected_pattern_index()
        if idx is None:
            return
        if len(self.cfg['patterns']) <= 1:
            messagebox.showinfo('Patterns', 'Keep at least one pattern.')
            return
        name = self.cfg['patterns'][idx].get('name', '')
        if not messagebox.askyesno('Delete pattern', f'Delete "{name}"?'):
            return
        del self.cfg['patterns'][idx]
        self.save_patterns()
        self.refresh_pattern_list(select=max(0, idx - 1))

    def pattern_rename(self):
        idx = self.selected_pattern_index()
        if idx is None:
            return
        self.cfg['patterns'][idx]['name'] = self.var_pattern_name.get().strip() or 'unnamed'
        self.save_patterns()
        self.refresh_pattern_list(select=idx)

    def pattern_play(self):
        idx = self.selected_pattern_index()
        if idx is None:
            return
        self.engine.enter_pattern(idx)

    def save_patterns(self):
        self.engine.apply_config(self.cfg)
        core.save_config(self.cfg)

    # ---- Settings tab ------------------------------------------------------

    def _build_settings_tab(self):
        conn = ttk.LabelFrame(self.tab_settings, text='Lovense connection', padding=10)
        conn.pack(fill='x')
        self.var_ip = tk.StringVar(value=str(self.cfg['lovense_ip']))
        self.var_port = tk.StringVar(value=str(self.cfg['lovense_port']))
        ttk.Label(conn, text='IP address').grid(row=0, column=0, sticky='w')
        ttk.Entry(conn, textvariable=self.var_ip, width=18).grid(row=0, column=1, padx=6)
        ttk.Label(conn, text='Port').grid(row=0, column=2, sticky='w', padx=(12, 0))
        ttk.Entry(conn, textvariable=self.var_port, width=8).grid(row=0, column=3, padx=6)
        ttk.Button(conn, text='Apply & reconnect',
                   command=self.apply_settings).grid(row=0, column=4, padx=(12, 0))
        ttk.Label(conn, text='30010 = HTTPS (PC app), 20010 = HTTP. The port is shown in '
                             'the Lovense app under Game Mode.',
                  style='Sub.TLabel').grid(row=1, column=0, columnspan=5, sticky='w', pady=(6, 0))

        tune = ttk.LabelFrame(self.tab_settings, text='Input & device tuning', padding=10)
        tune.pack(fill='x', pady=10)
        self.var_index = tk.StringVar(value=str(self.cfg['controller_index']))
        self.var_interval = tk.StringVar(value=str(self.cfg['send_interval_ms']))
        self.var_deadzone = tk.StringVar(value=str(self.cfg['stick_deadzone']))
        self.var_threshold = tk.StringVar(value=str(self.cfg['trigger_threshold']))
        self.var_maxspeed = tk.StringVar(value=str(self.cfg['max_speed']))
        self.var_gap = tk.StringVar(value=str(self.cfg['stroke_min_gap']))
        self.var_spm = tk.StringVar(value=str(self.cfg.get('strokes_per_min_at_max', 300)))
        self.var_len = tk.StringVar(value=str(self.cfg.get('stroke_length_mm', 78.7)))
        self.var_latch = tk.BooleanVar(value=bool(self.cfg.get('speed_latch', True)))
        fields = [
            ('Controller index (0-3)', self.var_index),
            ('Send interval (ms)', self.var_interval),
            ('Stick deadzone (0-1)', self.var_deadzone),
            ('Trigger threshold (0-1)', self.var_threshold),
            ('Max speed', self.var_maxspeed),
            ('Minimum stroke gap', self.var_gap),
            ('Strokes/min at max speed', self.var_spm),
            ('Total stroke length (mm)', self.var_len),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(tune, text=label).grid(row=i // 3, column=(i % 3) * 2,
                                             sticky='w', pady=4, padx=(0, 6))
            ttk.Entry(tune, textvariable=var, width=10).grid(row=i // 3, column=(i % 3) * 2 + 1,
                                                             sticky='w', padx=(0, 18))
        ttk.Checkbutton(tune, text='Latch speed when the trigger is released',
                        variable=self.var_latch).grid(row=3, column=0, columnspan=4,
                                                      sticky='w', pady=(8, 0))
        ttk.Button(tune, text='Apply', command=self.apply_settings).grid(
            row=3, column=4, sticky='e', pady=(8, 0))
        ttk.Label(tune, style='Sub.TLabel', wraplength=780, justify='left',
                  text=('The last two values only calibrate the motion view — the device '
                        'reports no position, so that view is reconstructed from the '
                        'command that was sent. Defaults are the Solace Pro figures: '
                        '78.7 mm of travel (3.1 in) at up to 300 strokes/min.')
                  ).grid(row=4, column=0, columnspan=6, sticky='w', pady=(8, 0))

        info = ttk.LabelFrame(self.tab_settings, text='About', padding=10)
        info.pack(fill='both', expand=True)
        ttk.Label(info, justify='left', text=(
            'Xbox-Controller-To-Lovense — drives a Lovense Solace / Solace Pro from an '
            'Xbox controller.\n\n'
            'Commands go to the local Lovense Remote API as\n'
            '  {"command":"Function","action":"Thrusting:<0-20>,Stroke:<min>-<max>", ...}\n\n'
            f'Settings file: {core.CONFIG_FILE}\n'
            'Companion to the SillyTavern-Lovense-Panel extension — both can run at the '
            'same time; the last command sent wins.\n\n'
            'For adult users (18+). Use responsibly.')).pack(anchor='w')

    def apply_settings(self):
        try:
            self.cfg['lovense_ip'] = self.var_ip.get().strip()
            self.cfg['lovense_port'] = int(self.var_port.get())
            self.cfg['controller_index'] = max(0, min(3, int(self.var_index.get())))
            self.cfg['send_interval_ms'] = max(50, int(float(self.var_interval.get())))
            self.cfg['stick_deadzone'] = max(0.0, min(0.9, float(self.var_deadzone.get())))
            self.cfg['trigger_threshold'] = max(0.0, min(0.9, float(self.var_threshold.get())))
            self.cfg['max_speed'] = max(1, int(float(self.var_maxspeed.get())))
            self.cfg['stroke_min_gap'] = max(0, min(90, int(float(self.var_gap.get()))))
            self.cfg['strokes_per_min_at_max'] = max(1, int(float(self.var_spm.get())))
            self.cfg['stroke_length_mm'] = max(1.0, float(self.var_len.get()))
            self.cfg['speed_latch'] = bool(self.var_latch.get())
        except ValueError:
            messagebox.showerror('Invalid settings', 'Please enter valid numbers.')
            return
        core.save_config(self.cfg)
        self.engine.apply_config(self.cfg)
        self.pad.index = self.cfg['controller_index']
        self.pad.deadzone = self.cfg['stick_deadzone']
        self.client.configure(self.cfg['lovense_ip'], self.cfg['lovense_port'],
                              self.cfg['send_interval_ms'])
        self.log('Settings applied')
        self.reconnect()

    # ---- status bar --------------------------------------------------------

    def _build_statusbar(self):
        bar = ttk.Frame(self, padding=(10, 4))
        bar.pack(fill='x', side='bottom')
        self.lbl_conn = ttk.Label(bar, text='Lovense: connecting …')
        self.lbl_conn.pack(side='left')
        self.lbl_pad = ttk.Label(bar, text='Controller: —')
        self.lbl_pad.pack(side='left', padx=20)
        ttk.Label(bar, text='Have Fun, mccrypt1', style='Sig.TLabel').pack(side='left')
        ttk.Button(bar, text='STOP', style='Stop.TButton',
                   command=lambda: self.engine.do_action('stop')).pack(side='right')
        ttk.Button(bar, text='Reconnect', command=self.reconnect).pack(side='right', padx=6)

    def reconnect(self):
        self.lbl_conn.configure(text='Lovense: connecting …')
        self.client.connect_async(callback=lambda ok: self.after(0, self._after_connect, ok))

    def _after_connect(self, ok):
        self.log(f'Connected — {self.client.toy_summary()}' if ok
                 else f'Not connected: {self.client.last_error}')

    # -- logging --------------------------------------------------------------

    def log(self, message):
        stamp = time.strftime('%H:%M:%S')
        self.log_box.configure(state='normal')
        self.log_box.insert('end', f'{stamp}  {message}\n')
        self.log_box.see('end')
        if int(self.log_box.index('end-1c').split('.')[0]) > 300:
            self.log_box.delete('1.0', '100.0')
        self.log_box.configure(state='disabled')

    # -- main loop ------------------------------------------------------------

    def _tick(self):
        now = time.monotonic()
        dt = now - self._last_frame
        self._last_frame = now

        changed = self.pad.poll()
        if changed:
            self.log('Controller connected' if self.pad.connected else 'Controller lost')
        self.engine.update(self.pad, dt)

        current = self.nb.index(self.nb.select())
        if current == 0:
            self.canvas_control.update_from_pad(self.pad)
            self._draw_speed_bar()
            self._draw_stroke_bar()
            self._update_mode_labels()
            self.stroke_view.step(
                speed=self.engine.speed, max_speed=self.engine.max_speed,
                lo=self.engine.stroke_min, hi=self.engine.stroke_max,
                mode=self.engine.mode, dt=dt,
                spm_at_max=float(self.cfg.get('strokes_per_min_at_max', 300)),
                length_mm=float(self.cfg.get('stroke_length_mm', 78.7)))
        elif current == 1:
            self.canvas_mapping.update_from_pad(self.pad)

        self.lbl_pad.configure(
            text=f'Controller: #{self.pad.index} connected' if self.pad.connected
            else 'Controller: not detected')
        if self.client.online:
            self.lbl_conn.configure(text=f'Lovense: {self.client.toy_summary() or "connected"}')
        elif self.client.base_url:
            self.lbl_conn.configure(text=f'Lovense: {self.client.last_error or "no toy"}')
        else:
            self.lbl_conn.configure(text='Lovense: not connected')

        if now - self._last_toy_refresh > TOY_REFRESH_S:
            self._last_toy_refresh = now
            self.client.connect_async()

        self.after(POLL_MS, self._tick)

    def _update_mode_labels(self):
        engine = self.engine
        self.lbl_mode.configure(text=engine.mode)
        if engine.mode == core.MODE_PATTERN:
            pattern = engine.current_pattern() or {}
            steps = len(pattern.get('steps', []))
            detail = (f'{pattern.get("name", "?")} · step {engine.step_idx + 1}/{steps} '
                      f'· tempo {engine.tempo:.1f}×')
        elif engine.mode == core.MODE_PRESET:
            detail = f'Lovense preset: {core.LOVENSE_PRESETS[engine.preset_idx]}'
        elif engine.mode == core.MODE_LIVE:
            detail = 'Controller drives speed and stroke directly'
        else:
            detail = 'Device idle'
        self.lbl_mode_detail.configure(text=detail)

    # -- shutdown --------------------------------------------------------------

    def on_close(self):
        try:
            core.save_config(self.cfg)
            self.client.stop_device()
            time.sleep(0.25)
            self.client.shutdown()
        finally:
            self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
