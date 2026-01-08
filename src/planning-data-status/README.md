# PlanX CRM Sync

Scripts for syncing **PlanX service and dataset status data** into a **Notion CRM**.

This project pulls performance data from the Planning Data Platform (via Datasette),
derives a status per dataset per council, and updates corresponding select fields in
a Notion database.

It is designed to run:
- locally (for development and dry runs)
- via **GitHub Actions** (for scheduled or manual syncs)

---

## What this does

For each council recorded in Notion:

- Fetches dataset issue summaries from Datasette
- Computes a status per dataset:
  - **Live**
  - **Needs Improving**
  - **Expired**
  - **Not Submitted**
- Maps those statuses to select properties in Notion
- Updates **only properties that have changed**

If a council exists in Notion but not in Datasette, all datasets are marked
**Not Submitted**.

---

## Project structure

```
.
├── src/
│   └── sync-planx-services/
│       ├── config.py        # Configuration & constants
│       ├── api_helpers.py   # Datasette + Notion API helpers
│       └── main.py          # Status logic + orchestration
├── .github/
│   └── workflows/           # GitHub Actions workflows
├── .env.example
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## Requirements

- Python **3.9+**
- A Notion integration token
- Access to the target Notion database

Python dependencies:
- `pandas`
- `requests`
- `urllib3`

---

## Notion setup

Your Notion database must include the following.

### Required property

**Reference Code**
- Type: `title` or `rich_text`
- Used to match councils against Datasette organisations

### Dataset select properties

The following select properties must exist **with these exact names**:

| Dataset slug | Notion property |
|-------------|-----------------|
| article-4-direction-area | Dataset - Article 4 Direction Area |
| conservation-area | Dataset - Conservation Area |
| listed-building-outline | Dataset - Listed Building Outline |
| tree-preservation-zone | Dataset - TPZ |
| tree | Dataset - Trees |

Each select property must include these options:
- `Live`
- `Needs Improving`
- `Expired`
- `Not Submitted`

---

## Local development setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install pandas requests
```

> On macOS you may see a LibreSSL / urllib3 warning.  
> This is safe locally and does **not** affect CI.

### 3. Set environment variables

Create a `.env` file or export manually:

```bash
export NOTION_API_TOKEN=secret_xxx
```

See `.env.example` for reference.

---

## Running locally

From the `src/sync-planx-services` directory:

```bash
python main.py
```

By default the script runs in **dry-run mode**:
- No updates are sent to Notion
- Changes are logged to the console

Example output:

```
[DRY RUN] ref=CAMDEN Dataset - Trees → Live
```

---

## Dry run vs live mode

In `config.py`:

```python
dry_run = True
```

- `True` → log changes only
- `False` → apply updates to Notion

Always run once in dry-run mode before switching to live.

---

## GitHub Actions

This repo is intended to run in CI.

### Required secret

You must define the following **GitHub Actions secret**:

```
NOTION_API_TOKEN
```

Where it lives:
- Repository-level or organisation-level Actions secret
- Added by a repo or org **Admin**

Secrets are **not visible** to non-admin users.

---

## Common issues

### I can’t see “Settings” in GitHub
You do not have Admin permissions on the repository.  
Ask an admin to add the secret.

### `Import "pandas" could not be resolved`
VS Code is not using your virtual environment.  
Select `.venv/bin/python` as the interpreter.

### LibreSSL / urllib3 warning on macOS
Safe to ignore locally, or pin:

```bash
pip install "urllib3<2"
```

CI runs on Linux with OpenSSL and will not show this warning.

---

## Design principles

- **Idempotent**: re-running produces the same result
- **Safe by default**: dry-run + diffing enabled
- **Explicit mapping**: no implicit inference
- **CI-friendly**: no local state required

---

## License

MPL-2.0

---

## Maintainers

Open Systems Lab – PlanX team
