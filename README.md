# 💬 Telegram for macOS Message Exporter

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS-111111.svg)](#)
[![Telegram](https://img.shields.io/badge/Telegram-macOS-2CA5E0.svg)](https://macos.telegram.org/)
[![CI](https://github.com/soakes/telegram-message-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/soakes/telegram-message-exporter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/)
[![Ruff](https://img.shields.io/badge/lint-ruff-262626.svg)](https://docs.astral.sh/ruff/)
[![Pylint](https://img.shields.io/badge/lint-pylint-ffcd00.svg)](https://pylint.readthedocs.io/)

A professional, offline recovery and export tool for the **native Telegram for macOS app** (not the cross‑platform Telegram Desktop/Qt app). It decrypts the local `db_sqlite` using `.tempkeyEncrypted` and produces a clean, readable transcript in **HTML**, **Markdown**, or **CSV**.

## Table of Contents

- [Overview](#overview)
- [Motivation & Use Case](#motivation--use-case)
- [Key Features](#key-features)
- [What It Does](#what-it-does)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Common Workflows](#common-workflows)
- [CLI Reference](#cli-reference)
- [Example Output](#example-output)
- [Key Paths (macOS)](#key-paths-macos)
- [Safety & Privacy](#safety--privacy)
- [Limitations](#limitations)
- [FAQ](#faq)
- [Versioning](#versioning)
- [Updating](#updating)
- [Quality Checks](#quality-checks)
- [Project Structure](#project-structure)
- [Credits](#credits)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Telegram for macOS stores messages locally in an encrypted SQLite database. This tool decrypts the local database, parses Telegram’s Postbox structure, and exports a clean transcript that a non‑technical user can read.

It is designed for **offline recovery** on a Mac where the local cache still exists and has not yet synced a deletion.

Compatibility note: this targets the **native Telegram for macOS** app (macos.telegram.org / Homebrew cask `telegram`). The cross‑platform Telegram Desktop (Qt) app uses a different storage layout.

---

## Motivation & Use Case

Telegram does not provide server‑side recovery for deleted chats. In scenarios like accidental deletion, device loss, or audit requirements, the **only remaining source of truth** can be the local encrypted cache on a macOS device.

This project was created after a family conversation was removed with no way to restore it via Telegram’s servers. The local Mac still had the encrypted cache, so this tool was built to recover what remained locally and convert it into a clean, shareable export.

---

## Key Features

- 🔐 Offline decryption using Telegram’s local key format (dbKey + dbSalt)
- 🧾 Human‑readable exports with names, timestamps, and link handling
- ✨ Modern HTML transcript with date jump + back‑to‑top
- 📊 CSV export for analysis or spreadsheets
- ⏱️ Date filters for targeted ranges
- 🧭 Best‑effort peer mapping for clean names

---

## What It Does

- Decrypts `db_sqlite` using `.tempkeyEncrypted`
- Extracts messages from the Postbox store
- Outputs HTML, Markdown, or CSV transcripts
- Supports date filtering and peer‑specific exports

What it does not do:

- Restore chats back into Telegram
- Recover media that was never downloaded/cached locally
- Bypass Telegram passcode without the passcode

---

## Requirements

- macOS with Telegram for macOS data present (native app)
- Python 3.10 or higher (tested on 3.11–3.13)
- Virtual environment recommended

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you prefer a requirements file:

```bash
pip install -r requirements.txt
```

Install from GitHub (latest):

```bash
pip install -U "git+https://github.com/soakes/telegram-message-exporter.git"
```

Clone from GitHub:

```bash
git clone https://github.com/soakes/telegram-message-exporter.git
cd telegram-message-exporter
pip install -e .
```

---

## Quick Start

### 1) Decrypt the database

```bash
telegram-exporter decrypt \
  --key ~/Library/Group\ Containers/6N38VWS5BX.ru.keepcoder.Telegram/stable/.tempkeyEncrypted \
  --db  ~/Library/Group\ Containers/6N38VWS5BX.ru.keepcoder.Telegram/stable/account-*/postbox/db/db_sqlite \
  --out plaintext.db
```

If Passcode Lock is enabled:

```bash
TG_LOCAL_PASSCODE="your-passcode" \
  telegram-exporter decrypt --key <key> --db <db> --out plaintext.db
```

### 2) Find the peer ID

```bash
telegram-exporter list-peers --db plaintext.db --search "Alex"
```

### 3) Export a transcript

```bash
telegram-exporter export \
  --db plaintext.db \
  --peer-id 123456789 \
  --me-name "Me" \
  --format html \
  --out chat_export.html
```

---

## Common Workflows

Export HTML for a specific chat:

```bash
telegram-exporter export --db plaintext.db --peer-id 123456789 --format html --me-name "Me" --out chat_export.html
```

Export a date range:

```bash
telegram-exporter export \
  --db plaintext.db \
  --peer-id 123456789 \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --format html \
  --out chat_2024.html
```

Debug decryption profile selection:

```bash
telegram-exporter decrypt --key <key> --db <db> --out plaintext.db --debug
```

Export all chats (large output):

```bash
telegram-exporter export --db plaintext.db --format html --out all_chats.html
```

---

## CLI Reference

| Command | Purpose |
| --- | --- |
| `decrypt` | Decrypt `db_sqlite` to a plaintext SQLite file |
| `diagnose` | Inspect tables and sample rows |
| `list-peers` | Find peer IDs by name fragment |
| `export` | Export messages to HTML/Markdown/CSV |

Common flags:

- `--db` Path to plaintext DB
- `--key` Path to `.tempkeyEncrypted`
- `--peer-id` Peer to export
- `--format` `html`, `md`, or `csv`
- `--start-date` / `--end-date` Date filtering
- `--me-name` Label for outgoing messages
- `--debug` Extra diagnostics (decrypt)

---

## Example Output

### HTML (snippet)

```html
<header class="glass header-panel">
  <div class="brand">
    <div class="logo">💬</div>
    <div class="title-area">
      <h1>Alex Example</h1>
      <p class="subtitle">Recovery export for Telegram for macOS</p>
    </div>
  </div>
  <div class="badge glass"><span class="dot"></span><span class="text">Ready</span></div>
</header>
```

### Markdown (snippet)

```markdown
# Telegram Chat History: Alex Example

**Exported:** 2026-02-04 16:05:12
**Total Messages:** 418

## Wednesday, February 04, 2026

**14:13:09 — Me**

3h48 is good also
```

### CSV (snippet)

```csv
date,time,timestamp,direction,speaker,text,peer_id,author_id
2026-02-04,14:13:09,1770214389,out,Me,"3h48 is good also",123456789,123456789
```

---

## Key Paths (macOS)

Telegram for macOS stores its data here:

- `~/Library/Group Containers/6N38VWS5BX.ru.keepcoder.Telegram/stable/`
- `.../account-*/postbox/db/db_sqlite`
- `.../stable/.tempkeyEncrypted`

Media cache (if downloaded):

- `.../account-*/files/`

---

## Safety & Privacy

- 🔌 Keep the Mac offline during recovery to avoid sync deletions
- 🧊 Media is only recoverable if it was cached locally
- 🧪 If decryption fails, retry with `--debug` and verify key path

---

## Limitations

- 🔒 Requires the local passcode if Passcode Lock is enabled
- ☁️ Cannot restore or re‑upload chats to Telegram servers
- 🗂️ Attachments only appear if they were previously cached on the Mac
- 🧩 Some newer Telegram message types may not fully decode

---

## FAQ

**Can this restore the chat inside Telegram?**  
No. This tool exports a transcript; it does not re‑insert messages back into Telegram.

**Why do I only see some attachments?**  
Only files that were downloaded and cached locally can be recovered.

**What if I get “file is not a database”?**  
The key and DB are mismatched, or Passcode Lock is enabled without the passcode.

**Does it work with Telegram Desktop (Qt) or mobile backups?**  
No. This targets the native Telegram for macOS app and its local storage layout.

---

## Versioning

The canonical version is stored in `VERSION` and exposed via:

```bash
telegram-exporter --version
```

Version bump helper:

```bash
./scripts/bump_version.py patch
./scripts/bump_version.py minor
./scripts/bump_version.py major
./scripts/bump_version.py --set 1.2.3
```

---

## Updating

If installed from GitHub:

```bash
pip install -U "git+https://github.com/soakes/telegram-message-exporter.git"
```

If installed from a local clone:

```bash
git pull
pip install -e .
```

---

## Quality Checks

```bash
black src/telegram_message_exporter telegram_exporter.py scripts/bump_version.py
ruff check src/telegram_message_exporter telegram_exporter.py scripts/bump_version.py
pylint src/telegram_message_exporter telegram_exporter.py
```

---

## Project Structure

```
telegram-message-exporter/
├── pyproject.toml                     # Packaging metadata + CLI entrypoint
├── telegram_exporter.py               # Convenience wrapper (no install)
├── scripts/
│   └── bump_version.py                # Version helper
├── src/
│   └── telegram_message_exporter/
│       ├── __init__.py                # Package entrypoint
│       ├── __main__.py                # python -m entrypoint
│       ├── cli.py                     # Argument parsing + commands
│       ├── crypto.py                  # SQLCipher + tempkey handling
│       ├── db.py                      # DB heuristics + message extraction
│       ├── exporters.py               # HTML / Markdown / CSV
│       ├── postbox.py                 # Postbox parsing utilities
│       ├── models.py                  # Message data model
│       ├── utils.py                   # Date + link helpers
│       └── hashing.py                 # Murmur3 helper
├── requirements.txt                   # Python dependencies
└── README.md
```

---

## Credits

This project builds on community reverse‑engineering work. Special thanks to **[@stek29](https://github.com/stek29)** for the original research and [reference implementation](https://gist.github.com/stek29/8a7ac0e673818917525ec4031d77a713) of Telegram for macOS local key format and Postbox structure. This tool extends those ideas into a polished, end‑user‑friendly CLI and export workflow.

---

## Contributing

For enhancements or alternate export styles, feel free to open a PR (or fork and submit one). We’ll review and merge solid improvements—this repo is meant to be a good base to build on.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
