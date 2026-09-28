# 🤖 Jarvis — Your Local AI Assistant

> A modular local-first AI assistant that combines voice control, messaging automation, local LLM reasoning, and Google Workspace actions.

## ✨ Features
- Voice assistant runtime with wake-word style flow, STT, and TTS.
- Local LLM execution via Ollama (primary + secondary brain routing).
- Telegram bot interface for text-first assistant control.
- WhatsApp automation agent (message draft/send + chat loop modes).
- Browser automation agent (Playwright-powered actions).
- RAG agent for document Q&A.
- Google Workspace bridge (Gmail, Drive, Docs, Calendar, Sheets, Tasks) via Apps Script.
- n8n webhook bridge for orchestration workflows.
- Tool system for weather, app/web launch, laptop controls, and utility automations.
- Active window detection - Know what app/website you're viewing (local-only, not logged remotely).
- Memory system with SQLite default and optional PostgreSQL backend.
- MCP client scaffolding for tools like DuckDuckGo/GitHub/Obsidian.
- Dockerfile + docker-compose support for containerized runs.

## Architecture Overview

```text
User (Voice / Telegram / WhatsApp)
          |
          v
   Jarvis.py Runtime
          |
          v
  Primary/Secondary Brain Router
          |
   +------+------+-----------------------------+
   |             |                             |
   v             v                             v
WhatsApp Agent  Browser Agent               RAG Agent
   |             |                             |
   +-------------+-----------------------------+
                     |
                     v
            Tools / Automations Layer
                     |
         +-----------+---------------------------+
         |                                       |
         v                                       v
   Ollama Local LLM                       External Bridges
(qwen / mistral / others)          (Google Apps Script, n8n, MCP)
                     |
                     v
                Final Response
```

## 📋 Prerequisites
- OS:
  - Windows 10/11 (recommended for this repo as-is)
  - Linux/macOS supported with dependency adjustments
  - WSL2 optional on Windows if you prefer Linux tooling
- Python 3.10+
- Docker Desktop + Docker Compose plugin
- Ollama
- Node.js (optional, useful for MCP/browser tooling ecosystems)
- Google account with access to the Workspace services you want
- Telegram account (for bot setup)
- WhatsApp account (WhatsApp Web automation is built-in)
- WhatsApp Business API (optional only if you extend to Cloud API tokens)

## 🚀 Installation & Setup

### Step 1 — Clone the Repository
```bash
git clone https://github.com/pranithjarvis/Jarvis.git
cd Jarvis
```

### Step 2 — Install Ollama & Pull a Model

Linux/macOS:
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model(s)
ollama pull qwen3:4b
ollama pull qwen2.5:1.5b
# optional fallback
ollama pull mistral

# Start Ollama server
ollama serve
```

Windows (PowerShell):
```powershell
# Install with winget
winget install Ollama.Ollama

# Pull model(s)
ollama pull qwen3:4b
ollama pull qwen2.5:1.5b
ollama pull mistral

# Start Ollama server
ollama serve
```

### Step 3 — Install Docker & Docker Compose
- Official docs: https://docs.docker.com/get-docker/

Windows (recommended):
- Install Docker Desktop from official docs.
- Ensure WSL2 backend is enabled (if prompted).

Quick check:
```bash
docker --version
docker compose version
```

### Step 4 — Set Up Environment Variables
```bash
cp .env.example .env
# Now open .env and fill in your values
```

| Variable | Description | Where to get it |
|---|---|---|
| TELEGRAM_BOT_TOKEN | Telegram bot token used by telegram_bot.py | @BotFather on Telegram |
| APPS_SCRIPT_URL | Deployed Google Apps Script Web App URL | script.google.com deployment panel |
| GEMINI_API_KEY | Optional Gemini API key for future fallback/extension | aistudio.google.com |
| GOOGLE_API_KEY | Optional Google API key for custom integrations | Google Cloud Console |
| WHATSAPP_TOKEN | Optional WhatsApp Business API token | Meta Developer Portal |
| WHATSAPP_PHONE_NUMBER_ID | Optional Cloud API phone number id | Meta Developer Portal |
| WHATSAPP_BUSINESS_ACCOUNT_ID | Optional WABA id | Meta Developer Portal |
| PG_HOST | PostgreSQL host (optional memory backend) | Your DB host |
| PG_PORT | PostgreSQL port | Your DB config |
| PG_DATABASE | PostgreSQL database name | Your DB config |
| PG_USER | PostgreSQL username | Your DB config |
| PG_PASSWORD | PostgreSQL password | Your DB config |
| N8N_BASE_URL | n8n base URL if you run webhook bridge flows | Your n8n deployment |
| OLLAMA_HOST | Ollama host if non-default | Your Ollama instance |

### Step 5 — Set Up Google Workspace via Apps Script

For a detailed guide on building the Google Workspace bridge, see:
**[CODE I USED for connecting JARVIS with Google WORKSPACE - Notion](https://www.notion.so/CODE-I-USED-for-connecting-JARVIS-with-google-WORKSPACE-2fb5f08470688073b7a8f54c25dfa1d6)**

Quick setup:
1. Go to https://script.google.com
2. Create a new project
3. Paste this Apps Script code:

```javascript
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents || "{}");
    var action = body.action || "";
    var params = body.params || {};

    var handlers = {
      test: function() { return { message: "bridge ok", ts: new Date().toISOString() }; },
      gmail_list_unread: function(p) {
        var max = Number(p.limit || 10);
        return GmailApp.search("is:unread", 0, max).map(function(t) {
          var m = t.getMessages()[0];
          return { threadId: t.getId(), subject: m.getSubject(), from: m.getFrom(), date: m.getDate() };
        });
      },
      gmail_search: function(p) {
        var q = (p.query || "").trim() || "in:inbox";
        return GmailApp.search(q, 0, Number(p.limit || 10)).map(function(t) {
          var m = t.getMessages()[0];
          return { threadId: t.getId(), subject: m.getSubject(), from: m.getFrom(), snippet: m.getPlainBody().slice(0, 200) };
        });
      },
      gmail_send: function(p) {
        GmailApp.sendEmail(p.to, p.subject || "(No subject)", p.body || "", { cc: p.cc || "", bcc: p.bcc || "" });
        return { sent: true };
      },
      drive_list_files: function(p) {
        var out = [], it = DriveApp.getFiles(), max = Number(p.limit || 20);
        while (it.hasNext() && out.length < max) {
          var f = it.next();
          out.push({ id: f.getId(), name: f.getName(), mimeType: f.getMimeType() });
        }
        return out;
      },
      calendar_get_events: function(p) {
        var cal = CalendarApp.getDefaultCalendar();
        var start = p.timeMin ? new Date(p.timeMin) : new Date();
        var end = p.timeMax ? new Date(p.timeMax) : new Date(Date.now() + 86400000);
        return cal.getEvents(start, end).map(function(ev) {
          return { id: ev.getId(), title: ev.getTitle(), start: ev.getStartTime(), end: ev.getEndTime(), location: ev.getLocation() };
        });
      },
      calendar_create_event: function(p) {
        var cal = CalendarApp.getDefaultCalendar();
        var ev = cal.createEvent(p.title || "Untitled Event", new Date(p.startTime), new Date(p.endTime), {
          description: p.description || "", location: p.location || ""
        });
        return { id: ev.getId(), title: ev.getTitle() };
      },
      sheets_read: function(p) {
        var ss = SpreadsheetApp.openById(p.spreadsheetId);
        var sh = ss.getSheetByName(p.sheetName || "Sheet1");
        var range = p.range || sh.getDataRange().getA1Notation();
        return sh.getRange(range).getValues();
      },
      sheets_write: function(p) {
        var ss = SpreadsheetApp.openById(p.spreadsheetId);
        var sh = ss.getSheetByName(p.sheetName || "Sheet1");
        sh.getRange(p.range).setValues(p.values || [[]]);
        return { written: true };
      },
      sheets_append: function(p) {
        var ss = SpreadsheetApp.openById(p.spreadsheetId);
        var sh = ss.getSheetByName(p.sheetName || "Sheet1");
        (p.values || []).forEach(function(row) { sh.appendRow(row); });
        return { appended: true };
      }
    };

    if (!handlers[action]) return jsonOut({ status: "error", error: "Unknown action: " + action });
    return jsonOut({ status: "success", action: action, data: handlers[action](params) });
  } catch (err) {
    return jsonOut({ status: "error", error: String(err) });
  }
}

function jsonOut(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
```

4. Deploy as a Web App:
   - Execute as: Me
   - Who has access: Anyone or Anyone with Google Account
5. Copy the deployment Web App URL
6. Paste it into your `.env` as: `APPS_SCRIPT_URL="YOUR_DEPLOYMENT_URL_HERE"`
7. Authorize the script when prompted

**Privacy Note**: Your APPS_SCRIPT_URL is stored only in `.env` and never committed to version control. All Google Workspace actions are triggered locally by you.

Google services used in this bridge:
- Gmail
- Google Drive
- Google Docs
- Google Calendar
- Google Sheets
- Google Tasks (optional, via advanced service)

### Step 6 — Set Up Telegram Bot
1. Open Telegram and search @BotFather
2. Send `/newbot` and follow prompts
3. Copy token and set `TELEGRAM_BOT_TOKEN` in `.env`
4. Optional: configure bot commands via `/setcommands`

### Step 7 — Set Up WhatsApp (Optional)
- Built-in repo flow uses WhatsApp Web automation.
- Optional Cloud API setup:
  - Create Meta app in Meta Developer Portal.
  - Add WhatsApp product.
  - Get access token, phone number id, and business account id.
  - Fill optional WhatsApp fields in `.env`.

### Step 8 — Run with Docker
```bash
docker-compose up --build
```

### Step 8 (Alternative) — Run without Docker
```bash
pip install -r requirements.txt
python Jarvis.py
```

## 📁 Project Structure

```text
Jarvis/
├── Jarvis.py
├── telegram_bot.py
├── Brain/
│   ├── primary_brain.py
│   ├── secondary_brain.py
│   ├── google_workspace_client.py
│   └── Memory/
├── Agents/
│   ├── WhatsApp_Agent/
│   ├── Browser_Agent/
│   └── RAG_Agent/
├── Tools/
├── Automations/
│   └── Webhooks/
├── apps_script/
│   └── jarvis_bridge.gs
├── DATA/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

## 🔧 Configuration Reference

| Area | File | Key Options |
|---|---|---|
| App runtime | Jarvis.py | startup threads, popup mode, Telegram thread bootstrap |
| Telegram | telegram_bot.py | TELEGRAM_BOT_TOKEN, command handlers |
| Workspace bridge | Brain/google_workspace_client.py | APPS_SCRIPT_URL |
| Memory backend | Brain/Memory/config.py | DB_MODE, SQLITE_PATH, PG_* |
| WhatsApp automation | Agents/WhatsApp_Agent/* | contacts file, web automation flow |
| n8n bridge | Automations/Webhooks/n8n_bridge.py | WEBHOOK_HOST, WEBHOOK_PORT, N8N_BASE_URL |
| Model prewarm | Brain/model_prewarm.py | model list and warmup behavior |

## 🧪 Testing
- Core startup:
  - `python Jarvis.py`
  - Confirm no crash and `input.txt` is monitored.
- Telegram bot:
  - Set `TELEGRAM_BOT_TOKEN`, start app, send `/start`.
- Google Workspace:
  - Set `APPS_SCRIPT_URL`, run a simple Gmail/Calendar command through assistant.
- WhatsApp automation:
  - Ensure WhatsApp Web session works and a draft message opens.
- RAG agent:
  - Add a sample document in RAG data flow and run a query.
- Docker:
  - `docker-compose up --build` and verify container starts.

## 🐛 Troubleshooting
- Ollama not running:
  - Start with `ollama serve`.
- Missing model:
  - Run `ollama pull qwen3:4b` and `ollama pull qwen2.5:1.5b`.
- Telegram bot fails at startup:
  - Verify `TELEGRAM_BOT_TOKEN` and bot permissions.
- Google Apps Script errors:
  - Recheck deployment access settings and script authorization.
- Docker port conflicts:
  - Stop conflicting services or change compose/service ports.
- WhatsApp automation issues:
  - Remove stale local session data and re-login to WhatsApp Web.

## Privacy & Data Handling

### What Data Is Collected?
All data collection in Jarvis is **local-first and user-controlled**:

- **Voice Commands**: Processed locally via STT engine. Not sent to external servers unless explicitly configured.
- **Active Window Monitoring**: Detects which app/website you're viewing. **Stored locally only in RAM** — not logged to disk or sent anywhere.
- **Chat History**: Stored in local SQLite database (`DATA/jarvis_memory.db`) or optional PostgreSQL (if configured via `.env`).
- **Google Workspace Access**: Uses Apps Script bridge — your credential tokens never leave your `.env` file.
- **Telegram/WhatsApp**: Only active when explicitly enabled in `.env` with your own credentials.

### What Is NOT Collected?
- No telemetry or usage analytics sent to external servers.
- No keyboard logging or screen recording.
- No microphone always-on listening (only when you say the wake word).
- No browsing history sent anywhere.
- No private contacts/emails shared unless you explicitly request actions (e.g., "send email").

### Data Storage Locations
| Data | Location | Privacy |
|---|---|---|
| Chat history | `history/` + SQLite `DATA/jarvis_memory.db` | Local only |
| Voice logs | `logs/` | Local only |
| Memory/embeddings | `memory/` | Local only |
| Contacts | `DATA/contacts.json` | Local only |
| Config | `.env` | Should NOT be committed to git |

### Active Window Detection Details
The active window monitor (`Tools/Simple_Automations/active_window.py`):
- Detects which app you have open (e.g., "Edge", "VS Code", "Spotify")
- Extracts website names from browser titles (e.g., "YouTube", "Gmail")
- **Does NOT capture window content, clipboard, or detailed URLs**
- **Does NOT send this data anywhere**
- **Is printed to console only** for your awareness
- Can be disabled by removing the `start_window_monitor()` call from `Jarvis.py`

### Google Workspace Bridge Security
For detailed documentation on how the Google Apps Script bridge works and why it's secure, see:
**[CODE I USED for connecting JARVIS with Google WORKSPACE - Notion](https://www.notion.so/CODE-I-USED-for-connecting-JARVIS-with-google-WORKSPACE-2fb5f08470688073b7a8f54c25dfa1d6)**

Key points:
- Apps Script deployment URL is stored only in your `.env`
- Credentials are never logged or stored in version control
- Actions are triggered only when you explicitly make requests
- Google Workspace permissions are granted by you during Apps Script authorization

### Recommendations for Privacy
1. **Never commit `.env` to git** — use `.gitignore` to prevent this.
2. **Review Google Apps Script permissions** before deploying.
3. **Use strong passwords** for any API tokens/credentials.
4. **Periodically rotate credentials** for Telegram/WhatsApp/Gmail.
5. **If running with PostgreSQL**, ensure database is only accessible locally or via secure VPN.
6. **For team use**, consider a shared `.env.example` without actual tokens.

### Data Deletion
To completely clear all local data:
```bash
# Clear chat history
rm -r history/* chat_history/*

# Clear memory/embeddings
rm -r memory/*

# Clear logs
rm -r logs/*

# Reset SQLite database
rm DATA/jarvis_memory.db*
```

### Questions?
If you have privacy concerns about specific features, review the source code:
- Active window: `Tools/Simple_Automations/active_window.py`
- Memory storage: `Brain/Memory/memory_manager.py`
- Google bridge: `Brain/google_workspace_client.py`

## 🤝 Contributing
- Fork the repository.
- Create a feature branch.
- Keep secrets out of commits.
- Add tests or validation steps for behavior changes.
- Open a pull request with a clear summary.

## 📜 License

MIT License — feel free to use, modify, and distribute.

