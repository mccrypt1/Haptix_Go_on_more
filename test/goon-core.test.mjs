/**
 * Consent and tag priority against the real core, with SillyTavern mocked.
 * Run: node test/goon-core.test.mjs
 */

class Emitter {
    constructor() { this.h = {}; }
    on(t, f) { (this.h[t] = this.h[t] || []).push(f); }
    async emit(t, ...a) { for (const f of (this.h[t] || [])) await f(...a); }
}
const es = new Emitter();
const eventTypes = { MESSAGE_RECEIVED: 'mr', MESSAGE_SENT: 'ms', CHAT_CHANGED: 'cc', GENERATION_STARTED: 'gs' };
const chat = [];
let llmCalls = 0;
const ctxObj = {
    chat, name1: 'You', name2: 'Aelora',
    characters: [{ name: 'Aelora', description: 'a sorceress' }],
    characterId: 0,
    substituteParams: (s) => s,
    setExtensionPrompt: () => {},
    eventSource: es, eventTypes,
    generateQuietPrompt: async () => { llmCalls++; return JSON.stringify({ contact: true, act: 'handjob', pace: 'slow', involuntary: 'none' }); },
};
globalThis.SillyTavern = { getContext: () => ctxObj };
globalThis.toastr = { info() {}, success() {}, warning() {}, error() {} };
globalThis.document = { hidden: false };
const store = new Map();
globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k),
};

const { initCore } = await import('../lib/core.js');
const api = initCore();
let pass = 0, fail = 0; const fails = [];
const t = (n, f) => { try { f(); pass++; } catch (e) { fail++; fails.push(`${n}: ${e.message}`); } };
const eq = (a, b, m) => { if (a !== b) throw new Error(`${m || 'eq'}: ${a} !== ${b}`); };
const ok = (c, m) => { if (!c) throw new Error(m || 'falsy'); };

async function ai(text) {
    chat.push({ mes: text, name: 'Aelora', is_user: false });
    await es.emit(eventTypes.MESSAGE_RECEIVED, chat.length - 1);
}

await api.connectLovense();
await ai('<lovense:thrusting="12" time="3"/>');
t('disarmed tag does not move the device', () => eq(api.getStatus().lastLovenseAction, 'GetToys'));

api.arm('consent-test');
const before = llmCalls;
await ai('<lovense:thrusting="8" time="2"/>');
t('tag wins over the scene classifier', () => {
    eq(api.getStatus().lastLovenseAction, 'Thrusting:8');
    eq(llmCalls, before);
});

api.estop();
await ai('<lovense:thrusting="15" time="2"/>');
t('stop ignores the rest of the response', () => eq(api.getStatus().lastLovenseAction, 'Stop'));

await es.emit(eventTypes.GENERATION_STARTED);
await ai('She wraps her hand around your cock and strokes you slowly');
t('next turn can use the scene when there is no tag', () => ok(String(api.getStatus().lastLovenseAction).startsWith('Thrusting:'), api.getStatus().lastLovenseAction));

document.hidden = true;
const hiddenAction = api.getStatus().lastLovenseAction;
const manual = await api.manualLovense(20, 0, 100);
t('hidden tab does not accept a manual override', () => {
    eq(manual, false);
    eq(api.getStatus().lastLovenseAction, hiddenAction);
});

if (fail) {
    console.error(fails.join('\n'));
    console.error(`goon-core: ${pass} passed, ${fail} failed`);
    process.exit(1);
}
console.log(`goon-core: ${pass} passed, 0 failed`);
