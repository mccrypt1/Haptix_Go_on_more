/**
 * Complete GO ON — Lovense action builder.
 * Pure functions shared by the SillyTavern extension and the node tests.
 * The desktop app mirrors these rules in desktop/lovense_action.py.
 * Vectors that both sides must match live in shared/action-vectors.json.
 */

export const SPEED_MAX = 20;
export const STROKE_GAP = 20;
export const FUNCTION_RANGES = Object.freeze({
    Vibrate: [0, 20],
    Rotate: [0, 20],
    Thrusting: [0, 20],
    Fingering: [0, 20],
    Suction: [0, 20],
    Oscillate: [0, 20],
    All: [0, 20],
    Pump: [0, 3],
    Depth: [0, 3],
});

const STROKE_BY_PACE = Object.freeze({
    caress: [40, 70],
    slow: [25, 80],
    steady: [15, 90],
    fast: [0, 100],
    frantic: [0, 100],
});

const PRESETS = new Set(['pulse', 'wave', 'fireworks', 'earthquake']);

export function clampInt(value, lo, hi) {
    const n = Number(value);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, Math.round(n)));
}

export function clampSpeed(value) {
    return clampInt(value, 0, SPEED_MAX);
}

/** Keep a stroke window inside 0..100 with a minimum gap. */
export function clampStroke(min, max, gap = STROKE_GAP) {
    const span = clampInt(gap, 1, 100);
    let lo = clampInt(min, 0, 100);
    let hi = clampInt(max, 0, 100);
    if (hi < lo) {
        const swap = lo;
        lo = hi;
        hi = swap;
    }
    if (hi - lo < span) {
        hi = Math.min(100, lo + span);
        lo = hi - span;
    }
    return [lo, hi];
}

/**
 * Thrusting toys: speed 0 is Stop. Otherwise Thrusting:N,Stroke:MIN-MAX.
 * Inputs are clamped. The result never contains caller-supplied text.
 */
export function buildThrustAction({ speed = 0, strokeMin = 0, strokeMax = 100, gap = STROKE_GAP } = {}) {
    const sp = clampSpeed(speed);
    if (sp <= 0) return 'Stop';
    const [lo, hi] = clampStroke(strokeMin, strokeMax, gap);
    return `Thrusting:${sp},Stroke:${lo}-${hi}`;
}

export function sceneToIntent(act, pace, intensity01) {
    if (!act) return { speed: 0, strokeMin: 0, strokeMax: 100, vibrate: 0, source: 'scene' };
    const level = Number(intensity01);
    const speed = clampSpeed(Number.isFinite(level) ? level * SPEED_MAX : 0);
    const window = STROKE_BY_PACE[pace] || STROKE_BY_PACE.steady;
    const [strokeMin, strokeMax] = clampStroke(window[0], window[1]);
    return { speed, strokeMin, strokeMax, vibrate: speed, source: 'scene' };
}

/**
 * Accept only Stop or a comma-joined list of known Function:int tokens.
 * Stroke is MIN-MAX. Anything else, including extra commands, is rejected.
 */
export function sanitizeFunctionAction(raw) {
    if (typeof raw !== 'string') return null;
    const text = raw.trim();
    if (text === 'Stop') return 'Stop';
    if (!/^[A-Za-z0-9:,-]+$/.test(text)) return null;
    const parts = text.split(',');
    if (!parts.length || parts.length > 8) return null;
    const cleaned = [];
    for (const part of parts) {
        const stroke = /^Stroke:(\d{1,3})-(\d{1,3})$/.exec(part);
        if (stroke) {
            const [lo, hi] = clampStroke(stroke[1], stroke[2]);
            cleaned.push(`Stroke:${lo}-${hi}`);
            continue;
        }
        const fn = /^([A-Za-z]+):(\d{1,3})$/.exec(part);
        if (!fn || !Object.prototype.hasOwnProperty.call(FUNCTION_RANGES, fn[1])) return null;
        const [lo, hi] = FUNCTION_RANGES[fn[1]];
        cleaned.push(`${fn[1]}:${clampInt(fn[2], lo, hi)}`);
    }
    return cleaned.join(',');
}

export function sanitizePresetName(name) {
    const value = String(name || '').toLowerCase().trim();
    return PRESETS.has(value) ? value : null;
}

export function sanitizePromptName(name) {
    const clean = String(name || '').replace(/[^A-Za-z0-9 -]/g, '').replace(/\s+/g, ' ').trim();
    return clean.slice(0, 40);
}

const LOVENSE_SUFFIX = '.lovense.club';

/**
 * Host is an IPv4 address (no leading zeros) or a single-label *.lovense.club name.
 * Link-local, unspecified, multicast, and reserved ranges are rejected.
 * Port must sit in the Lovense HTTP (20000-20099) or HTTPS (30000-30099) band.
 */
export function isAllowedHostPort(host, port) {
    if (typeof host !== 'string') return false;
    const name = host.trim().toLowerCase();
    if (!name || name.length > 253 || !/^[a-z0-9.-]+$/.test(name)) return false;
    const portNum = Number(port);
    if (!Number.isInteger(portNum)) return false;
    const httpBand = portNum >= 20000 && portNum <= 20099;
    const httpsBand = portNum >= 30000 && portNum <= 30099;
    if (!httpBand && !httpsBand) return false;
    if (name.endsWith(LOVENSE_SUFFIX)) {
        const label = name.slice(0, -LOVENSE_SUFFIX.length);
        return /^[a-z0-9-]+$/.test(label) && !label.startsWith('-') && !label.endsWith('-');
    }
    const parts = name.split('.');
    if (parts.length !== 4) return false;
    const nums = [];
    for (const part of parts) {
        if (!/^\d{1,3}$/.test(part) || (part.length > 1 && part.startsWith('0'))) return false;
        const n = Number(part);
        if (n > 255) return false;
        nums.push(n);
    }
    const a = nums[0];
    const b = nums[1];
    if (a === 0 || a >= 224) return false;
    if (a === 169 && b === 254) return false;
    return true;
}

export function protocolForPort(port) {
    return Number(port) >= 30000 ? 'https' : 'http';
}

/** Build the only URL the proxy is allowed to call. Returns null when the target is rejected. */
export function commandUrl(host, port) {
    if (!isAllowedHostPort(host, port)) return null;
    const name = host.trim().toLowerCase();
    return `${protocolForPort(port)}://${name}:${Number(port)}/command`;
}

export function normalizeUserHost(input) {
    let host = String(input || '').trim().toLowerCase();
    if (!host || host === 'localhost') host = '127.0.0.1';
    if (host.endsWith(LOVENSE_SUFFIX)) return host;
    return host;
}

/** Raw IPv4 first, then the dashed lovense.club name the desktop app already uses. */
export function candidateHosts(input) {
    const host = normalizeUserHost(input);
    if (host.endsWith(LOVENSE_SUFFIX)) return [host];
    if (!isAllowedHostPort(host, 30010) && !isAllowedHostPort(host, 20010)) return [];
    if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return [];
    return [host, `${host.replaceAll('.', '-')}${LOVENSE_SUFFIX}`];
}

export function patternToCommands(pattern, gap = STROKE_GAP) {
    const steps = Array.isArray(pattern?.steps) ? pattern.steps : [];
    return steps.slice(0, 32).map((step) => {
        const [lo, hi] = clampStroke(step?.stroke?.[0], step?.stroke?.[1], gap);
        const action = buildThrustAction({ speed: step?.speed, strokeMin: lo, strokeMax: hi, gap });
        const sec = Number(step?.sec);
        const timeSec = Number.isFinite(sec) ? Math.max(0, Math.min(60, sec)) : 5;
        return { command: 'Function', action, timeSec, apiVer: 1 };
    });
}
