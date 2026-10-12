/**
 * Allowlist for the Lovense proxy. The browser never supplies a URL.
 * Only POST /command on an allowed host and port is forwarded, and only
 * known Lovense command fields are copied into the upstream body.
 */

import { commandUrl, sanitizeFunctionAction, sanitizePresetName } from './lovense-action.mjs';

const COMMANDS = new Set(['GetToys', 'Function', 'Preset', 'Pattern']);

function finite(value, lo, hi, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(lo, Math.min(hi, n));
}

function toyId(value) {
    if (value == null || value === '') return undefined;
    const text = String(value);
    return /^[A-Za-z0-9]{1,64}$/.test(text) ? text : undefined;
}

/**
 * Turn a plugin request body into { url, payload } or an error string.
 * `url` in the body is ignored so the plugin cannot be aimed at an arbitrary address.
 */
export function buildUpstream(body) {
    const source = body && typeof body === 'object' ? body : {};
    const url = commandUrl(source.host, source.port);
    if (!url) return { error: 'Lovense host or port is not allowed' };

    const command = String(source.command || '');
    if (!COMMANDS.has(command)) return { error: 'Lovense command is not allowed' };

    const payload = { command, apiVer: command === 'Pattern' ? 2 : 1 };
    const toy = toyId(source.toy);
    if (toy) payload.toy = toy;

    if (command === 'Function') {
        const action = sanitizeFunctionAction(source.action);
        if (!action) return { error: 'Lovense action is not allowed' };
        payload.action = action;
        payload.timeSec = finite(source.timeSec, 0, 60, 0);
        payload.apiVer = 1;
    } else if (command === 'Preset') {
        const name = sanitizePresetName(source.name);
        if (!name) return { error: 'Lovense preset is not allowed' };
        payload.name = name;
        payload.timeSec = finite(source.timeSec, 0, 60, 0);
    } else if (command === 'Pattern') {
        const strength = String(source.strength || '');
        if (!/^(\d{1,2})(;\d{1,2}){0,31}$/.test(strength)) return { error: 'Pattern strength is not allowed' };
        const levels = strength.split(';').map((part) => Math.max(0, Math.min(20, Number(part))));
        payload.strength = levels.join(';');
        const rule = String(source.rule || '');
        if (!/^V:1;F:[vrptfsdo](?:,[vrptfsdo]){0,7};S:\d{2,4}#$/.test(rule)) return { error: 'Pattern rule is not allowed' };
        payload.rule = rule;
        payload.timeSec = finite(source.timeSec, 0, 60, 0);
        payload.apiVer = 2;
    }

    return { url, payload };
}
