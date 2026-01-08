# Sync PlanX Services (Detailed) → Notion

This script pulls service-level data from a Metabase card and **upserts one row per service** into a Notion database (“Live Services – Detailed”).  
It also **reconciles each service to a Council** via **Reference Code** (read from your Councils DB) and optionally writes a **Usage Rank** per council.

---

## What it does

- Fetches Metabase JSON (via API key) for a card that returns columns like:
  - `reference_code`, `council_name`, `flow_id`, `service_name`, `usage`, `first_online_at`, `url`, …
- Loads Councils from Notion and maps: **Reference Code → Council page id**
- Loads existing services from Notion and maps: **Flow Id (title) → Service page snapshot**
- Upserts services into the **Detailed Services DB**:
  - Creates a page if Flow Id doesn’t exist
  - Updates props if values changed
  - Sets/repairs the Council relation based on **Reference Code**
- (Optional) Computes and writes **Usage Rank** (highest usage = rank 1) per council.

**Important:** The script only **writes** to the Detailed Services DB. It only **reads** from the Councils DB.

---

## Repository layout

Your folder should contain:

```
src/sync-planx-services-detailed/
  main.py
  api_helpers.py
  sync_config.py
  .env              (optional, not committed)
```

---

## Prerequisites

- Python 3.9+
- A Notion integration token with access to both databases
- Metabase API key with permission to query the card
- Your Notion DB IDs:
  - Councils DB ID (read-only)
  - Detailed Services DB ID (write target)

---

## Install (local)

From repo root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install notion-client==2.2.1 requests pandas python-dotenv
```

---

## Configuration

### Option A: Environment variables (recommended)

Set these in your shell or a `.env` file:

```bash
NOTION_TOKEN="secret_..."
METABASE_API_KEY="mb_..."
```

Database IDs are currently hardcoded in `sync_config.py` (you can move them to env later if you want).

### `.env` file (example)

Create `src/sync-planx-services-detailed/.env`:

```
NOTION_TOKEN=secret_...
METABASE_API_KEY=mb_...
```

---

## Notion schema requirements

### Councils DB (read)
- **Council Name** (Title)  ← `COUNCIL_PROP_NAME`
- **Reference Code** (Rich text) ← `COUNCIL_PROP_REF_CODE`

> If your title property is actually called `Name` (common), update `COUNCIL_PROP_NAME` in `sync_config.py`.

### Live Services – Detailed DB (write target)
- **Flow Id** (Title) ← `SVC_PROP_FLOW_ID`
- **Reference Code** (Rich text) ← `SVC_PROP_REFERENCE_CODE`
- **Council Name** (Rich text) ← `SVC_PROP_COUNCIL_NAME`
- **Service Name** (Rich text) ← `SVC_PROP_SERVICE_NAME`
- **Usage** (Number) ← `SVC_PROP_USAGE`
- **First Online** (Date) ← `SVC_PROP_FIRST_ONLINE`
- **URL** (URL) ← `SVC_PROP_URL`
- **Councils** (Relation → Councils DB) ← `SVC_PROP_COUNCIL_REL`

### Usage ranking (optional)
If you want ranking:
1. Add a **Number** property to the Detailed Services DB called **Usage Rank** (or whatever you set in config).
2. In `sync_config.py`:
   ```python
   ENABLE_USAGE_RANK = True
   SVC_PROP_USAGE_RANK = "Usage Rank"
   ```

---

## Run

From repo root:

```bash
source .venv/bin/activate
python -B src/sync-planx-services-detailed/main.py
```

`-B` avoids writing bytecode (`__pycache__`) and makes debugging import issues easier.

---

## Ordering services by rank in Notion

Notion formulas cannot sort arrays.  
To display services in rank order:
1. Sort the related services view on the Council page by **Usage Rank** ascending.
2. Rollups will then follow that ordering.

A robust pattern is:
- In the Services DB create a `Display` formula: `"{rank}. {name} ({usage})"`
- Roll that up to Councils
- `join()` the rollup in a Council formula.

---

## Troubleshooting

### “METABASE_API_KEY env var not set” / “NOTION_TOKEN env var not set”
Make sure `.env` is loaded **before** importing modules that read env vars.

In `main.py`:

```python
from dotenv import load_dotenv
load_dotenv()

import sync_config
import api_helpers as api
```

### macOS LibreSSL / urllib3 warning
You may see:

```
urllib3 v2 only supports OpenSSL 1.1.1+, currently ssl is compiled with LibreSSL 2.8.3
```

This is usually just a warning. If HTTPS requests fail, consider using a Python build linked against OpenSSL (e.g., via `pyenv`) or pin urllib3 `<2` as a workaround.

### Notion schema mismatch errors
The script validates the Detailed Services DB property types at startup.  
If you renamed a property in Notion, update the matching `SVC_PROP_*` name in `sync_config.py`.

---

## Security notes

- Do **not** commit `.env` to git.
- Treat the Metabase API key and Notion token like passwords.

---

## Ownership

Internal tooling for PlanX CRM / service visibility.
