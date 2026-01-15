# PlanX Dataset Status -> Notion Sync

## Purpose
This script syncs **dataset status** per council from the Planning Data Platform
(via Datasette) into a **Notion CRM** database.

---

## How It Works

### 1. Fetch data from Datasette
- Queries the Planning Data Datasette endpoint for issue summaries
- Filters to the dataset list defined in `config.py`

### 2. Compute dataset statuses
For each council and dataset:
- **Live** if any active rows exist and none have problem severities
- **Needs Improving** if any active row has a problem severity
- **Expired** if rows exist but none are active
- **Not Submitted** if the council has no rows for that dataset

### 3. Update Notion
- Maps each dataset status to a select property in Notion
- Only writes changes (idempotent updates)
- Supports `dry_run` in `config.py` for safe testing

---

## Notion Schema Requirements

### Councils database
| Property | Type | Purpose |
|----------|------|---------|
| **Reference Code** | Title or Rich text | Matches councils to Datasette organisations |

### Dataset select properties
These select properties must exist with exact names and options:

| Dataset slug | Notion property |
|-------------|-----------------|
| article-4-direction-area | Dataset - Article 4 Direction Area |
| conservation-area | Dataset - Conservation Area |
| listed-building-outline | Dataset - Listed Building Outline |
| tree-preservation-zone | Dataset - TPZ |
| tree | Dataset - Trees |

Select options required for each:
- `Live`
- `Needs Improving`
- `Expired`
- `Not Submitted`

---

## Configuration
Values are defined in `config.py` or via environment variables.

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Notion integration token (required at runtime) |
| `notion_database_id` | Target Notion database ID (in `config.py`) |
| `dataset_to_notion_prop` | Dataset -> Notion property mapping |
| `dry_run` | If true, prints updates without writing |

---

## Run
From repo root:

```bash
uv run src/planning-data-status/main.py
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
| **Councils DB** | Dataset status selects stay current per council. |

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
