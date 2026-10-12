/**
 * Parse <lovense:…/> tags into allowlisted Lovense commands.
 * Toy ids are taken only from the connected toy map, never from the tag text.
 */

import { clampInt, clampStroke, sanitizeFunctionAction, sanitizePresetName } from '../shared/lovense-action.mjs';

const TAG = /<lovense:(\w+)([^>]*?)\/>/gi;
const ATTR = /(\w+)="([^"]*)"/g;
const SHORTHAND = /^\s*="([^"]*)"/;

const LEVELS = Object.freeze({
    vibrate: ['Vibrate', 0, 20],
    rotate: ['Rotate', 0, 20],
    thrusting: ['Thrusting', 0, 20],
    fingering: ['Fingering', 0, 20],
    suction: ['Suction', 0, 20],
    oscillate: ['Oscillate', 0, 20],
    all: ['All', 0, 20],
    pump: ['Pump', 0, 3],
    depth: ['Depth', 0, 3],
});

const PATTERN_FLAGS = Object.freeze({
    vibrate: 'v', rotate: 'r', pump: 'p', thrusting: 't', fingering: 'f', suction: 's', depth: 'd', oscillate: 'o',
});

function attrsOf(raw) {
    const attrs = {};
    if (/[<>\r\n;]/.test(raw)) return null;
    let match;
    ATTR.lastIndex = 0;
    while ((match = ATTR.exec(raw)) !== null) {
        if (!/^[A-Za-z0-9 ._-]{0,64}$/.test(match[2])) return null;
        attrs[match[1].toLowerCase()] = match[2];
    }
    return attrs;
}

function timeSec(attrs) {
    return clampInt(attrs.time || attrs.duration || 5, 0, 60) || 5;
}

function toyFrom(attrs, toys) {
    if (!attrs.device || !toys) return undefined;
    const wanted = attrs.device.toLowerCase();
    for (const [id, toy] of Object.entries(toys)) {
        const name = String(toy?.name || '').toLowerCase();
        const nick = String(toy?.nickName || '').toLowerCase();
        if ((name === wanted || nick === wanted) && /^[A-Za-z0-9]{1,64}$/.test(id)) return id;
    }
    return undefined;
}

function withToy(command, attrs, toys) {
    const toy = toyFrom(attrs, toys);
    if (toy) command.toy = toy;
    return command;
}

function levelToken(key, raw) {
    const spec = LEVELS[key];
    if (!spec || !/^\d{1,3}$/.test(String(raw))) return null;
    return `${spec[0]}:${clampInt(raw, spec[1], spec[2])}`;
}

export function parseLovenseTags(text, toys = {}) {
    const commands = [];
    if (typeof text !== 'string' || text.length > 20000) return commands;
    TAG.lastIndex = 0;
    let match;
    while ((match = TAG.exec(text)) !== null) {
        const action = match[1].toLowerCase();
        if (!/^[a-z]{1,20}$/.test(action)) continue;
        const attrs = attrsOf(match[2] || '');
        if (!attrs) continue;
        const short = SHORTHAND.exec(match[2] || '');
        if (short) {
            if (!/^[A-Za-z0-9 ._-]{0,64}$/.test(short[1])) continue;
            attrs[action] = short[1];
        }

        if (action === 'stop') {
            commands.push({ command: 'Function', action: 'Stop', timeSec: 0, apiVer: 1 });
            continue;
        }

        if (action === 'preset') {
            const name = sanitizePresetName(attrs.name);
            if (!name) continue;
            commands.push(withToy({ command: 'Preset', name, timeSec: timeSec(attrs), apiVer: 1 }, attrs, toys));
            continue;
        }

        if (action === 'pattern') {
            if (!/^(\d{1,2})(;\d{1,2}){0,31}$/.test(attrs.strength || '')) continue;
            const flags = [];
            for (const [key, letter] of Object.entries(PATTERN_FLAGS)) {
                if (attrs[key] === '1' || attrs[key] === 'true') flags.push(letter);
            }
            if (!flags.length) flags.push('v');
            const interval = clampInt(attrs.interval || 150, 50, 2000);
            const rule = `V:1;F:${flags.join(',')};S:${interval}#`;
            const strength = attrs.strength.split(';').map((part) => String(clampInt(part, 0, 20))).join(';');
            commands.push({ command: 'Pattern', rule, strength, timeSec: timeSec(attrs), apiVer: 2 });
            continue;
        }

        const tokens = [];
        if (action === 'combo') {
            for (const key of Object.keys(LEVELS)) {
                if (attrs[key] != null) {
                    const token = levelToken(key, attrs[key]);
                    if (token) tokens.push(token);
                }
            }
            if (attrs.stroke && /^\d{1,3}-\d{1,3}$/.test(attrs.stroke)) {
                const [a, b] = attrs.stroke.split('-');
                const [lo, hi] = clampStroke(a, b);
                tokens.push(`Stroke:${lo}-${hi}`);
            }
        } else if (action === 'stroke') {
            const raw = attrs.stroke || attrs.range || '';
            if (!/^\d{1,3}-\d{1,3}$/.test(raw)) continue;
            const [a, b] = raw.split('-');
            const [lo, hi] = clampStroke(a, b);
            tokens.push(`Stroke:${lo}-${hi}`);
        } else if (LEVELS[action]) {
            const token = levelToken(action, attrs[action] || attrs.intensity);
            if (token) tokens.push(token);
        }

        if (!tokens.length) continue;
        const built = sanitizeFunctionAction(tokens.join(','));
        if (!built) continue;
        commands.push(withToy({
            command: 'Function',
            action: built,
            timeSec: timeSec(attrs),
            apiVer: 1,
        }, attrs, toys));
    }
    return commands;
}
