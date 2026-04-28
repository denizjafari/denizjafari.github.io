# deniz-chat — Cloudflare Worker

This Worker powers the **Ask me about my past projects** chatbot on
denizjafari.com. It runs Llama 3.1 8B + BGE embeddings on Cloudflare
Workers AI's free tier, retrieves answers from your private docs in
`./public/corpus.json`, refuses anything off-topic, and forwards real
leads to your Gmail via FormSubmit.

**Cost:** $0 for the personal-site traffic profile. Workers AI free tier is
~10,000 "neurons" / day — well over a thousand chats — and the rest of the
stack (Workers, KV, Static Assets) is free up to 100K reqs/day.

**Where secrets live:** only on Cloudflare, set via `wrangler secret put`.
Nothing in this directory should ever contain a key.

---

## One-time setup

You'll need a free [Cloudflare account](https://dash.cloudflare.com/sign-up).

```bash
# 1. Install Wrangler
npm install -g wrangler

# 2. Sign in
wrangler login

# 3. From this directory, install dev deps (just wrangler)
cd worker
npm install
```

## Create a KV namespace (one-time)

KV stores cached embeddings and per-IP rate-limit counters.

```bash
wrangler kv:namespace create CHAT_KV
wrangler kv:namespace create CHAT_KV --preview
```

Each command prints an `id`. Copy them into `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "CHAT_KV"
id = "abc123…"          # from the first command
preview_id = "def456…"  # from the second
```

## (Optional) Wire lead capture to Gmail

When the chatbot detects a real lead with an email address, it POSTs to
FormSubmit, which forwards to your Gmail.

1. Visit https://formsubmit.co and enter `dnz.jfr@gmail.com`. They'll send
   you a **token URL** like `https://formsubmit.co/abcd1234efgh`.
2. Confirm the address from your inbox so future submissions don't bounce.
3. Set the URL as a Worker secret (it never lands in source):

   ```bash
   echo "https://formsubmit.co/abcd1234efgh" | wrangler secret put FORMSUBMIT_URL
   ```

If you skip this, the chatbot still works — leads simply aren't recorded.

## Build the corpus and deploy

From the **repo root**:

```bash
# (Re)build the corpus from me/*.pdf — outputs worker/public/corpus.json.
python3 scripts/build_chat_corpus.py
```

Then from `worker/`:

```bash
wrangler deploy
```

You'll get a URL like `https://deniz-chat.<your-subdomain>.workers.dev`.

## Wire the static site

Two edits in `contact.html`:

1. **Replace the placeholder** in:

   ```html
   <meta name="chat-api" content="https://deniz-chat.REPLACE-ME.workers.dev/chat">
   ```

   with your actual workers.dev URL.

2. **Update the CSP** so the browser is allowed to call it:

   ```html
   <!-- existing connect-src 'self' https://deniz-chat.*.workers.dev -->
   <!-- replace the wildcard with your exact worker host, e.g.: -->
   connect-src 'self' https://deniz-chat.your-subdomain.workers.dev;
   ```

That's it. Push the static change to GitHub Pages and the chatbot is live.

## Local development

```bash
# from worker/
wrangler dev --local
# Worker is live at http://127.0.0.1:8787
```

In another terminal, serve the static site so CSP & CORS work:

```bash
# from repo root
python3 -m http.server 8765
# open http://127.0.0.1:8765/contact.html
```

While developing, point the meta tag at `http://127.0.0.1:8787/chat`.

## Updating the corpus

Whenever you update or add a doc in `me/`:

```bash
python3 scripts/build_chat_corpus.py
cd worker && wrangler deploy
```

Embeddings are re-computed automatically on the first chat after deploy
(the corpus fingerprint changes), then cached in KV again.

## Useful commands

```bash
wrangler tail                  # live-tail logs from production
wrangler kv:key list --binding=CHAT_KV
wrangler secret list           # confirm FORMSUBMIT_URL is set
wrangler secret delete FORMSUBMIT_URL
```

## Files

```
worker/
├── package.json                 # wrangler dev dep only
├── wrangler.toml                # bindings: AI, ASSETS, KV, vars
├── README.md                    # this file
├── public/
│   └── corpus.json              # built by scripts/build_chat_corpus.py — text only, no keys
└── src/
    └── worker.js                # request handler — topic gate, RAG, generation, lead capture
```

## Safety notes

- The pre-classifier rejects off-topic questions before they hit the main
  model, so refusals are fast and cheap.
- The system prompt grounds replies strictly in the retrieved chunks; it's
  instructed to say "I don't have that on file" when context is missing.
- The corpus builder strips emails and phone numbers from chunks before
  bundling, so private contact info can't leak through the model.
- CORS is restricted to your domains; rate limit defaults to 10 messages
  per IP per minute. Bump `RATE_LIMIT_PER_MIN` in `wrangler.toml` if needed.
- No browser localStorage or cookies — chat history exists only in the
  open modal, then is forgotten.
