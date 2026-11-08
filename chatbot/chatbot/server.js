import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { ChatError } from './errors.js';
import { listProviders, sendChat } from './chat.js';

const MAX_BODY_BYTES = 1_000_000;
const WINDOW_MS = 60_000;
const requestsByIp = new Map();

function loadEnvFile(filePath) {
    if (!existsSync(filePath)) return;
    const text = readFileSync(filePath, 'utf8');
    for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const raw = trimmed.startsWith('export ') ? trimmed.slice(7).trim() : trimmed;
        const separator = raw.indexOf('=');
        if (separator === -1) continue;
        const name = raw.slice(0, separator).trim();
        let value = raw.slice(separator + 1).trim();
        if (
            (value.startsWith('"') && value.endsWith('"'))
            || (value.startsWith("'") && value.endsWith("'"))
        ) {
            value = value.slice(1, -1);
        }
        if (name && process.env[name] === undefined) {
            process.env[name] = value;
        }
    }
}

export function loadLocalEnv() {
    const root = dirname(dirname(fileURLToPath(import.meta.url)));
    loadEnvFile(join(root, '.env.local'));
    loadEnvFile(join(root, '.env'));
}

function allowedOrigins() {
    const raw = process.env.CORS_ORIGIN || 'http://localhost:5173';
    return raw.split(',').map((origin) => origin.trim()).filter(Boolean);
}

function rateLimitMax() {
    const parsed = Number(process.env.CHAT_RATE_LIMIT || 30);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : 30;
}

function tooManyRequests(ip) {
    const now = Date.now();
    const recent = (requestsByIp.get(ip) || []).filter((time) => now - time < WINDOW_MS);
    if (recent.length >= rateLimitMax()) {
        requestsByIp.set(ip, recent);
        return true;
    }
    recent.push(now);
    requestsByIp.set(ip, recent);
    return false;
}

function statusFor(error) {
    if (error.code === 'validation') return 400;
    if (error.code === 'config') return 503;
    return 502;
}

function jsonResponse(status, body, origin) {
    const headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff'
    };
    if (origin && allowedOrigins().includes(origin)) {
        headers['Access-Control-Allow-Origin'] = origin;
        headers.Vary = 'Origin';
    }
    return { status, headers, body };
}

export async function handleApiRequest({ method, path, body, origin, ip = 'local' }) {
    const allowed = !origin || allowedOrigins().includes(origin);
    if (origin && !allowed) {
        return jsonResponse(403, {
            error: { code: 'forbidden', message: 'This origin is not allowed.' }
        }, origin);
    }

    if (method === 'OPTIONS') {
        const headers = jsonResponse(204, null, origin).headers;
        headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS';
        headers['Access-Control-Allow-Headers'] = 'Content-Type';
        headers['Access-Control-Max-Age'] = '600';
        return { status: 204, headers, body: null };
    }

    if (method === 'GET' && path === '/api/v1/health') {
        return jsonResponse(200, { ok: true }, origin);
    }

    if (method === 'GET' && path === '/api/v1/providers') {
        return jsonResponse(200, { providers: listProviders() }, origin);
    }

    if (method === 'POST' && path === '/api/v1/chat') {
        if (tooManyRequests(ip)) {
            return jsonResponse(429, {
                error: { code: 'rate_limit', message: 'Too many requests. Try again in a minute.' }
            }, origin);
        }

        try {
            const result = await sendChat({
                messages: body?.messages,
                provider: body?.provider || 'DeepSeek',
                explainCode: body?.explainCode === true,
                referer: origin || undefined
            });
            return jsonResponse(200, result, origin);
        } catch (error) {
            if (error instanceof ChatError) {
                return jsonResponse(statusFor(error), {
                    error: { code: error.code, message: error.message }
                }, origin);
            }
            console.error('Chat request error:', error?.name || 'Error');
            return jsonResponse(500, {
                error: { code: 'internal', message: 'The AI request failed. Check your connection and try again.' }
            }, origin);
        }
    }

    return jsonResponse(404, {
        error: { code: 'not_found', message: 'Not found.' }
    }, origin);
}

function readBody(req) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        let size = 0;
        req.on('data', (chunk) => {
            size += chunk.length;
            if (size > MAX_BODY_BYTES) {
                reject(new ChatError('validation', 'Request body is too large.'));
                req.destroy();
                return;
            }
            chunks.push(chunk);
        });
        req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
        req.on('error', () => reject(new ChatError('validation', 'Could not read the request.')));
    });
}

function send(res, result) {
    res.writeHead(result.status, result.headers);
    res.end(result.body == null ? '' : JSON.stringify(result.body));
}

export function createChatServer() {
    return createServer(async (req, res) => {
        const url = new URL(req.url || '/', 'http://127.0.0.1');
        const origin = req.headers.origin;
        let body;
        if (req.method === 'POST') {
            const contentType = req.headers['content-type'] || '';
            if (!contentType.includes('application/json')) {
                send(res, jsonResponse(415, {
                    error: { code: 'validation', message: 'Send JSON with Content-Type application/json.' }
                }, origin));
                return;
            }
            try {
                const raw = await readBody(req);
                body = raw ? JSON.parse(raw) : {};
                if (!body || typeof body !== 'object' || Array.isArray(body)) {
                    throw new ChatError('validation', 'Request body must be a JSON object.');
                }
            } catch (error) {
                const message = error instanceof ChatError
                    ? error.message
                    : 'Request body must be JSON.';
                send(res, jsonResponse(400, { error: { code: 'validation', message } }, origin));
                return;
            }
        }

        try {
            const result = await handleApiRequest({
                method: req.method || 'GET',
                path: url.pathname,
                body,
                origin,
                ip: req.socket?.remoteAddress || 'local'
            });
            send(res, result);
        } catch (error) {
            console.error('HTTP error:', error?.name || 'Error');
            send(res, jsonResponse(500, {
                error: { code: 'internal', message: 'The AI request failed. Check your connection and try again.' }
            }, origin));
        }
    });
}

const entry = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === entry) {
    loadLocalEnv();
    const port = Number(process.env.PORT) || 8787;
    const server = createChatServer();
    server.listen(port, '127.0.0.1', () => {
        console.log(`Chat backend listening on http://127.0.0.1:${port}`);
    });
}
