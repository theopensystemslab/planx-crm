# Planning Data Entity -> Notion Sync

## Purpose
This script syncs **Planning Data entity IDs** into the **Councils** Notion database.
It matches Planning Data `reference` codes to the Notion **Reference Code** property,
then writes the `entity` value to **PD Entity**.

---

## How It Works

### 1. Fetch Planning Data entities
- Calls the Planning Data API for `dataset=local-authority`
- Retrieves `reference`, `entity`, and `name`

### 2. Update Notion
- Finds a Notion page by **Reference Code**
- Writes `entity` into the **PD Entity** text field
- Only writes changes (idempotent updates)
- Supports `dry_run` in `config.py` for safe testing

---

## Notion Schema Requirements

### Councils database
| Property | Type | Purpose |
|----------|------|---------|
| **Reference Code** | Title or Rich text | Matches councils to Planning Data `reference` |
| **PD Entity** | Rich text | Stores Planning Data `entity` ID |

---

## Configuration
Values are defined in `config.py` or via environment variables.

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Notion integration token (required at runtime) |
| `notion_database_id` | Target Notion database ID (in `config.py`) |
| `dry_run` | If true, prints updates without writing |

---

## Run
From repo root:

```bash
uv run src/planning-data-entity-sync/main.py
```

---

## Runbook
1. Ensure all councils have a **Reference Code** in Notion.
2. Run with `dry_run=True` to inspect changes.
3. Set `dry_run=False` and run again to write updates.

---

## Expected Outcome
| Database | Result |
|----------|--------|
| **Councils DB** | **PD Entity** stays current per council. |

---

## GitHub Actions
The workflow reads the Notion token from repo or org secrets:

```
NOTION_TOKEN
```

---

## Design Principles
- **Idempotent**: re-running produces the same result
- **Safe by default**: dry-run + diffing enabled
- **Explicit mapping**: no implicit inference
- **CI-friendly**: no local state required

---

## Maintainers
Open Systems Lab - PlanX team
