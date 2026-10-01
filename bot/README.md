# Woven Bot

Node microservice that feeds chat messages into the FastAPI ingest pipeline.

## Modes

| Mode | When | What runs |
|---|---|---|
| `mock` | Default, or `BOT_MODE=mock` | Express only — use `/trigger-mock` |
| `slack` | Slack env vars present, or `BOT_MODE=slack` | Express **plus** Slack Socket Mode listener |

Startup always logs: `Bot mode: mock|slack`

`/trigger-mock` keeps working in both modes.

## Environment variables

Create `bot/.env` (or add to the repo root `.env`):

```env
# Required for Slack mode
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_APP_TOKEN=xapp-...

# Optional
BOT_MODE=slack
PORT=3001
INGEST_URL=http://localhost:8000/api/ingest
```

## Run

```bash
cd bot
npm install
npm run dev
```

Mock path (no Slack needed):

```bash
curl http://localhost:3001/trigger-mock
```

## Slack app setup (Socket Mode)

### 1. Create the app
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Pick a workspace.

### 2. Enable Socket Mode
1. **Socket Mode** → toggle **Enable Socket Mode**.
2. Create an **App-Level Token** with scope `connections:write`.
3. Copy the `xapp-...` token → `SLACK_APP_TOKEN`.

### 3. Bot token + signing secret
1. **OAuth & Permissions** → install the app to your workspace.
2. Copy **Bot User OAuth Token** (`xoxb-...`) → `SLACK_BOT_TOKEN`.
3. **Basic Information** → **Signing Secret** → `SLACK_SIGNING_SECRET`.

### 4. Exact bot scopes (OAuth & Permissions → Bot Token Scopes)
Add these scopes:

| Scope | Why |
|---|---|
| `channels:history` | Read public channel messages |
| `channels:read` | Resolve channel names |
| `chat:write` | Optional; useful if you later reply |
| `users:read` | Resolve user display names |

If you also want private channels later (not required for this task):
- `groups:history`
- `groups:read`

### 5. Event subscriptions
1. **Event Subscriptions** → **Enable Events**.
2. Subscribe to bot events:
   - `message.channels` (public channel messages)
3. Socket Mode means you do **not** need a public Request URL.

### 6. Invite the bot
In each public channel you want ingested:

```
/invite @YourBotName
```

### 7. Start Woven + bot
1. FastAPI on `:8000`
2. `cd bot && npm run dev`
3. Confirm log: `Bot mode: slack`
4. Post a message in an invited public channel → watch FastAPI ingest logs

## Message mapping

Slack events are mapped to the Phase 1 schema:

```json
{
  "message_id": "...",
  "text": "...",
  "timestamp": "ISO-8601",
  "author": { "user_id": "...", "name": "...", "platform": "slack" },
  "channel": { "channel_id": "...", "name": "...", "platform": "slack" }
}
```

Then POSTed to `http://localhost:8000/api/ingest`.

Bot messages, subtypes, and empty text are ignored.
