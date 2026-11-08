import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { ChatError, sendChat } from './index.js';
import { handleApiRequest } from './server.js';

describe('chat backend', { concurrency: false }, () => {

function useFetch(t, impl) {
    const previousFetch = globalThis.fetch;
    const previousOpenRouter = process.env.OPENROUTER_API_KEY;
    const previousGroq = process.env.GROQ_API_KEY;
    process.env.OPENROUTER_API_KEY = 'test-openrouter-key';
    process.env.GROQ_API_KEY = 'test-groq-key';
    globalThis.fetch = impl;
    t.after(() => {
        globalThis.fetch = previousFetch;
        restoreEnv('OPENROUTER_API_KEY', previousOpenRouter);
        restoreEnv('GROQ_API_KEY', previousGroq);
    });
}

function restoreEnv(name, value) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
}

function jsonResponse(content, status = 200) {
    return new Response(JSON.stringify({
        choices: [{ message: { content } }]
    }), { status, headers: { 'Content-Type': 'application/json' } });
}

test('answers a text question without a file', async (t) => {
    let sent;
    useFetch(t, async (url, options) => {
        sent = { url, options, body: JSON.parse(options.body) };
        return jsonResponse('The answer is 4.');
    });

    const result = await sendChat({
        messages: [{ role: 'user', content: 'What is 2+2?' }]
    });

    assert.equal(result.text, 'The answer is 4.');
    assert.deepEqual(result.codeBlocks, []);
    assert.equal(sent.body.model, 'deepseek/deepseek-v3.2');
    assert.equal(sent.body.max_tokens, 2048);
    assert.equal(sent.body.messages[0].content, 'What is 2+2?');
    assert.equal(sent.options.headers.Authorization, 'Bearer test-openrouter-key');
    assert.equal(JSON.stringify(result).includes('test-openrouter-key'), false);
});

test('attaches file text to the user message', async (t) => {
    let sent;
    useFetch(t, async (_url, options) => {
        sent = JSON.parse(options.body);
        return jsonResponse('It prints hi.');
    });

    const result = await sendChat({
        provider: 'Groq',
        messages: [{
            role: 'user',
            content: 'What does this do?',
            files: [{ name: 'main.py', content: "print('hi')" }]
        }]
    });

    assert.equal(result.text, 'It prints hi.');
    assert.match(sent.messages[0].content, /What does this do\?/);
    assert.match(sent.messages[0].content, /--- File: main.py ---/);
    assert.match(sent.messages[0].content, /print\('hi'\)/);
    assert.equal(sent.model, 'qwen/qwen3.8-27b');
});

test('splits fenced code out of the reply', async (t) => {
    useFetch(t, async () => jsonResponse('Look\n```python\nprint(1)\n```\nDone'));

    const result = await sendChat({
        messages: [{ role: 'user', content: 'Show code' }]
    });

    assert.equal(result.text, 'Look\n[CODE_BLOCK_0]\nDone');
    assert.equal(result.codeBlocks[0].language, 'python');
    assert.equal(result.codeBlocks[0].code, 'print(1)');
    assert.deepEqual(result.codeBlocks[0].explanation, []);
});

test('rejects a missing key, an unknown provider, and an empty chat', async (t) => {
    const previous = process.env.OPENROUTER_API_KEY;
    const previousVite = process.env.VITE_OPENROUTER_KEY;
    delete process.env.OPENROUTER_API_KEY;
    delete process.env.VITE_OPENROUTER_KEY;
    t.after(() => {
        restoreEnv('OPENROUTER_API_KEY', previous);
        restoreEnv('VITE_OPENROUTER_KEY', previousVite);
    });

    await assert.rejects(
        () => sendChat({ messages: [{ role: 'user', content: 'Hi' }] }),
        (error) => error instanceof ChatError && error.code === 'config' && !error.message.includes('sk-')
    );
    await assert.rejects(
        () => sendChat({ provider: 'Claude', messages: [{ role: 'user', content: 'Hi' }] }),
        (error) => error instanceof ChatError && error.code === 'validation'
    );
    await assert.rejects(
        () => sendChat({ messages: [] }),
        (error) => error instanceof ChatError && error.code === 'validation'
    );
});

test('hides upstream error details from the caller', async (t) => {
    useFetch(t, async () => new Response(JSON.stringify({
        error: { message: 'secret-model-detail user_secret' }
    }), { status: 404 }));

    await assert.rejects(
        () => sendChat({ messages: [{ role: 'user', content: 'Hi' }] }),
        (error) => error instanceof ChatError
            && error.code === 'upstream'
            && !error.message.includes('secret-model-detail')
    );
});

test('POST /api/v1/chat returns the model reply', async (t) => {
    useFetch(t, async () => jsonResponse('Ready.'));

    const result = await handleApiRequest({
        method: 'POST',
        path: '/api/v1/chat',
        origin: 'http://localhost:5173',
        ip: 'test-chat',
        body: { messages: [{ role: 'user', content: 'Hello' }] }
    });

    assert.equal(result.status, 200);
    assert.equal(result.body.text, 'Ready.');
    assert.equal(result.headers['Access-Control-Allow-Origin'], 'http://localhost:5173');
});

test('rejects a disallowed origin and too many posts', async (t) => {
    const previousLimit = process.env.CHAT_RATE_LIMIT;
    process.env.CHAT_RATE_LIMIT = '1';
    t.after(() => restoreEnv('CHAT_RATE_LIMIT', previousLimit));
    useFetch(t, async () => jsonResponse('ok'));

    const forbidden = await handleApiRequest({
        method: 'POST',
        path: '/api/v1/chat',
        origin: 'https://evil.example',
        ip: 'test-origin',
        body: { messages: [{ role: 'user', content: 'Hello' }] }
    });
    assert.equal(forbidden.status, 403);

    const first = await handleApiRequest({
        method: 'POST',
        path: '/api/v1/chat',
        origin: 'http://localhost:5173',
        ip: 'test-rate',
        body: { messages: [{ role: 'user', content: 'Hello' }] }
    });
    const second = await handleApiRequest({
        method: 'POST',
        path: '/api/v1/chat',
        origin: 'http://localhost:5173',
        ip: 'test-rate',
        body: { messages: [{ role: 'user', content: 'Hello again' }] }
    });
    assert.equal(first.status, 200);
    assert.equal(second.status, 429);
});

test('lists providers and rejects an empty chat over HTTP', async () => {
    const providers = await handleApiRequest({
        method: 'GET',
        path: '/api/v1/providers'
    });
    assert.equal(providers.status, 200);
    assert.deepEqual(providers.body.providers.map((item) => item.id), ['DeepSeek', 'Groq']);

    const invalid = await handleApiRequest({
        method: 'POST',
        path: '/api/v1/chat',
        origin: 'http://localhost:5173',
        ip: 'test-empty',
        body: { messages: [] }
    });
    assert.equal(invalid.status, 400);
    assert.equal(invalid.body.error.code, 'validation');
});
});
