# Enterprise Intelligence Layer (`b2b-agentic-enterprise`)

An autonomous, 6-agent orchestration system that feeds an SQLite database (`pipeline.db`) to drive enterprise B2B sales operations. Inspired by the **Hermes agent framework philosophy**, all agents communicate **EXCLUSIVELY** by reading and updating stateful rows in SQLite. Outbound emails are dispatched via **Resend API** to bypass SMTP restrictions, while inbound replies are triaged via Gmail IMAP reading strictly from the dedicated `B2B_Pipeline` folder.

---

## 🏛 Framework Philosophy & Design Architecture

- **Stateful DB Communication**: Agents operate as isolated, object-oriented micro-services that exchange state exclusively via `pipeline.db`.
- **Resend API Outbound Dispatch**: `src/dispatcher.py` reads `approved_for_dispatch` leads, transmits via `resend.Emails.send()` with a 60-120s sleep jitter, and updates status to `dispatched`.
- **Gmail Sandbox IMAP Triage**: `src/agents/triage_agent.py` connects to Gmail IMAP and reads unread replies strictly from the dedicated `B2B_Pipeline` folder (never default `INBOX`).
- **Strict Free Cloud Stack**:
  - `groq` SDK for Llama 3.1 70B/8B (Fast reasoning & scouting).
  - `requests` for OpenRouter free Hermes 3 tier (System prompt & instruction adherence).
  - `resend` SDK for HTTP email dispatch (`Riyan <eng@muhammadriyan.tech>`).
  - `duckduckgo-search` (`DDGS`) & `beautifulsoup4` for web data extraction & context scraping.
  - Deterministic offline fallbacks for zero-downtime demonstration without active cloud keys.

```
                  +-----------------------------------+
                  |      SQLite DB: pipeline.db       |
                  +-----------------------------------+
                     ^     ^     ^     ^     ^     ^
                     |     |     |     |     |     |
    +----------------+     |     |     |     |     +----------------+
    |                      |     |     |     |                      |
[Triage Agent]             |     |     |     |               [PR Guardian Agent]
    ^                      |     |     |     |                      ^
    |                      v     |     v     |                      |
[B2B_Pipeline IMAP]  [Analytics Agent] [Scout Agent]          [Sales Agent]
                                                                    |
                                                                    v
                                                          [Resend API Dispatcher]
```

---

## 🤖 The 6 Enterprise Agents & Dispatcher

### 1. Analytics Agent (`src/agents/analytics_agent.py`)
- Reads `leads` and `replies` tables from `pipeline.db`.
- Calculates total reply rates, positive conversion ratios, and sentiment metrics per service lane (`SolidWorks DFM`, `ROS 2 / Gazebo`, `TinyML / INT8 Quantization`, `Cascade Pneumatics`).
- Logs a structured JSON summary into the `analytics_logs` table.

### 2. Strategy Agent (`src/agents/strategy_agent.py`)
- **The CEO Agent**. Reads the Analytics JSON summary.
- Analyzes campaign metrics and formulates daily search focus (e.g. *"Shift 80% of today's search focus to 'SolidWorks DFM' due to a 4% higher positive reply rate"*).
- Updates the `campaign_directives` table in SQLite with target keywords, sector allocation, and CEO reasoning.

### 3. Scout Agent (`src/agents/scout_agent.py`)
- Reads active directive from `campaign_directives`.
- Executes web queries using `duckduckgo-search` to locate targeted hardware startups, robotics labs, or mechanical engineering job postings.
- Extracts company names, URLs, and decision-maker titles, inserting rows into `leads` table (`status: 'scouted'`).

### 4. Sales Agent / Copywriter (`src/agents/sales_agent.py`)
- Reads `'scouted'` rows from `leads`.
- Scrapes target company URLs using `requests` and `beautifulsoup4` for context grounding.
- **CRITICAL FOUNDER GROUNDING**: System prompt grounds copy in founder's authentic mechatronics engineering background:
  - *Final Year Mechatronics Student at UET Faisalabad*
  - *SolidWorks DFM* (CNC machining, injection molding, sheet metal cost reduction)
  - *ROS 2 & Gazebo Simulation* (URDF modeling, Nav2 autonomous navigation)
  - *TinyML & INT8 Quantization* (TFLite Micro on ESP32 & STM32 MCUs)
  - *Cascade Pneumatics* (Multi-cylinder electropneumatic sequence control)
- Generates a **maximum 65-word** peer-to-peer cold pitch with zero fluff. Updates row (`status: 'drafted'`).

### 5. PR Guardian Agent (`src/agents/pr_agent.py`)
- **The Compliance Officer**. Reads `'drafted'` rows.
- Audits copy against a spam-lexicon (*"free", "revolutionary", "synergy", "guaranteed", "no risk", "100%"*).
- Enforces strict word count constraint (< 75 words).
- Approves compliant pitches (`status: 'approved_for_dispatch'`) or kicks back non-compliant pitches (`status: 'scouted'`) with `compliance_notes`.

### 6. Triage Agent (`src/agents/triage_agent.py`)
- Connects via IMAP to inspect incoming unread email replies.
- **CRITICAL FOLDER REQUIREMENT**: Reads strictly from the IMAP folder named `B2B_Pipeline` (bypassing default `INBOX`).
- Uses Llama 3.1 to classify sentiment into `Positive`, `Negative`, `Pricing`, `Unsubscribed`, or `Out of Office`.
- Writes incoming replies to `replies` table in SQLite for the Analytics Agent.

### 🚀 Resend Email Dispatcher (`src/dispatcher.py`)
- Fetches leads from SQLite with status `approved_for_dispatch`.
- Transmits emails using `resend.Emails.send()` set from `"Riyan <eng@muhammadriyan.tech>"`.
- Applies a **60–120 second random sleep jitter** between dispatches to maintain deliverability hygiene.
- Updates SQLite row status to `dispatched`.

---

## 🗄 Database Schema (`pipeline.db`)

Initialized and managed by `database.py`:
- `leads`: ID, company_name, url, decision_maker, target_keyword, service_lane, email_body, subject, status (`scouted`, `drafted`, `approved_for_dispatch`, `dispatched`, `replied`), compliance_notes, timestamps.
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

- **Seed Historic Pipeline Data** (To test analytics & strategy CEO adaptation immediately):
  ```bash
  python main.py --seed
  ```

- **Run Single 6-Agent Pipeline Pass**:
  ```bash
  python main.py --run-once
  ```

- **Dispatch Approved Leads via Resend API**:
  ```bash
  python main.py --dispatch
  ```

- **Run Continuous Pipeline Loop**:
  ```bash
  python main.py --loop --delay 60
  ```

- **View Current Pipeline Database Status**:
  ```bash
  python main.py --status
  ```

---

## 📜 License
MIT License. Developed for Autonomous Enterprise Agentic Workflows.
