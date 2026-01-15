# PlanX Services (Detailed) -> Notion Sync

## Purpose
This script syncs **service-level details** from a Metabase card into the
**Live Services - Detailed** Notion database. It also reconciles each service
with a council via **Reference Code** and can optionally write **Usage Rank**.

---

## How It Works

### 1. Fetch data from Metabase
- Calls a Metabase card using an API key
- Expects columns like:
  `reference_code`, `council_name`, `flow_id`, `service_name`, `usage`, `first_online_at`, `url`

### 2. Load Notion snapshots
- Reads Councils from Notion to map **Reference Code -> Council page id**
- Reads existing services to map **Flow Id -> Service page snapshot**

### 3. Upsert services in Notion
- Creates a page if Flow Id does not exist
- Updates properties only when values change
- Links each service to the correct council
- Optionally computes and writes **Usage Rank**

---

## Notion Schema Requirements

### Councils database (read)
| Property | Type | Purpose |
|----------|------|---------|
| **Council Name** | Title | Council name |
| **Reference Code** | Rich text | Matches Metabase reference code |

### Live Services - Detailed database (write)
| Property | Type | Purpose |
|----------|------|---------|
| **Flow Id** | Title | Unique flow/service id |
| **Reference Code** | Rich text | Council reference code |
| **Council Name** | Rich text | Council name |
| **Service Name** | Rich text | Service name |
| **Usage** | Number | Usage count |
| **First Online** | Date | First online date |
| **URL** | URL | Service URL |
| **Councils** | Relation | Linked back to Councils DB |

### Usage ranking (optional)
1. Add a **Number** property to the Detailed Services DB called **Usage Rank**.
2. In `sync_config.py`:
   ```python
   ENABLE_USAGE_RANK = True
   SVC_PROP_USAGE_RANK = "Usage Rank"
   ```

---

## Configuration
Values are in `sync_config.py` or environment variables.

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Notion integration token |
| `METABASE_API_KEY` | Metabase API key |
| `COUNCILS_DB_ID` | Notion Councils database ID (in `sync_config.py`) |
| `SERVICES_DB_ID` | Notion Detailed Services database ID (in `sync_config.py`) |
| `ENABLE_USAGE_RANK` | Toggle rank writing |

---

## Run
From repo root:

```bash
uv run src/sync-planx-services-detailed/main.py
```

---

## Runbook
1. Ensure all councils have the correct **Reference Code** in Notion.
2. Run once to backfill services into the Detailed Services DB.
3. Re-run after council Reference Codes are set to link relationships.

---

## Expected Outcome
| Database | Result |
|----------|--------|
| **Live Services - Detailed** | One current row per service, linked to its council. |
| **Councils** | Relations and optional usage rank are kept current. |

---

## Troubleshooting

### "METABASE_API_KEY env var not set" / "NOTION_TOKEN env var not set"
Make sure `.env` is loaded before importing modules that read env vars.

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

This is usually just a warning. If HTTPS requests fail, consider using a Python
build linked against OpenSSL or pin urllib3 `<2`.

---

## Security notes
- Do **not** commit `.env` to git.
- Treat the Metabase API key and Notion token like passwords.

---

## Maintainers
Open Systems Lab - PlanX team
