# Enterprise Intelligence Layer (`b2b-agentic-enterprise`)

An autonomous, 6-agent orchestration system that feeds an SQLite database (`pipeline.db`) to drive enterprise B2B sales operations. Inspired by the **Hermes agent framework philosophy**, all agents communicate **EXCLUSIVELY** by reading and updating stateful rows in SQLite. Outbound emails are dispatched via **Resend API** to bypass SMTP restrictions, while inbound replies are triaged via Gmail IMAP reading strictly from the dedicated `B2B_Pipeline` folder.

Features a **God Mode Retro Command Center Dashboard** (`dashboard.py`) and a background **Autonomous Scheduler** (`scheduler.py`).

---

## 🏛 Framework Philosophy & Design Architecture

- **Stateful DB Communication**: Agents operate as isolated, object-oriented micro-services that exchange state exclusively via `pipeline.db`.
- **Resend API Outbound Dispatch**: `src/dispatcher.py` reads `approved_for_dispatch` leads, transmits via `resend.Emails.send()` with a 60-120s sleep jitter, and updates status to `dispatched`.
- **Gmail Sandbox IMAP Triage & Bounce Detection**: `src/agents/triage_agent.py` connects to Gmail IMAP and reads unread replies strictly from the dedicated `B2B_Pipeline` folder. Automated bouncebacks (`Mailer-Daemon`, `Postmaster`, `Undeliverable`) are immediately marked `bounced` without wasting LLM tokens.
- **Autonomous Scheduler**: `scheduler.py` runs continuous background loops (Triage every 2h, Dispatch every 1h, CEO/Scout/Copywriter Intelligence cycle every 4h).
- **God Mode Retro Dashboard**: `dashboard.py` built with Streamlit & Pandas featuring a pixelated 8-bit disco-techno hacker UI, live metric status array, pipeline lead matrix, pre-dispatch draft inspector, audit logs, and manual override controls.

```
                  +-----------------------------------+
                  |      SQLite DB: pipeline.db       |
                  +-----------------------------------+
                     ^     ^     ^     ^     ^     ^
                     |     |     |     |     |     |
    +----------------+     |     |     |     |     +----------------+
    |                      |     |     |     |                      |
[Triage Agent]             |     |     |     |               [PR Guardian Agent]
 (Bounce & Sentiment)      |     |     |     |                      ^
    ^                      v     |     v     |                      |
[B2B_Pipeline IMAP]  [Analytics Agent] [Scout Agent]          [Sales Agent]
                                                                    |
                                                                    v
                                                          [Resend API Dispatcher]
```

---

## 🤖 The 6 Enterprise Agents & System Tools

### 1. Analytics Agent (`src/agents/analytics_agent.py`)
- Reads `leads` and `replies` tables from `pipeline.db`.
- Calculates total reply rates, positive conversion ratios, and sentiment metrics per service lane (`SolidWorks DFM`, `ROS 2 / Gazebo`, `TinyML / INT8 Quantization`, `Cascade Pneumatics`).

### 2. Strategy Agent (`src/agents/strategy_agent.py`)
- **The CEO Agent**. Reads the Analytics JSON summary.
- Formulates daily search focus and updates `campaign_directives` table in SQLite with target keywords and allocation percentages.

### 3. Scout Agent (`src/agents/scout_agent.py`)
- Reads active directive from `campaign_directives`.
- Executes web queries using `duckduckgo-search` to locate targeted hardware startups, robotics labs, or mechanical engineering job postings.
- Applies strict B2B safety domain filtering before writing leads (`status: 'scouted'`).

### 4. Sales Agent / Copywriter (`src/agents/sales_agent.py`)
- Reads `'scouted'` rows from `leads`. Scrapes company website context.
- **FOUNDER GROUNDING**: System prompt grounds copy in founder's authentic mechatronics engineering background (UET Faisalabad, SolidWorks DFM, ROS 2 / Gazebo, TinyML / INT8 quantization on ESP32/STM32, cascade pneumatics).
- Generates a **maximum 65-word** peer-to-peer cold pitch with zero fluff (`status: 'drafted'`).

### 5. PR Guardian Agent (`src/agents/pr_agent.py`)
- **The Compliance Officer**. Reads `'drafted'` rows.
- Audits copy against a spam-lexicon (*"free", "revolutionary", "synergy", "guaranteed", "no risk", "100%"*).
- Enforces strict word count constraint (< 75 words).
- Approves compliant pitches (`status: 'approved_for_dispatch'`) or kicks back non-compliant pitches (`status: 'scouted'`).

### 6. Triage Agent (`src/agents/triage_agent.py`)
- Connects via IMAP to inspect incoming unread email replies in folder `B2B_Pipeline`.
- **Bounce Detection**: Detects `Mailer-Daemon`, `Postmaster`, or `Undeliverable` notices and immediately marks lead status as `bounced` without consuming LLM tokens.
- Classifies non-bounce replies into `Positive`, `Negative`, `Pricing`, `Unsubscribed`, or `Out of Office`.

### 🚀 Resend Email Dispatcher (`src/dispatcher.py`)
- Transmits approved leads via `resend.Emails.send()` set from `"Riyan <eng@muhammadriyan.tech>"`.
- Applies a **60–120 second random sleep jitter** between dispatches (1s in mock mode).

### ⏰ Autonomous Scheduler (`scheduler.py`)
- Background runner setting up scheduled intervals for Triage (2h), Dispatcher (1h), and Intelligence Cycle (4h).

### 👾 God Mode Command Center (`dashboard.py`)
- Local Streamlit command center (`streamlit run dashboard.py`) with retro 8-bit disco-techno styling, scanlines, neon glowing borders, pipeline matrix, pre-dispatch draft inspector, and manual override trigger buttons.

---

## 🗄 Database Schema (`pipeline.db`)

Initialized and managed by `database.py`:
- `leads`: ID, company_name, url, decision_maker, target_keyword, service_lane, email_body, subject, status (`scouted`, `drafted`, `approved_for_dispatch`, `dispatched`, `replied`, `bounced`), compliance_notes, timestamps.
- `campaign_directives`: ID, directive_text, target_sectors, focus_service_lane, search_keywords, allocation_percentage, reasoning, status (`active`, `archived`), timestamp.
- `replies`: ID, lead_id, sender_email, subject, body, sentiment, service_lane, received_at.
- `analytics_logs`: ID, summary_json, created_at.

---

## 🚀 Getting Started

### 1. Installation

```bash
git clone https://github.com/Haque45/b2b-agentic-enterprise.git
cd b2b-agentic-enterprise
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Copy `.env.example` to `.env` and set your API keys:

```ini
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-v1-...
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=Riyan <eng@muhammadriyan.tech>
DB_PATH=pipeline.db
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_existing_gmail@gmail.com
IMAP_PASSWORD=your_16_digit_app_password
IMAP_FOLDER=B2B_Pipeline
```

### 3. Usage Commands

- **Launch "God Mode" Retro Dashboard**:
  ```bash
  streamlit run dashboard.py
  ```

- **Start Autonomous Scheduler**:
  ```bash
  python scheduler.py
  ```

- **Run Single 6-Agent Pipeline Pass**:
  ```bash
  python main.py --run-once
  ```

- **Dispatch Approved Leads via Resend API**:
  ```bash
  python main.py --dispatch
  ```

- **View Current Pipeline Database Status**:
  ```bash
  python main.py --status
  ```

---

## 📜 License
MIT License. Developed for Autonomous Enterprise Agentic Workflows.
