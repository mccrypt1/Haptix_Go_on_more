/**
 * System-prompt text for tag-driven Lovense control.
 * Toy names are reduced to a short safe alphabet before they enter the prompt.
 */

import { sanitizePromptName } from '../shared/lovense-action.mjs';

const CAPABILITIES = Object.freeze({
    nora: ['vibrate', 'rotate'],
    diamo: ['vibrate', 'rotate'],
    ridge: ['vibrate', 'rotate'],
    max: ['vibrate', 'pump'],
    'max 2': ['vibrate', 'pump'],
    gravity: ['vibrate', 'thrusting'],
    'sex machine': ['vibrate', 'thrusting'],
    'mini sex machine': ['vibrate', 'thrusting'],
    solace: ['vibrate', 'thrusting'],
    'solace pro': ['vibrate', 'thrusting'],
    flexer: ['vibrate', 'fingering'],
    tenera: ['vibrate', 'suction'],
    'tenera 2': ['vibrate', 'suction'],
    osci: ['vibrate', 'oscillate'],
    'osci 2': ['vibrate', 'oscillate'],
    'osci 3': ['vibrate', 'oscillate'],
});

const LINES = Object.freeze({
    vibrate: '<lovense:vibrate="X" time="Y"/> - Vibrate at X (0-20) for Y seconds',
    rotate: '<lovense:rotate="X" time="Y"/> - Rotate at X (0-20) for Y seconds',
    pump: '<lovense:pump="X" time="Y"/> - Pump at X (0-3) for Y seconds',
    thrusting: '<lovense:thrusting="X" time="Y"/> - Thrust at X (0-20) for Y seconds',
    fingering: '<lovense:fingering="X" time="Y"/> - Fingering at X (0-20) for Y seconds',
    suction: '<lovense:suction="X" time="Y"/> - Suction at X (0-20) for Y seconds',
    oscillate: '<lovense:oscillate="X" time="Y"/> - Oscillate at X (0-20) for Y seconds',
});

export function capabilitiesFor(toys) {
    const caps = new Set(['vibrate']);
    const names = [];
    for (const toy of Object.values(toys || {})) {
        const raw = sanitizePromptName(toy?.name || toy?.nickName || '');
        if (!raw) continue;
        names.push(raw);
        const known = CAPABILITIES[raw.toLowerCase()] || ['vibrate'];
        known.forEach((cap) => caps.add(cap));
    }
    return { caps, names };
}

export function buildLovensePrompt(toys, guidelines) {
    const { caps, names } = capabilitiesFor(toys);
    const lines = [...caps].map((cap) => LINES[cap]).filter(Boolean);
    const guide = String(guidelines || '').replace(/[<>]/g, '').slice(0, 500);
    const stroke = caps.has('thrusting')
        ? '\nStroke "MIN-MAX" (each 0-100, gap at least 20) sets stroke length. Example: <lovense:combo thrusting="10" stroke="20-90"/>'
        : '';
    const devices = names.length ? `\nConnected devices: ${names.join(', ')}.` : '';
    return `You can control the user's Lovense device during this conversation.
<lovense>
${lines.join('\n')}
<lovense:preset name="pulse|wave|fireworks|earthquake" time="Y"/>
<lovense:stop/>
${guide}${stroke}${devices}
</lovense>`;
}
