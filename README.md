# Thuk

Personal expense tracker — iOS app + AI backend.
Log expenses by typing, talking, or sharing a screenshot. Splits, budgets, analytics.

**Stack:** FastAPI · LangGraph · Groq · Gemini · SwiftUI  
**Hosting:** Koyeb (app) · Supabase (PostgreSQL) · Upstash (Redis) · **$0/month**

---

## What it does

- **Chat:** "500 for lunch" or "1200 dinner split with Rahul and Priya"
- **Voice:** Hold mic → speak → logs automatically
- **Screenshot:** Share any bank SMS or receipt → extracts and logs the transaction
- **Analytics:** Spend by category, daily chart, month-over-month
- **Splits & debts:** Track who owes what, settle with one tap
- **Budget:** Set a monthly limit, get warned when close

---

## Prerequisites

Before starting, create accounts on these (all free, no credit card):

| Service | What for | Sign up |
|---------|----------|---------|
| Supabase | PostgreSQL database | supabase.com |
| Upstash | Redis | upstash.com |
| Groq | Primary LLM | console.groq.com |
| Koyeb | App hosting | koyeb.com |

And these (free tier, but credit card may be needed for billing account):

| Service | What for | Sign up |
|---------|----------|---------|
| Google AI Studio | Gemini (image processing) | aistudio.google.com |
| OpenAI | Whisper voice transcription only | platform.openai.com |

---

## Part 1 — External Services

### 1.1 Supabase — PostgreSQL

1. Go to **supabase.com** → sign in with GitHub → **New project**
2. Name: `thuk` · Region: closest to you · set a DB password · **Create project**
3. Wait ~2 minutes
4. **Project Settings → Database → Connection string → URI** → copy it
5. Replace `postgresql://` with `postgresql+asyncpg://`

Your `DATABASE_URL` will look like:
```
postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
```

> **Note:** Free projects pause after 7 days of no activity. Resume from the dashboard or just make any API call — it wakes up automatically.

---

### 1.2 Upstash — Redis

1. Go to **upstash.com** → sign in with GitHub → **Create database**
2. Name: `thuk` · region: closest to you · **Create**
3. Copy the **Redis URL** from the database page (starts with `rediss://`)

Your `REDIS_URL` will look like:
```
rediss://default:[PASSWORD]@[ENDPOINT].upstash.io:6379
```

---

### 1.3 Groq — LLM API key

1. Go to **console.groq.com** → sign in → **API Keys → Create API Key**
2. Copy the key (starts with `gsk_`)

Free tier: 14,400 requests/day on fast models. More than enough.

---

### 1.4 Google AI Studio — Gemini API key

1. Go to **aistudio.google.com/apikey** → **Create API key**
2. Copy the key (starts with `AIza`)

Used for image/receipt processing. Free tier: 500 requests/day.

---

### 1.5 OpenAI — for Whisper (voice only)

1. Go to **platform.openai.com** → API keys → **Create new secret key**
2. Copy the key (starts with `sk-`)

Only used for voice transcription. Usage is minimal — a few cents per month at most for personal use.

---

## Part 2 — Backend: Local Setup

```bash
git clone <your-repo-url>
cd Thuk

# Install dependencies
pip install -e .

# Copy and fill in environment variables
cp .env.example .env
```

Open `.env` and fill in every value:

```env
DATABASE_URL=postgresql+asyncpg://...      # from Supabase
REDIS_URL=rediss://...                     # from Upstash
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
JWT_SECRET=                                # generate below
ENCRYPTION_KEY=                            # generate below
WEBHOOK_BASE_URL=http://localhost:8000     # update after deploying
```

Generate the two secret keys:
```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Run migrations and start:
```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API is live at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

## Part 3 — Backend: Deploy to Koyeb

### 3.1 Push your code to GitHub

Koyeb deploys from GitHub. Make sure your repo is pushed:
```bash
git add .
git commit -m "ready for deployment"
git push origin main
```

### 3.2 Create the Koyeb service

1. Go to **koyeb.com** → sign in with GitHub → **Create Service**
2. **GitHub** → select your repo → branch: `main`
3. Koyeb detects the `Dockerfile` automatically — leave build settings as-is
4. Configure:
   - **Port:** `8000`
   - **Health check path:** `/health`
   - **Instance:** Free (nano)

### 3.3 Set environment variables

In the Koyeb dashboard under **Environment variables**, add all of these:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Your Supabase `postgresql+asyncpg://...` URL |
| `REDIS_URL` | Your Upstash `rediss://...` URL |
| `GROQ_API_KEY` | Your Groq key |
| `GEMINI_API_KEY` | Your Gemini key |
| `OPENAI_API_KEY` | Your OpenAI key |
| `JWT_SECRET` | The hex string you generated |
| `ENCRYPTION_KEY` | The Fernet key you generated |
| `WEBHOOK_BASE_URL` | Leave blank for now — fill in after first deploy |

### 3.4 Deploy

Click **Deploy**. First build takes ~3 minutes.

Once deployed, Koyeb gives you a URL like:
```
https://thuk-abc123.koyeb.app
```

Go back to **Environment variables** → set `WEBHOOK_BASE_URL` to that URL → **Redeploy**.

### 3.5 Verify

```bash
curl https://thuk-abc123.koyeb.app/health
# → {"status": "ok", "db": "ok"}
```

Migrations run automatically on every deploy via `start.sh`. You never need to run them manually.

---

## Part 4 — iOS App: Xcode Setup

### 4.1 Requirements

- Xcode 15 or later
- Your iPhone running iOS 17+
- Apple ID (free — no paid developer account needed for personal use)

### 4.2 Create the Xcode project

1. Open Xcode → **File → New → Project**
2. **iOS → App** → Next
3. Fill in:
   - **Product Name:** `Thuk`
   - **Team:** your personal Apple ID (shows as *"Your Name (Personal Team)"*)
   - **Bundle Identifier:** `com.yourname.thuk` — pick any reverse-domain format, must be unique
   - **Interface:** SwiftUI
   - **Language:** Swift
   - **Minimum Deployments:** iOS 17.0
4. Save **inside the `ios/` folder** of this repo

### 4.3 Add the source files

Xcode creates a default `ContentView.swift` — **delete it** (Move to Trash).

Then:
1. Right-click the **Thuk** group in the navigator → **Add Files to "Thuk"**
2. Select all folders inside `ios/Thuk/`:
   - `Design/`
   - `Features/`
   - `Network/`
   - `Utilities/`
   - `ThukApp.swift`
3. **"Copy items if needed"** → unchecked (files already live here)
4. **"Create groups"** → selected
5. Click **Add**

### 4.4 Add privacy entries to Info.plist

1. Select the **Thuk** project in the navigator → **Thuk** target → **Info** tab
2. Add these three keys (hover any row → click `+`):

| Key | Value |
|-----|-------|
| Privacy - Microphone Usage Description | `Thuk uses the microphone to record voice notes describing expenses.` |
| Privacy - Camera Usage Description | `Thuk uses the camera to photograph receipts and transaction screenshots.` |
| Privacy - Photo Library Usage Description | `Thuk reads photos so you can share bank transaction screenshots.` |

### 4.5 Point to your backend

Open `ios/Thuk/Network/APIClient.swift` and update line 9:

```swift
private let kBaseURL = URL(string: "https://thuk-abc123.koyeb.app")!
```

Replace `thuk-abc123.koyeb.app` with your actual Koyeb URL.

### 4.6 Add the Share Extension target

This lets the app appear in the iOS share sheet when you share any image.

1. **File → New → Target → iOS → Share Extension** → Next
2. **Product Name:** `ThukShare` → same Team → **Finish** → when prompted, click **Cancel** (don't activate the scheme)
3. Delete the generated `ShareViewController.swift` and `MainInterface.storyboard` that Xcode created
4. Add the files from `ios/ThukShare/`:
   - Right-click **ThukShare** group → **Add Files to "ThukShare"**
   - Select `ShareViewController.swift`, `MainInterface.storyboard`, `Info.plist`
   - Uncheck "Copy items if needed" → **Add**
5. Select **ThukShare** target → **Build Settings** → search `INFOPLIST_FILE` → set to `ThukShare/Info.plist`

### 4.7 Add App Groups (lets Share Extension read your auth token)

**For the Thuk target:**
1. Select **Thuk** target → **Signing & Capabilities** → `+ Capability` → **App Groups**
2. Click `+` → add: `group.com.yourname.thuk`

**For the ThukShare target:**
1. Select **ThukShare** target → same steps → add the same: `group.com.yourname.thuk`

### 4.8 Update identifiers in two files

Replace `yourname` with whatever you used in your bundle identifier throughout these files:

`ios/Thuk/Utilities/Keychain.swift` lines 8–9:
```swift
static let accessGroup = "group.com.yourname.thuk"
private static let service = "com.yourname.thuk"
```

`ios/ThukShare/ShareViewController.swift` lines 137–138:
```swift
private static let service     = "com.yourname.thuk"
private static let accessGroup = "group.com.yourname.thuk"
```

`ios/ThukShare/ShareViewController.swift` line ~172 (upload URL):
```swift
let url = URL(string: "https://thuk-abc123.koyeb.app/api/chat/image")!
```

---

## Part 5 — Running on Your iPhone (Free Apple ID)

### 5.1 One-time device setup

**Add your Apple ID to Xcode:**
Xcode → **Settings** (Cmd+,) → **Accounts** → `+` → **Apple ID** → sign in with the Apple ID on your iPhone

**Trust your Mac:**
Connect iPhone via USB → tap **Trust This Computer** on the phone → enter passcode

**Enable Developer Mode on iPhone:**
Settings → **Privacy & Security** → **Developer Mode** → turn on → iPhone restarts

### 5.2 Build and run

Select your iPhone in the Xcode toolbar → **Cmd+R**

**First run only:** Xcode succeeds but the app won't open — it says "Untrusted Developer". Fix it on the iPhone:

Settings → **General** → **VPN & Device Management** → tap your Apple ID email → **Trust**

Then hit **Cmd+R** again. Done.

### 5.3 The 7-day certificate renewal

Free Apple ID certificates expire every 7 days. When the app stops launching:

1. Plug iPhone into Mac
2. Open Xcode, select your iPhone
3. **Cmd+R**

Takes under a minute. Your data and login session are unaffected.

---

## Part 6 — Share Extension: Test it

1. Build the main **Thuk** scheme first (Cmd+B)
2. Switch to the **ThukShare** scheme in the toolbar → Run
3. Xcode asks which app to launch → choose **Photos**
4. Long-press any photo → **Share** → scroll down → **Thuk** appears
5. Tap it — a card appears showing "Processing receipt..." → "Added to Thuk" → auto-dismisses

---

## Part 7 — Sharing with Friends (when ready)

Requires an **Apple Developer account ($99/year)**.

1. Register at **developer.apple.com/enroll**:
   - Choose **Individual** (not Company)
   - Use the same Apple ID as on your iPhone
   - $99/year charged immediately
   - Usually activates within minutes

2. Archive and upload:
   - Select **Any iOS Device** in Xcode toolbar
   - **Product → Archive**
   - **Distribute App → TestFlight & App Store** → upload

3. In **App Store Connect** → **TestFlight** → add friends' Apple ID emails

4. Friends install **TestFlight** from the App Store → accept invite email → install Thuk

Builds expire after 90 days. Upload a new one to refresh — no re-review needed for minor updates.

---

## Redeploying the backend

Push to `main` → Koyeb auto-deploys in ~2 minutes. Migrations run automatically.

```bash
git add .
git commit -m "your changes"
git push origin main
```

---

## Local development with Docker

Run the full stack locally without external services:

```bash
cp .env.example .env
# Fill in GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, JWT_SECRET, ENCRYPTION_KEY
# Leave DATABASE_URL and REDIS_URL as-is — Docker Compose provides them

docker compose up
```

API at `http://localhost:8000` · Docs at `http://localhost:8000/docs`

---

## Environment variables reference

| Variable | Required | How to get |
|----------|----------|------------|
| `DATABASE_URL` | Yes | Supabase → Settings → Database → URI (asyncpg format) |
| `DB_SSL` | Yes | `true` for Supabase, `false` for local Docker |
| `REDIS_URL` | Yes | Upstash → database page → Redis URL |
| `GROQ_API_KEY` | Yes | console.groq.com → API Keys |
| `GEMINI_API_KEY` | Yes | aistudio.google.com/apikey |
| `OPENAI_API_KEY` | Yes | platform.openai.com → API keys |
| `JWT_SECRET` | Yes | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Yes | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `WEBHOOK_BASE_URL` | Yes | Your Koyeb app URL e.g. `https://thuk-abc123.koyeb.app` |
| `DEBUG` | No | `true` for verbose logs (default: `false`) |

---

## Architecture

```
iPhone app (SwiftUI)
    │
    │  REST + multipart
    ▼
FastAPI (Koyeb)
    ├── Auth (JWT + bcrypt)
    ├── LangGraph supervisor
    │     ├── Intent classifier  → Groq llama-3.1-8b-instant
    │     ├── Expense agent      → Groq llama-3.3-70b-versatile
    │     ├── Text2SQL agent     → Groq llama-3.3-70b-versatile
    │     ├── Budget agent
    │     ├── Split agent
    │     └── Export agent
    ├── Image processor          → Gemini 2.5 Flash
    ├── Voice processor          → OpenAI Whisper
    ├── PostgreSQL               → Supabase
    └── Redis                    → Upstash
```
