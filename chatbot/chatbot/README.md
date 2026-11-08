# Chat backend

No screens. This folder calls DeepSeek (OpenRouter) and Groq. Another UI sends JSON and renders the reply.

## Run

From the project root:

```bash
npm run chat:server
```

The server listens on `http://127.0.0.1:8787`. It reads API keys from the environment, then from `.env.local` or `.env`. It does not override variables you already exported.

Accepted key names:

- `OPENROUTER_API_KEY` or `VITE_OPENROUTER_KEY`
- `GROQ_API_KEY` or `VITE_GROQ_KEY`

Optional:

- `PORT` (default `8787`)
- `CORS_ORIGIN` (default `http://localhost:5173`, comma-separated if the UI uses more than one origin)
- `APP_URL` (sent to OpenRouter as the referer)
- `CHAT_RATE_LIMIT` (default `30` posts per minute per address)

## HTTP

`GET /api/v1/health`

`GET /api/v1/providers`

`POST /api/v1/chat`

```json
{
  "provider": "DeepSeek",
  "explainCode": false,
  "messages": [
    {
      "role": "user",
      "content": "What does this file do?",
      "files": [{ "name": "main.py", "content": "print('hi')" }]
    }
  ]
}
```

`provider` is `DeepSeek` or `Groq`. Omit it to use DeepSeek. `explainCode` asks for a second call on each code block. Files must already be text. This server does not accept uploads.

Success:

```json
{
  "text": "It prints hi.",
  "codeBlocks": []
}
```

When the reply contains a fenced code block, `text` keeps a `[CODE_BLOCK_0]` marker and `codeBlocks` holds `{ language, code, explanation }`.

Failure:

```json
{ "error": { "code": "validation", "message": "Send at least one message." } }
```

`code` is `validation` (400), `forbidden` (403), `rate_limit` (429), `upstream` (502), `config` (503), or `internal` (500).

Example:

```bash
curl -s http://127.0.0.1:8787/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://localhost:5173' \
  -d '{"messages":[{"role":"user","content":"What is 2+2?"}]}'
```

## Import from Node

```js
import { sendChat, listProviders } from './chatbot/index.js';

const reply = await sendChat({
  provider: 'Groq',
  messages: [{ role: 'user', content: 'Hello' }]
});
```

Keep the API keys in this process. Do not put them in the UI bundle.
