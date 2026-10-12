/**
 * Lovense Remote client. Commands leave only when the session is armed,
 * except Stop, which is always allowed. GetToys is a read and is always allowed.
 * In Node (tests) nothing is sent over the network.
 */

import { buildThrustAction, candidateHosts, commandUrl, sceneToIntent } from '../shared/lovense-action.mjs';

const DEFAULT_GUIDE = `1. Match intensity to context: gentle (1-10), moderate (11-15), intense (16-20)
2. Use commands that fit the scene naturally
3. Multiple commands per response allowed
4. Commands loop until your next response`;

export function createLovenseRemote({ isArmed = () => false, fetchImpl, headersImpl, onLog } = {}) {
    let host = '127.0.0.1';
    let port = 30010;
    let pinnedHost = null;
    let connected = false;
    let connecting = false;
    let toys = {};
    let lastAction = null;
    let lastError = '';

    function log(message) { onLog?.(`[lovense] ${message}`); }

    async function post(targetHost, body) {
        const url = commandUrl(targetHost, port);
        if (!url) {
            lastError = 'host rejected';
            return null;
        }
        const envelope = { host: targetHost, port, ...body };
        lastAction = body.action || body.command;
        if (typeof window === 'undefined') return { code: 200, data: { toys: {} } };
        const fetchFn = fetchImpl || globalThis.fetch;
        if (typeof fetchFn !== 'function') return null;
        let headers = { 'Content-Type': 'application/json' };
        try {
            const extra = await headersImpl?.();
            if (extra && typeof extra === 'object') headers = { ...headers, ...extra };
        } catch { /* SillyTavern headers are optional in tests */ }
        const response = await fetchFn('/api/plugins/lovense/command', {
            method: 'POST',
            headers,
            body: JSON.stringify(envelope),
        });
        return response.json();
    }

    async function send(command) {
        const name = command?.command;
        const isStop = name === 'Function' && command.action === 'Stop';
        const isRead = name === 'GetToys';
        if (!isStop && !isRead && !isArmed()) return false;
        if (!pinnedHost && !isRead) return false;
        try {
            const result = await post(pinnedHost || host, command);
            return result?.code === 200;
        } catch (error) {
            lastError = error.message;
            log(lastError);
            return false;
        }
    }

    return {
        configure({ ip, port: nextPort } = {}) {
            if (ip) host = String(ip).trim();
            if (nextPort) port = Number(nextPort);
            pinnedHost = null;
            connected = false;
        },
        get host() { return host; },
        get port() { return port; },
        get connected() { return connected; },
        get connecting() { return connecting; },
        get toys() { return toys; },
        get lastAction() { return lastAction; },
        get lastError() { return lastError; },
        get guidelines() { return DEFAULT_GUIDE; },
        async checkConnection() {
            connecting = true;
            connected = false;
            toys = {};
            pinnedHost = null;
            const hosts = candidateHosts(host);
            try {
                for (const candidate of hosts) {
                    if (!commandUrl(candidate, port)) continue;
                    const result = await post(candidate, { command: 'GetToys' });
                    if (result?.code !== 200) continue;
                    const raw = result.data?.toys;
                    const parsed = typeof raw === 'string' ? JSON.parse(raw || '{}') : (raw || {});
                    toys = parsed && typeof parsed === 'object' ? parsed : {};
                    pinnedHost = candidate;
                    connected = true;
                    lastError = '';
                    return true;
                }
                lastError = 'Lovense Remote did not answer';
                return false;
            } catch (error) {
                lastError = error.message;
                return false;
            } finally {
                connecting = false;
            }
        },
        disconnect() {
            pinnedHost = null;
            connected = false;
            toys = {};
        },
        send,
        sendIntent(intent) {
            const action = buildThrustAction(intent || {});
            return send({ command: 'Function', action, timeSec: 0, apiVer: 1 });
        },
        sendScene(act, pace, intensity) {
            return this.sendIntent(sceneToIntent(act, pace, intensity));
        },
        stop() {
            return send({ command: 'Function', action: 'Stop', timeSec: 0, apiVer: 1 });
        },
    };
}
