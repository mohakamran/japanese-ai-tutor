<div align="center">

<img src="docs/banner.svg" alt="Japanese AI Tutor — learn Japanese with an AI tutor that explains why" width="100%">

<br>

**An AI-powered Japanese tutor for English speakers, from your first ひらがな to natural, fluent conversation.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.66-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Responses%20API-412991?logo=openai&logoColor=white)](https://platform.openai.com/docs)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-208%20passing-2F7A55)](#-testing)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)

[Features](#-features) · [Screenshots](#-screenshots) · [Quick start](#-quick-start) · [Architecture](#-architecture) · [Security](#-security--privacy) · [Testing](#-testing) · [Deployment](#-deployment)

</div>

---

## ✨ Overview

**Japanese AI Tutor** is a complete, multi-user web application that uses a large language model to teach Japanese. Learners create an account, connect their own OpenAI API key, and get:

- **Vocabulary lists** for any topic, with flashcard review.
- **Grammar explanations** in plain English.
- **Quizzes**, scored by the app's own code rather than by the model.
- **Feedback on Japanese they write themselves.**
- **Role-play conversations** with an AI partner.

Their streak, scores and activity are stored and charted.

It is built as an AI-engineering project, so the AI layer is held to production-style standards:

- **Structured outputs everywhere.** Every model response is a Pydantic schema, validated before it is shown or saved.
- **Deterministic logic stays in code.** Quiz scoring, answer-key hiding and duplicate protection never depend on the model.
- **Defense in depth.** Prompt-injection delimiters, HTML escaping of every AI string, parameterized SQL, encrypted API keys, scrypt password hashes, and log redaction.
- **208 automated tests** with a fully mocked AI layer, plus headless browser-level UI tests.

> ⚠️ All learning content is AI-generated and labelled as such. It is usually helpful but **can contain mistakes**, so verify important points with a teacher, textbook or dictionary.

---

## 🎯 Features

| | Feature | What you get |
|---|---|---|
| 🔐 | **Accounts** | Sign up, log in, "keep me signed in", update your profile, change your password (this signs out your other devices), and permanently delete your account and all its data. |
| 🔑 | **Bring your own AI** | Paste your OpenAI API key in **Settings → AI setup**. It is verified with OpenAI, then **encrypted** before storage. Pick a model from the list of models **your key can actually use**, and run a one-click test request. |
| 🏠 | **Dashboard** | A time-of-day greeting in Japanese, study streak, word of the day, average-score ring, recommended next step, activity timeline, and quick-start tiles. |
| 語 | **Vocabulary** | 3–15 words for any topic, each with kanji, kana reading, romaji, meaning, part of speech, an example sentence and a usage note. Save words, search and filter your list, and review with **flashcards** that show your hardest words first. |
| 文 | **Grammar Tutor** | Ask anything in English. The answer comes back as a lesson: the pattern, how to form it, an explanation, examples labelled formal or casual, common mistakes and related patterns. Follow-up questions keep context, lessons can be saved, and one click turns a lesson into a quiz. |
| 試 | **Quiz Center** | Seven question types plus a mixed mode, each with topic, level, difficulty and length controls. Answer keys stay hidden until you submit, and scoring is done in Python. You get per-question feedback, an AI "explain my mistake" option, and a review of mistakes from past quizzes. A local quiz built from your saved words needs no AI. |
| 直 | **Sentence Correction** | Rates your sentence as *correct*, *could be more natural*, *needs correction* or *ambiguous*. Grammar and word-choice issues are listed by severity, with a more natural alternative, any assumptions stated, and a learning tip. A sentence is never marked wrong just for being unusual. |
| 話 | **Conversation Practice** | Eleven role-play scenarios (restaurant, convenience store, train station, doctor and more). Optional corrections, romaji toggle, vocabulary notes, suggested replies, and a word-by-word breakdown of any sentence. |
| 進 | **Learning Progress** | Statistic tiles, a quiz-score trend, 30-day activity, saved words by topic, quiz history and a timeline. Every value is computed from your stored records, never estimated. |
| ⚙️ | **Settings** | Level, romaji, explanation style, quiz difficulty and correction preferences; AI setup; account management; and deletion of your data by category. |

---

## 📸 Screenshots

> Captured from the running app with real `gpt-5.4-mini` responses and a fictional demo account. Click any image to view it full size.

<table>
  <tr>
    <td width="50%"><b>Landing &amp; login</b><br><img src="docs/screenshots/01_landing.png" alt="Landing page with log-in form"></td>
    <td width="50%"><b>Dashboard</b><br><img src="docs/screenshots/02_dashboard.png" alt="Dashboard with streak, word of the day and activity"></td>
  </tr>
  <tr>
    <td><b>Vocabulary generation</b><br><img src="docs/screenshots/03_vocabulary.png" alt="Generated vocabulary cards"></td>
    <td><b>Grammar lesson</b><br><img src="docs/screenshots/04_grammar.png" alt="Grammar lesson with common mistakes"></td>
  </tr>
  <tr>
    <td><b>Quiz in progress</b> (answer key hidden)<br><img src="docs/screenshots/05_quiz_question.png" alt="Quiz question"></td>
    <td><b>Quiz results</b> (scored in Python)<br><img src="docs/screenshots/06_quiz_results.png" alt="Quiz results with correct and incorrect answers"></td>
  </tr>
  <tr>
    <td><b>Sentence correction</b><br><img src="docs/screenshots/07_correction.png" alt="Sentence correction feedback"></td>
    <td><b>Conversation practice</b><br><img src="docs/screenshots/08_conversation.png" alt="Restaurant role-play conversation"></td>
  </tr>
  <tr>
    <td><b>Flashcard review</b><br><img src="docs/screenshots/09_flashcard.png" alt="Flashcard review"></td>
    <td><b>Learning progress</b><br><img src="docs/screenshots/10_progress.png" alt="Progress charts"></td>
  </tr>
  <tr>
    <td><b>AI setup</b> (key never displayed)<br><img src="docs/screenshots/11_settings_ai.png" alt="AI setup settings"></td>
    <td><b>Account management</b><br><img src="docs/screenshots/12_settings_account.png" alt="Account settings"></td>
  </tr>
</table>

<p align="center"><b>Mobile</b> (the log-in card moves to the top on phones)<br><img src="docs/screenshots/13_mobile_landing.png" alt="Mobile landing page" width="300"></p>

---

## 🚀 Quick start

### 1. Prerequisites

| You need | Notes |
|---|---|
| **Python 3.11 or newer** | Tested on 3.12. Check with `python3 --version`. On macOS: `brew install python@3.12`. On Windows: [python.org](https://www.python.org/downloads/) (tick *Add Python to PATH*). |
| **An OpenAI API key** | From [platform.openai.com → API keys](https://platform.openai.com/api-keys), with billing enabled. **A ChatGPT subscription does not include API access.** |
| **Git** (optional) | Only needed to clone; you can also download a ZIP. |

### 2. Download the project

**Option A: clone with Git**

```bash
git clone https://github.com/mohakamran/japanese-ai-tutor.git
cd japanese-ai-tutor
```

**Option B: download a ZIP**

On the GitHub page, click **Code → Download ZIP**, unzip it, and open a terminal in the unzipped folder.

### 3. Install

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv                 # use python3.12 explicitly if python3 is older than 3.11
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1            # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```
</details>

### 4. Run

```bash
streamlit run app.py
```

Open **http://localhost:8501**.

### 5. Connect the AI

1. Click **Create account** and sign up. Accounts are stored locally in SQLite.
2. Open **Settings → AI setup**, paste your OpenAI API key, and click **Verify & save key**.
3. Click **Load available models**, choose one, then **Save model** and **Test model**.

That's it. Generate your first vocabulary list on the **Vocabulary** page. 🎉

> 💡 **Server-wide key (optional).** Instead of pasting a key in the UI, you can put `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`. Every signed-in user then uses them unless they save their own. Set `SHARE_SERVER_API_KEY=false` to turn that off.

---

## 🧭 Using the app

<details>
<summary><b>Vocabulary &amp; flashcards</b></summary>

- **Generate words:** choose a topic or type your own (≤ 60 characters), pick a level and count (3–15), then press **Generate Vocabulary**. Save single cards or **Save all**; duplicates are ignored.
- **My vocabulary:** search, filter by topic, remove words, or start **Quiz me on my saved words**. This quiz is built locally with no AI and needs at least 4 words.
- **Flashcard review:** recall the meaning, press **Reveal answer**, then mark **I knew it** or **Still learning**. Words you find hardest come back first.
</details>

<details>
<summary><b>Grammar Tutor</b></summary>

Ask a question such as *"What is the difference between は and が?"* and you get a structured lesson. Follow-ups remember your last 3 questions; **Start a new topic** resets that. **Save this lesson** keeps it under *Saved lessons*, and **Generate Practice Quiz** creates a 5-question grammar quiz.
</details>

<details>
<summary><b>Quiz Center</b></summary>

Pick a topic, type, level, difficulty and length, then **Generate Quiz**. Questions that fail the quality checks are discarded, and the app tells you how many were kept. Answer with **Previous / Next** or the numbered buttons; unanswered questions are marked with ·. **Submit quiz** scores it once; repeated clicks never create duplicates. Afterwards, filter to the questions you missed, ask **Explain my mistake**, and see older errors under **Review mistakes from past quizzes**.
</details>

<details>
<summary><b>Sentence Correction</b></summary>

Write a Japanese sentence (≤ 300 characters). Optionally add what you meant and who you're talking to, since context changes what counts as natural. The activity log records only "Checked a Japanese sentence", never the sentence itself.
</details>

<details>
<summary><b>Conversation Practice</b></summary>

Choose a scenario, press **Start conversation**, and reply in Japanese (≤ 500 characters). Expand **English &amp; notes** for the translation, vocabulary and a suggested reply, or use **Explain this sentence** for a word-by-word breakdown. Conversations are kept for the browser session only.
</details>

<details>
<summary><b>Account &amp; data</b></summary>

**Settings → Account** lets you rename yourself, change your email (requires your password), change your password (signs out your other devices), or **delete your account**. Deleting requires your password and typing `DELETE`, and removes every record linked to you. **Settings → Your data** clears one category at a time while keeping your account.
</details>

---

## 🏗 Architecture

```mermaid
flowchart TD
    U[English-Speaking Learner]
    UI[Streamlit User Interface]
    AUTH[Accounts & Sessions]
    APP[Application and Business Logic]
    PROMPTS[Prompt Templates]
    AI[AI Service]
    LLM[OpenAI API and Language Model]
    VALID[Response Validation with Pydantic]
    DB[Database Access Layer]
    SQLITE[(SQLite Database)]
    TESTS[Automated Tests]

    U <--> UI
    UI <--> AUTH
    UI <--> APP
    AUTH <--> DB
    APP --> PROMPTS
    APP --> AI
    PROMPTS --> AI
    AI <--> LLM
    AI --> VALID
    VALID --> APP
    APP <--> DB
    DB <--> SQLITE
    TESTS -. Tests .-> APP
    TESTS -. Tests .-> AI
    TESTS -. Tests .-> DB
    TESTS -. Tests .-> UI
```

| Layer | Location | Responsibility |
|---|---|---|
| **Presentation** | `app.py`, `ui/` | Pages, theme and components. It never calls OpenAI or writes SQL directly. Every dynamic string inserted into HTML goes through `ui/components.esc()`. |
| **Accounts & sessions** | `features/accounts.py`, `ui/session.py`, `core/security.py` | Sign-up, login with lockout, "remember me" sessions, profile and password changes, account deletion, encrypted API keys, and choosing which key and model each user's AI requests use. |
| **Business logic** | `features/` | Validates input, builds prompts, calls the AI, checks results (drops invalid quiz questions, shuffles options), scores quizzes, and persists data. It has **no Streamlit imports**, so it is unit-testable and reusable. |
| **Prompt templates** | `prompts/` | A shared tutor persona, per-level guidance, security rules, and one task template per feature. |
| **AI service** | `services/llm_service.py` | The only module that talks to OpenAI. It uses `responses.parse` with Pydantic schemas, retries invalid or truncated output once, maps errors to friendly messages, and lists and tests models. |
| **Validation** | `schemas/` | Pydantic models for every AI response, with local validators (non-empty strings, consistent verdicts, required examples). |
| **Persistence** | `database/` | Transactional connections, forward-only migrations, row dataclasses, and two repositories: `AccountRepository` and a **user-scoped** `LearningRepository` in which every query filters by `user_id`. |
| **Config & security** | `config/`, `core/` | Settings validation, log redaction, input validation, the error hierarchy, password hashing and encryption. |

### Request lifecycle: generating a quiz

1. The learner submits the form. Widget values persist, so a failed request never loses their input.
2. `features/quiz.generate_quiz()` validates the topic, level, count, type and difficulty against allow-lists.
3. `prompts/quiz.build_quiz_prompt()` wraps the topic in `<learner_input>` delimiters and adds the tutor rules.
4. `LLMService.generate_structured()` calls `client.responses.parse(text_format=QuizGenerationResponse, store=False)` with the user's own key and model.
5. Pydantic validates the JSON. Invalid or truncated output gets **one** retry, with a larger token budget if the output was cut off.
6. `validate_generated_questions()` drops questions with duplicate options, an out-of-range answer index or the wrong type. `shuffle_options()` randomizes where the correct answer sits.
7. A `QuizSession` is stored in session state. The page renders only `public_questions()`, which contain **no answer index and no explanation**.
8. On submit, `calculate_quiz_score()` scores the quiz in Python. The attempt and every response are saved in one transaction. A `UNIQUE` quiz id, together with the session keeping its score, prevents double-scoring.

### Project structure

```text
japanese-ai-tutor/
├── app.py                    # Entry point: theme, login routing, navigation, sidebar
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # + pytest, ruff
├── pyproject.toml            # pytest + ruff configuration
├── .env.example              # Configuration template (no secrets)
├── .streamlit/
│   ├── config.toml           # Theme (washi paper, vermilion, indigo), hidden error details
│   └── secrets.toml.example
├── assets/                   # Logo and icon (SVG)
├── config/                   # settings.py (validated config), logging_config.py (redaction)
├── core/                     # constants, errors, validation, security (scrypt, Fernet)
├── services/llm_service.py   # OpenAI integration, model listing and testing
├── prompts/                  # base persona + vocabulary, grammar, quiz, correction, conversation
├── schemas/                  # Pydantic response models
├── features/                 # accounts, vocabulary, grammar, quiz, correction, conversation, progress
├── database/                 # connection, migrations, models, repositories
├── ui/                       # auth page, 8 app pages, components, styles, session, services
├── tests/                    # 209 tests (unit, security, accounts, mocked AI, UI)
├── docs/                     # banner and screenshots
└── data/                     # SQLite database + generated encryption key (git-ignored)
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env`. Every setting is optional; the app runs without any of them. Real environment variables take precedence over `.env`, which takes precedence over Streamlit secrets.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Server-wide key used by learners who haven't saved their own. |
| `OPENAI_MODEL` | — | Default model, used when a learner hasn't picked one. |
| `SHARE_SERVER_API_KEY` | `true` | Whether signed-in users may use the server key. **Set `false` for public deployments.** |
| `OPENAI_REASONING_EFFORT` | — | For reasoning models: `low`, `medium` or `high`. Lower is cheaper and faster. |
| `OPENAI_TIMEOUT_SECONDS` | `60` | Per-request timeout (5–600). |
| `OPENAI_MAX_RETRIES` | `2` | SDK retries for rate limits, timeouts and 5xx errors (0–5). |
| `APP_SECRET_KEY` | auto | Fernet key that encrypts saved API keys. If unset, one is generated into `data/.app_secret_key` (mode 600). **Back it up**, because losing it makes saved keys unreadable. |
| `SESSION_DAYS` | `14` | How long "keep me signed in" lasts (0 disables it). |
| `ALLOW_SIGNUPS` | `true` | Set `false` to close registration. |
| `APP_PASSWORD` | — | Optional site-wide password shown before the login page. |
| `DATABASE_PATH` | `./data/japanese_tutor.db` | SQLite file location. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |

Generate an `APP_SECRET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Choosing a model.** Use **Settings → AI setup → Load available models**. The list comes from your own OpenAI account, filtered to text-generation models and shown newest first. Pick one that supports **structured outputs**; **Test model** confirms it works. For reasoning models, `OPENAI_REASONING_EFFORT=low` keeps costs down.

**If a key leaks:** revoke it on the OpenAI platform, create a new one, and save it again in Settings (or `.env`). Removing a committed key from Git does not make it safe; rotating it does.

---

## 🤖 AI integration

- **API:** the official `openai` Python SDK (v3) and the **Responses API**, called as `client.responses.parse(model, instructions, input, text_format=<PydanticModel>, max_output_tokens, store=False)`.
- **Per-user credentials:** the user's own key and model win; the server's key and model are fallbacks (`features/accounts.resolve_ai_config`). Each session builds its own client, so clients are never shared between users.
- **Structured outputs:** every feature has a schema in `schemas/`. Local validators add rules that are not in the JSON schema, so the API never receives unsupported keywords.
- **Schema-valid does not mean linguistically correct.** The app adds its own checks where it can and labels all AI content.
- **Errors map to clear messages** and are never shown raw:

  | Situation | Learner sees | Retried? |
  |---|---|---|
  | No key or model | Link to AI setup | — |
  | 401 / 403 | "The OpenAI API rejected the configured API key…" | No |
  | 404 model | "The configured model was not found…" | No |
  | 400 / 422 | "The model may not support structured outputs…" | No |
  | 429 rate limit | "Too many requests… wait a moment" | By the SDK |
  | 429 `insufficient_quota` | "No remaining API quota… check billing" | No |
  | Timeout / network / 5xx | "Could not reach the AI service…" | By the SDK |
  | Invalid, empty or truncated JSON | "The AI returned a response that could not be used…" | Once by the app |
  | Refusal or content filter | "The AI declined to answer this request…" | No |

- **Cost controls:**
  - Token caps per feature: 3,000–8,000.
  - Bounded histories: 3 grammar turns, sent as compact summaries; 12 conversation messages.
  - AI is called only when a button is pressed, and results are reused across reruns.
  - Flashcards, the saved-vocabulary quiz and all progress features use no AI.

### Prompt engineering

`prompts/base.py` holds the shared persona. The tutor is patient and accurate, explains in English, distinguishes errors from style, and admits uncertainty. It also holds level and style guidance and the security rules. Each feature module adds a focused task template.

From `prompts/correction.py`:

```text
- Do NOT mark a sentence wrong just because it is unusual, casual, or differs from a textbook
  phrasing. Valid alternatives, dropped subjects and casual speech are not errors.
```

To change a prompt:

1. Edit the feature's `TASK` text.
2. If you change the output shape, update the matching schema **and** the page that renders it.
3. Keep `SECURITY_RULES` intact.
4. Run the tests.

---

## 🗄 Database

SQLite is created automatically and upgraded by numbered, forward-only migrations. Startup never drops data. Version 1 was the original single-user schema. Version 2 adds accounts; it rebuilds tables using SQLite's documented table-rebuild procedure, and the **first account created inherits any pre-account data**.

```mermaid
erDiagram
    users ||--o{ user_sessions : "remembered logins"
    users ||--o| user_api_credentials : "encrypted key"
    users ||--o| learner_preferences : has
    users ||--o{ vocabulary : saves
    vocabulary ||--o| saved_vocabulary : "review state"
    vocabulary ||--o{ vocabulary_reviews : "flashcard answers"
    users ||--o{ grammar_lessons : saves
    users ||--o{ quiz_attempts : takes
    quiz_attempts ||--o{ quiz_responses : contains
    users ||--o{ activity_log : records
```

| Table | Key fields |
|---|---|
| `users` | `email` (unique, case-insensitive), `display_name`, `password_hash` (scrypt), `failed_logins`, `locked_until`, `last_login_at` |
| `user_sessions` | `token_hash` (SHA-256 of the cookie token, never the token itself), `user_id`, `expires_at` |
| `user_api_credentials` | `encrypted_api_key` (Fernet), `key_hint` (`…abcd`) |
| `learner_preferences` | Level, romaji, explanation style, difficulty, corrections, `openai_model` |
| `vocabulary` / `saved_vocabulary` / `vocabulary_reviews` | Saved words (unique per user), review counts, review history |
| `grammar_lessons` | Saved, validated lesson JSON (unique per user, title, pattern and level) |
| `quiz_attempts` / `quiz_responses` | Scores (with `client_quiz_id` unique, which blocks double submission) and per-question answers |
| `activity_log` | Short descriptions for the dashboard. Your sentences and chat messages are never stored. |

Every user-owned table has `ON DELETE CASCADE` to `users`, so **deleting an account removes all of its data** (tested).

**Not stored:** conversations, sentence-correction text, unsaved generated content and raw API responses.

**Backups:** `sqlite3 data/japanese_tutor.db ".backup backup.db"`. Back up `data/.app_secret_key` too.

---

## 🔒 Security & privacy

| Area | What the app does |
|---|---|
| **Passwords** | scrypt (N=2¹⁴, r=8, p=1) with a random 16-byte salt and constant-time comparison. The policy requires 8+ characters with at least one letter and one number. |
| **Login abuse** | Error messages don't reveal whether an account exists, and login takes the same time either way. **5 failed attempts lock the account for 10 minutes.** |
| **Sessions** | Random 256-bit tokens in an `SameSite=Strict` cookie (`Secure` over HTTPS). Only SHA-256 hashes are stored. Tokens expire, are deleted on logout, and are revoked on password change. |
| **API keys** | Verified with OpenAI, encrypted with Fernet before storage, and never shown again (only `…abcd`). Raw key input is cleared from widget state after saving. |
| **Data isolation** | `LearningRepository` is bound to one `user_id`, and every query filters by it. Tests confirm one user cannot read, change or delete another's data, or hijack their quiz ids. |
| **Account deletion** | Requires the password and typing `DELETE`; cascades remove everything linked to the account. |
| **Input validation** | Length limits, allow-lists and control-character stripping on every input. The repository accepts only validated Pydantic objects. |
| **AI output** | Schema-validated, HTML-escaped on render, and never executed. The model has no tools. |
| **Prompt injection** | Learner text is wrapped in delimiters (any embedded delimiters are stripped), and the instructions treat it strictly as data. This *reduces* but cannot eliminate prompt injection; impact is limited because output is only displayed. |
| **SQL** | Fully parameterized. A test parses the database code and fails if SQL is built with f-strings, concatenation or `.format()`. |
| **Errors & logs** | `showErrorDetails = "none"`, so tracebacks never reach the browser. Logs redact `sk-…` keys, bearer tokens and configured secrets, including inside tracebacks. |
| **Provider privacy** | Requests use `store=False`. Only the current request and its bounded history are sent; database contents never are. |

**Limitations.** This is a portfolio-grade application with careful defaults, but it has **not had a professional security audit**. It has no email verification or password-reset email; a forgotten password requires an administrator. The session cookie is set from JavaScript, so it cannot be `HttpOnly`; all dynamic output is escaped to limit XSS risk. Serve public deployments over **HTTPS**.

---

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest                                 # 208 pass, 1 skipped; no API key needed, no cost
RUN_LIVE_TESTS=1 pytest -m live        # optional: one real, billed API call (uses your .env)
```

| File | Covers |
|---|---|
| `test_accounts.py` | Hashing and salting, password and email rules, sign-up and duplicates, generic login errors, **lockout**, sessions (hash-only storage, expiry, revocation), profile and password changes, **account deletion cascade**, **cross-user isolation**, v1→v2 migration, encryption at rest, key precedence, model filtering |
| `test_quiz.py` | Scoring, missing and invalid answers, determinism, dropping invalid questions, shuffling, hidden answer keys, idempotent submission, save-failure retry, saved-vocabulary quiz |
| `test_database.py` | Migrations without data loss, CRUD, de-duplication, transactions, cascades, clearing data, friendly database errors |
| `test_llm_service.py` | Mocked OpenAI client: request shape, malformed, empty and truncated output, retry limits, refusals, mapping of every error class without leaking details |
| `test_features.py` | Feature workflows with a fake AI: bounded histories, correction toggles, failed replies, input limits, recommendations |
| `test_security.py` | No secrets in `repr`, logs or source; settings validation; HTML escaping; SQL-injection strings stored literally; static parameterization check |
| `test_app.py` | Headless Streamlit: landing page, **sign-up / login / logout through the UI**, all pages render without errors or secrets, saving an API key, per-user data in the UI, hidden quiz answers, single save across reruns, friendly AI errors |
| `test_live_api.py` | Opt-in real API smoke test |

**Code quality:**

```bash
ruff check .
ruff format --check .
```

Ruff is configured with the `E F W I B UP S SIM RUF` rule sets; `S` adds Bandit-style security checks.

---

## ☁️ Deployment

### Streamlit Community Cloud

1. Fork or push this repository to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io), create an app with main file `app.py` and Python 3.11+.
3. Under **Advanced settings → Secrets**, add:
   ```toml
   APP_SECRET_KEY = "your-generated-fernet-key"
   SHARE_SERVER_API_KEY = "false"     # each user brings their own key
   # Optional server defaults:
   # OPENAI_MODEL = "your-default-model"
   ```
4. Deploy. HTTPS is automatic.

> ⚠️ **Storage is ephemeral on Community Cloud.** The SQLite file, including accounts, is wiped when the app restarts or redeploys. Use it for demos; for real users, self-host with a persistent volume or migrate to PostgreSQL (all SQL lives in `database/`).

### Self-hosting

Run `streamlit run app.py --server.address 0.0.0.0` behind a TLS reverse proxy such as Caddy or nginx. Set the variables above as environment variables, point `DATABASE_PATH` at a persistent, non-public volume, and back up the database together with `APP_SECRET_KEY`.

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| **"Connect your AI tutor" notice** | Save an API key and model in **Settings → AI setup**, or set them in `.env` and restart. |
| **"The OpenAI API rejected the configured API key"** | The key is wrong or revoked. Create a new one and save it again. Check for extra spaces. |
| **"Model was not found" / "rejected the request"** | Choose a model from **Load available models** and click **Test model**. Remove `OPENAI_REASONING_EFFORT` for non-reasoning models. |
| **"No remaining API quota"** | Add billing or credits on the OpenAI platform. ChatGPT Plus does not cover API usage. |
| **"Too many requests"** | Wait a minute, or use fewer quiz questions. |
| **"Saved API key could not be decrypted"** | `APP_SECRET_KEY` (or `data/.app_secret_key`) changed. Save your key again. |
| **"Account locked"** | Wait 10 minutes after 5 failed attempts. |
| **Forgot password** | There is no reset email yet. An administrator can delete the account row in the database, after which you can sign up again. |
| **Logged out after refresh** | Tick *Keep me signed in* when logging in, and allow cookies for the site. |
| **`streamlit: command not found`** | Activate the virtual environment first. |
| **Port in use** | `streamlit run app.py --server.port 8502` |
| **Dependency install fails** | Check `python --version` is 3.11+ inside the venv, upgrade pip, and retry. |
| **Japanese shows as boxes (□)** | The app loads Noto Sans JP from Google Fonts. Offline, install a Japanese font (Windows: add the Japanese language pack; Linux: `fonts-noto-cjk`). |
| **"Configuration problem" at startup** | A value in `.env` is invalid; the message names the variable. |

---

## 🧱 Known limitations

- **AI can be wrong.** Readings, nuance, examples and quiz distractors may contain errors, so verify important points.
- **Every quiz is multiple choice**, which keeps scoring deterministic. Typed answers are not supported.
- **No audio.** There is no text-to-speech, pronunciation practice or speech recognition.
- **Conversations and corrections are not saved.**
- **Flashcard ordering is heuristic**, not true spaced repetition.
- **No email verification or password-reset email.**

## 🔭 Roadmap (not yet implemented)

- [ ] Spaced repetition (SM-2) scheduling
- [ ] Text-to-speech and pronunciation practice
- [ ] Typed answers with fuzzy and AI-assisted grading
- [ ] JLPT study paths and mock tests
- [ ] RAG over verified Japanese learning resources
- [ ] Password reset by email, and OAuth sign-in
- [ ] PostgreSQL backend for persistent multi-user hosting
- [ ] Anki export

---

## 🤝 Contributing

1. Open an issue describing the bug (steps, expected vs. actual behaviour, OS and Python version, **no API keys**) or the learning problem a feature would solve.
2. Branch from `main` and keep the layering: UI in `ui/`, logic in `features/`, prompts in `prompts/`, schemas in `schemas/`, SQL only in `database/`.
3. Add tests (mock all AI calls), then run `ruff format . && ruff check . && pytest`.
4. Update this README if behaviour or configuration changes, and open a pull request.

## 📄 License

No license has been chosen yet, so default copyright applies and others may not reuse or redistribute the code. The owner should add a `LICENSE` file (see [choosealicense.com](https://choosealicense.com)) before distributing this as open source.

---

<div align="center">

**Built with Python, Streamlit, the OpenAI Responses API and Pydantic.**

がんばって！ — *Keep going!*

</div>
