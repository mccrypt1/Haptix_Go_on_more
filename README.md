# Complete GO ON

One SillyTavern extension and one Windows desktop app. Both speak the same Lovense command: `Thrusting` for speed and `Stroke:MIN-MAX` for the stroke window.

The extension also keeps the Haptix LELO Bluetooth path. Solace Pro stays on Lovense Remote. LELO stays on Web Bluetooth.

## What is in the box

- **Lovense Remote.** Tags such as `<lovense:thrusting="10" time="5"/>` and `<lovense:combo thrusting="10" stroke="20-90"/>`, a queue with Pause and Play, and STOP. If a reply has no tag, the Haptix scene classifier can drive speed and a conservative stroke window. A tag in the same reply wins.
- **LELO Bluetooth.** The original Haptix connector, safety gate, sequences, and scene classifier. Stroke length is not simulated on LELO.
- **Panel.** Host and port, drive mode (tags, scene, or tags then scene), speed, stroke window, shared patterns, consent, Arm, and STOP. Panel modes: compact, stop button only, hidden.
- **Desktop app** in `desktop/`. Xbox controller via XInput, remapping, the same six patterns, and the same action string. It does not need the browser to be focused. If both run, the last command wins.

Nothing moves until the toy is connected, consent is ticked, and the session is armed. Esc and the red STOP clear the queue and ignore the rest of that reply.

## Install the extension

`main` on this fork is still the untouched Haptix snapshot. Install this branch:

```text
git clone -b Complete_GO_ON_Main https://github.com/mccrypt1/Haptix_Go_on_more
```

Put that folder in SillyTavern's `data/default-user/extensions/third-party/`.

Then:

1. In `config.yaml`, set `enableServerPlugins: true`.
2. Copy `server/lovense.mjs`, `server/lovense-guard.mjs`, and `server/lovense-action.mjs` into SillyTavern's `plugins/` folder. They have to sit side by side.
3. Restart SillyTavern. The console should say `Lovense Control server plugin loaded successfully`.
4. Start Lovense Remote on the PC, or Game Mode on the phone. Connect the toy. In the panel choose Lovense, enter the host and port shown by the app, and press Check connection.
5. Tick consent and press Arm.

`auto_update` is off. SillyTavern's updater would otherwise pull `main`, which is not this product. Turn updates on only after this branch is the default branch.

Web Bluetooth for LELO needs Chrome or Edge on `localhost` or HTTPS. Lovense Remote does not need Web Bluetooth.

## Desktop app

Windows 10 or 11, an XInput controller, and Python 3.8 or newer if you run the script. From `desktop/`:

```text
python xbox_to_lovense.py
```

`start.bat` does the same. `build_exe.bat` builds `XboxToLovense.exe`. The exe looks for `patterns.json` beside itself, then for `shared/patterns.json` in this repo. The first run writes `config.json` next to the script or exe.

The action rules live in `desktop/lovense_action.py` and match `shared/lovense-action.mjs`. Both are checked against `shared/action-vectors.json`.

## Safety notes

The Lovense plugin is not an open proxy. It ignores any `url` in the request and only posts to `/command` on an IPv4 host or a single-label `*.lovense.club` name, and only on ports 20000-20099 or 30000-30099. Link-local addresses, including cloud metadata, are refused. Redirects are not followed. TLS certificate checks are relaxed only after that allowlist passes, because Lovense Remote uses its own certificate.

That still means a logged-in SillyTavern session can send a Lovense command to any allowed address and port. The plugin does not know whether the panel session is armed. Arm, STOP, and the hidden-tab stop are enforced in the extension and the desktop app.

Other limits:

- Speed, stroke, presets, and pattern text are rebuilt from numbers. Extra text in a tag or pattern does not become part of the command.
- Toy names shown in the panel and written into the prompt are reduced to letters, numbers, spaces, and hyphens.
- A hidden browser tab and a disarmed session do not start output. STOP still can.
- The desktop app never shells out to the host you type. It only opens the allowlisted command URL, and it does not follow redirects.
- There is no telemetry and no extra package install. The extension is plain JavaScript. The desktop app is the Python standard library.

Known leftovers:

- A public IP in the Lovense port band is allowed, because a phone running Game Mode is not always on a private address.
- Lovense Remote is command-only. The desktop motion view reconstructs the stroke. It is not a position reading. LELO sensor feedback stays on the Bluetooth path.
- The extension and the desktop app do not share a live session.
- The panel still loads the Haptix display fonts from Google Fonts.

## Develop

```text
npm test
```

That runs the Haptix edge and integration harnesses, the GO ON checks, and the Python action mirror. No toy and no LLM are required.

## Credit

- Haptix (LELO Bluetooth, scene classifier, consent gate, panel): OlafBerserker, MIT. https://github.com/OlafBerserker/Haptix
- Lovense SillyTavern extension this Solace path grew from: Marinara, https://github.com/SpicyMarinara/SillyTavern-Lovense
- Solace Pro commands, live panel, and Xbox app: mccrypt1

Not affiliated with Lovense or LELO. For adults. Use at your own risk.
