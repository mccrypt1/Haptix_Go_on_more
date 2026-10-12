import http from 'http';
import https from 'https';
import crypto from 'crypto';
import { buildUpstream } from './lovense-guard.mjs';

/**
 * SillyTavern server plugin. Copy this file into SillyTavern's plugins/ folder.
 * It forwards one Lovense command to the host and port the extension saved.
 * It does not accept a raw URL, does not follow redirects, and relaxes TLS
 * only after the host has passed the allowlist.
 */

export const info = {
    id: 'lovense',
    name: 'Lovense Control Plugin',
    description: 'Allowlisted proxy for the local Lovense Remote command API',
};

function createLovenseAgent() {
    return new https.Agent({
        rejectUnauthorized: false,
        secureOptions: crypto.constants.SSL_OP_LEGACY_SERVER_CONNECT,
        minVersion: 'TLSv1.2',
        keepAlive: true,
    });
}

const lovenseHttpsAgent = createLovenseAgent();
const lovenseHttpAgent = new http.Agent({ keepAlive: true });

export async function init(router) {
    console.log('Loading Lovense Control server plugin...');

    router.post('/command', async (req, res) => {
        const built = buildUpstream(req.body);
        if (built.error) {
            return res.status(400).json({ error: built.error });
        }

        try {
            const urlObj = new URL(built.url);
            const postData = JSON.stringify(built.payload);
            const isHttps = urlObj.protocol === 'https:';
            const transport = isHttps ? https : http;
            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: '/command',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData),
                    'X-platform': 'CompleteGOON',
                },
                agent: isHttps ? lovenseHttpsAgent : lovenseHttpAgent,
                timeout: 10000,
            };

            const proxyReq = transport.request(options, (proxyRes) => {
                if (proxyRes.statusCode >= 300 && proxyRes.statusCode < 400) {
                    proxyRes.resume();
                    if (!res.headersSent) res.status(502).json({ error: 'Lovense redirect was blocked' });
                    return;
                }
                let data = '';
                proxyRes.on('data', (chunk) => { data += chunk; });
                proxyRes.on('end', () => {
                    if (res.headersSent) return;
                    try {
                        res.json(JSON.parse(data));
                    } catch {
                        res.status(502).json({ error: 'Invalid response from Lovense device' });
                    }
                });
            });

            proxyReq.on('timeout', () => {
                proxyReq.destroy();
                if (!res.headersSent) res.status(504).json({ error: 'Connection to Lovense device timed out' });
            });
            proxyReq.on('error', (error) => {
                if (!res.headersSent) res.status(502).json({ error: 'Failed to connect to Lovense device', details: error.message });
            });
            proxyReq.write(postData);
            proxyReq.end();
        } catch (error) {
            if (!res.headersSent) res.status(500).json({ error: error.message });
        }
    });

    console.log('Lovense Control server plugin loaded successfully');
}
