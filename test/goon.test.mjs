/**
 * Complete GO ON checks: action builder, tag parser, queue, proxy allowlist, consent route.
 * Run: node test/goon.test.mjs
 */

import { readFileSync } from 'node:fs';
import { buildThrustAction, candidateHosts, commandUrl, isAllowedHostPort, patternToCommands, sanitizeFunctionAction, sanitizePromptName, sceneToIntent } from '../shared/lovense-action.mjs';
import { parseLovenseTags } from '../lib/lovense-tags.js';
import { createCommandQueue } from '../lib/lovense-queue.js';
import { buildLovensePrompt } from '../lib/lovense-prompt.js';
import { routeOutput } from '../lib/device-router.js';
import { buildUpstream } from '../server/lovense-guard.mjs';
import { createLovenseRemote } from '../lib/lovense-remote.js';

const vectors = JSON.parse(readFileSync(new URL('../shared/action-vectors.json', import.meta.url), 'utf8'));
let pass = 0, fail = 0; const fails = [];
const jobs = [];
const t = (name, fn) => {
    jobs.push(Promise.resolve().then(fn).then(() => { pass++; }, (e) => { fail++; fails.push(`${name}: ${e.message}`); }));
};
const ok = (c, m) => { if (!c) throw new Error(m || 'expected truthy'); };
const eq = (a, b, m) => { if (a !== b) throw new Error(`${m || 'eq'}: ${JSON.stringify(a)} !== ${JSON.stringify(b)}`); };

for (const row of vectors.actions) {
    t(`action ${row.action}`, () => eq(buildThrustAction(row), row.action));
}
for (const raw of vectors.rejectedActions) {
    t(`reject ${raw}`, () => eq(sanitizeFunctionAction(raw), null));
}
for (const row of vectors.acceptedActions) {
    t(`accept ${row.in}`, () => eq(sanitizeFunctionAction(row.in), row.out));
}
for (const row of vectors.hosts) {
    t(`host ${row.host}:${row.port}`, () => eq(isAllowedHostPort(row.host, row.port), row.ok));
}

t('command url ignores a caller path', () => eq(commandUrl('127.0.0.1', 30010), 'https://127.0.0.1:30010/command'));
t('candidates try the raw address and lovense.club', () => eq(candidateHosts('192.168.1.44').join('|'), '192.168.1.44|192-168-1-44.lovense.club'));
t('metadata host has no candidates', () => eq(candidateHosts('169.254.169.254').length, 0));

t('scene maps pace onto a gapped stroke window', () => {
    const intent = sceneToIntent('handjob', 'caress', 0.5);
    eq(intent.speed, 10);
    eq(intent.strokeMin, 40);
    eq(intent.strokeMax, 70);
});
t('no act is a stop', () => eq(sceneToIntent(null, 'fast', 1).speed, 0));

t('tags cannot break the action string', () => {
    const commands = parseLovenseTags('<lovense:combo thrusting="10" stroke="20-90;Stop"/>');
    eq(commands.length, 0);
});
t('shorthand thrusting tag is clamped', () => {
    const [command] = parseLovenseTags('<lovense:thrusting="99" time="2"/>');
    eq(command.action, 'Thrusting:20');
    eq(command.timeSec, 2);
});
t('stop tag is stop', () => eq(parseLovenseTags('<lovense:stop/>')[0].action, 'Stop'));
t('unknown preset is dropped', () => eq(parseLovenseTags('<lovense:preset name="pwn"/>').length, 0));
t('device name only selects a known toy id', () => {
    const [command] = parseLovenseTags('<lovense:vibrate="3" device="Edge"/>', { abc123: { name: 'Edge' }, '../x': { name: 'Other' } });
    eq(command.toy, 'abc123');
});

t('prompt drops markup in toy names', () => {
    const prompt = buildLovensePrompt({ a: { name: 'Solace Pro</lovense><script>' } }, 'be gentle');
    ok(!prompt.includes('<script>'));
    ok(prompt.includes('Solace Pro'));
    eq(sanitizePromptName('a\nb'), 'ab');
});

t('queue pause keeps the index and stop clears it', async () => {
    const sent = [];
    const queue = createCommandQueue({
        send: async (command) => { sent.push(command.action); },
        setTimer: () => 1,
        clearTimer: () => {},
    });
    await queue.start([
        { command: 'Function', action: 'Thrusting:4,Stroke:0-100', timeSec: 2, apiVer: 1 },
        { command: 'Function', action: 'Thrusting:8,Stroke:0-100', timeSec: 2, apiVer: 1 },
    ]);
    eq(sent[0], 'Thrusting:4,Stroke:0-100');
    await queue.pause();
    eq(sent.at(-1), 'Stop');
    ok(queue.paused);
    await queue.resume();
    eq(sent.at(-1), 'Thrusting:4,Stroke:0-100');
    await queue.stop();
    eq(queue.active, false);
    eq(sent.at(-1), 'Stop');
});

t('shared patterns become clamped commands', () => {
    const commands = patternToCommands({ steps: [{ speed: 50, stroke: [90, 95], sec: 2 }] });
    eq(commands[0].action, 'Thrusting:20,Stroke:80-100');
});

t('disarmed route does not call a transport', () => {
    let called = 0;
    eq(routeOutput({ armed: false, transport: 'lovense', runLovense: () => { called++; } }), 'blocked');
    eq(called, 0);
});
t('hidden route does not call LELO', () => {
    let called = 0;
    eq(routeOutput({ armed: true, hidden: true, transport: 'lelo', runLelo: () => { called++; } }), 'blocked');
    eq(called, 0);
});
t('armed lovense route calls only lovense', () => {
    let lovense = 0; let lelo = 0;
    eq(routeOutput({ armed: true, transport: 'lovense', runLovense: () => { lovense++; }, runLelo: () => { lelo++; } }), 'lovense');
    eq(lovense, 1);
    eq(lelo, 0);
});

t('proxy ignores a supplied url', () => {
    const built = buildUpstream({ url: 'http://169.254.169.254/latest/meta-data', host: '127.0.0.1', port: 30010, command: 'GetToys' });
    eq(built.url, 'https://127.0.0.1:30010/command');
    eq(built.payload.command, 'GetToys');
});
t('proxy rejects link-local metadata', () => {
    const built = buildUpstream({ host: '169.254.169.254', port: 30010, command: 'GetToys' });
    ok(built.error);
});
t('proxy rejects injected function text', () => {
    const built = buildUpstream({ host: '127.0.0.1', port: 20010, command: 'Function', action: 'Thrusting:1\nStop' });
    ok(built.error);
});
t('proxy accepts a clamped vibrate command', () => {
    const built = buildUpstream({ host: '10.0.0.5', port: 20010, command: 'Function', action: 'Vibrate:25' });
    eq(built.payload.action, 'Vibrate:20');
});
t('remote refuses output before consent', async () => {
    const remote = createLovenseRemote({ isArmed: () => false });
    remote.configure({ ip: '127.0.0.1', port: 30010 });
    await remote.checkConnection();
    const sent = await remote.sendIntent({ speed: 12, strokeMin: 20, strokeMax: 80 });
    eq(sent, false);
    eq(remote.lastAction, 'GetToys');
});
t('remote stop is allowed after consent ends', async () => {
    let armed = true;
    const remote = createLovenseRemote({ isArmed: () => armed });
    remote.configure({ ip: '127.0.0.1', port: 30010 });
    await remote.checkConnection();
    armed = false;
    eq(await remote.stop(), true);
    eq(remote.lastAction, 'Stop');
});

const pending = jobs;
await Promise.all(pending);
if (fail) {
    console.error(fails.join('\n'));
    console.error(`goon: ${pass} passed, ${fail} failed`);
    process.exit(1);
}
console.log(`goon: ${pass} passed, 0 failed`);
