import { ChatError } from './errors.js';

const REQUEST_TIMEOUT_MS = 60000;
const MAX_OUTPUT_TOKENS = 2048;
const MAX_MESSAGES = 40;
const MAX_MESSAGE_CHARS = 20000;
const MAX_FILES = 5;
const MAX_FILE_CHARS = 100000;
const MAX_FILE_NAME_CHARS = 200;

export const AI_PROVIDERS = {
    DeepSeek: {
        name: 'DeepSeek',
        endpoint: 'https://openrouter.ai/api/v1/chat/completions',
        model: 'deepseek/deepseek-v3.2',
        referer: true
    },
    Groq: {
        name: 'Groq (Qwen)',
        endpoint: 'https://api.groq.com/openai/v1/chat/completions',
        model: 'qwen/qwen3.8-27b',
        referer: false
    }
};

function envValue(name) {
    const env = globalThis.process?.env;
    if (!env) return undefined;
    const value = env[name];
    return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function viteValue(providerId) {
    if (!import.meta.env) return undefined;
    const value = providerId === 'DeepSeek'
        ? import.meta.env.VITE_OPENROUTER_KEY
        : import.meta.env.VITE_GROQ_KEY;
    return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function apiKeyFor(providerId) {
    if (providerId === 'DeepSeek') {
        return envValue('OPENROUTER_API_KEY')
            || envValue('VITE_OPENROUTER_KEY')
            || viteValue(providerId);
    }
    return envValue('GROQ_API_KEY')
        || envValue('VITE_GROQ_KEY')
        || viteValue(providerId);
}

export function listProviders() {
    return Object.entries(AI_PROVIDERS).map(([id, provider]) => ({
        id,
        name: provider.name,
        model: provider.model
    }));
}

function providerById(providerId) {
    const provider = AI_PROVIDERS[providerId];
    if (!provider) {
        throw new ChatError('validation', 'Choose DeepSeek or Groq.');
    }
    return provider;
}

function safeFileName(name) {
    return String(name).replace(/[\r\n\0]/g, ' ').trim().slice(0, MAX_FILE_NAME_CHARS);
}

function roleOf(message) {
    if (message.role === 'user' || message.role === 'assistant' || message.role === 'system') {
        return message.role;
    }
    if (message.sender === 'user') return 'user';
    if (message.sender === 'bot' || message.sender === 'assistant') return 'assistant';
    throw new ChatError('validation', 'Each message needs a role of user, assistant, or system.');
}

function fileText(file) {
    if (!file || typeof file !== 'object' || typeof file.name !== 'string' || typeof file.content !== 'string') {
        throw new ChatError('validation', 'Each file needs a name and text content.');
    }
    const name = safeFileName(file.name);
    if (!name) {
        throw new ChatError('validation', 'Each file needs a name and text content.');
    }
    if (!file.content.trim()) {
        throw new ChatError('validation', `File ${name} is empty.`);
    }
    if (file.content.length > MAX_FILE_CHARS) {
        throw new ChatError('validation', `File ${name} is too large.`);
    }
    return { name, content: file.content };
}

export function normalizeMessages(messages) {
    if (!Array.isArray(messages) || messages.length === 0) {
        throw new ChatError('validation', 'Send at least one message.');
    }
    if (messages.length > MAX_MESSAGES) {
        throw new ChatError('validation', 'This conversation is too long.');
    }

    const formatted = messages.map((message) => {
        if (!message || typeof message !== 'object') {
            throw new ChatError('validation', 'Each message must be an object.');
        }
        if (message.content != null && typeof message.content !== 'string') {
            throw new ChatError('validation', 'Each message needs text content.');
        }
        const contentText = typeof message.content === 'string' ? message.content : '';
        if (contentText.length > MAX_MESSAGE_CHARS) {
            throw new ChatError('validation', 'A message is too long.');
        }

        const files = Array.isArray(message.files) ? message.files : [];
        if (files.length > MAX_FILES) {
            throw new ChatError('validation', 'Too many files on one message.');
        }

        let content = contentText.trim();
        for (const file of files.map(fileText)) {
            content += `\n\n--- File: ${file.name} ---\n${file.content}\n---`;
        }
        if (!content) {
            throw new ChatError('validation', 'Each message needs text or a file.');
        }

        return { role: roleOf(message), content };
    });

    if (!formatted.some((message) => message.role === 'user')) {
        throw new ChatError('validation', 'Send a user message.');
    }

    return formatted;
}

function safeLanguage(language) {
    if (typeof language !== 'string') return 'plaintext';
    return /^[A-Za-z0-9_+#-]{1,32}$/.test(language) ? language : 'plaintext';
}

export function detectCodeBlocks(text) {
    const codeBlocks = [];
    const processedText = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (_full, language, code) => {
        codeBlocks.push({
            language: safeLanguage(language),
            code: code.trim(),
            explanation: []
        });
        return `[CODE_BLOCK_${codeBlocks.length - 1}]`;
    });

    return { text: processedText, codeBlocks };
}

function assistantText(message) {
    if (!message || typeof message !== 'object') return '';
    if (typeof message.content === 'string' && message.content.trim()) return message.content;
    if (typeof message.reasoning === 'string' && message.reasoning.trim()) return message.reasoning;
    return '';
}

async function readErrorDetail(response) {
    try {
        const body = await response.json();
        const detail = body?.error?.message || body?.error?.code || '';
        return String(detail).slice(0, 300);
    } catch {
        return '';
    }
}

async function completeChat({ provider, messages, referer }) {
    const apiKey = apiKeyFor(provider.id);
    if (!apiKey) {
        throw new ChatError('config', `Missing API key for ${provider.name}.`);
    }

    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`
    };
    if (provider.referer) {
        headers['HTTP-Referer'] = referer || envValue('APP_URL') || 'http://localhost:8787';
        headers['X-Title'] = 'DeepChat';
    }

    let response;
    try {
        response = await fetch(provider.endpoint, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                model: provider.model,
                messages,
                temperature: 0.7,
                max_tokens: MAX_OUTPUT_TOKENS
            }),
            signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
        });
    } catch (error) {
        console.error('AI request error:', error?.name || 'Error');
        throw new ChatError('upstream', 'The AI request failed. Check your connection and try again.');
    }

    if (!response.ok) {
        const detail = await readErrorDetail(response);
        console.error('AI request failed', response.status, detail);
        throw new ChatError('upstream', 'The AI request failed. Check your connection and try again.');
    }

    let data;
    try {
        data = await response.json();
    } catch {
        throw new ChatError('upstream', 'The AI request failed. Check your connection and try again.');
    }

    const text = assistantText(data?.choices?.[0]?.message);
    if (!text) {
        throw new ChatError('upstream', 'The model returned an empty reply. Try again.');
    }
    return text;
}

async function explainCodeBlock(block, provider, referer) {
    try {
        const explanation = await completeChat({
            provider,
            referer,
            messages: [{
                role: 'user',
                content: `Explain this ${block.language} code in short lines. Describe what each important part does.\n\n${block.code}`
            }]
        });
        return explanation.split('\n').map((line) => line.trim()).filter(Boolean);
    } catch (error) {
        console.error('Code explanation error:', error?.name || 'Error');
        return ['Unable to generate an explanation. Try again.'];
    }
}

export async function sendChat({
    messages,
    provider = 'DeepSeek',
    explainCode = false,
    referer
} = {}) {
    if (explainCode !== undefined && typeof explainCode !== 'boolean') {
        throw new ChatError('validation', 'explainCode must be true or false.');
    }

    const selected = providerById(provider);
    const formatted = normalizeMessages(messages);
    const rawText = await completeChat({
        provider: { ...selected, id: provider },
        messages: formatted,
        referer
    });
    const result = detectCodeBlocks(rawText);

    if (explainCode) {
        for (const block of result.codeBlocks) {
            if (block.language !== 'plaintext') {
                block.explanation = await explainCodeBlock(block, { ...selected, id: provider }, referer);
            }
        }
    }

    return result;
}
