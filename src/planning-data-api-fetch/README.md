# Planning Data API Fetch -> Notion Sync

## Purpose
This script checks whether each council has records in specific Planning Data datasets.
It uses each council's **PD Entity** to query five datasets and updates checkbox fields
in the Notion **Councils** database.

---

## Datasets & Notion Fields
| Dataset | Notion checkbox |
|---------|-----------------|
| article-4-direction | PD-A4 |
| conservation-area | PD-CNSV |
| listed-building-outline | PD-LBO |
| tree | PD-TREE |
| tree-preservation-zone | PD-TPZ |

---

## How It Works
1. Loads all pages in the Councils DB.
2. For each page with **Reference Code** and **PD Entity**:
   - Calls Planning Data API with `limit=1` for each dataset.
   - Uses `count > 0` to set the checkbox to `true`.
3. Writes checkbox updates only when values change.

---

## Notion Schema Requirements
| Property | Type | Purpose |
|----------|------|---------|
| **Reference Code** | Title or Rich text | Identifies a council |
| **PD Entity** | Rich text | Organisation entity ID |
| **PD-A4** | Checkbox | Dataset presence |
| **PD-CNSV** | Checkbox | Dataset presence |
| **PD-LBO** | Checkbox | Dataset presence |
| **PD-TREE** | Checkbox | Dataset presence |
| **PD-TPZ** | Checkbox | Dataset presence |

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
uv run src/planning-data-api-fetch/main.py
```

---

## Runbook
1. Ensure all councils have **Reference Code** and **PD Entity** values.
2. Run with `dry_run=True` to inspect changes.
3. Set `dry_run=False` and run again to write updates.

---

## Design Principles
- **Idempotent**: re-running produces the same result
- **Safe by default**: dry-run + diffing enabled
- **Explicit mapping**: no implicit inference
- **CI-friendly**: no local state required

---

## Maintainers
Open Systems Lab - PlanX team
