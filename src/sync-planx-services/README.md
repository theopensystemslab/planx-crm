# 🧩 PlanX → Notion Live Sync Script

## Purpose
This script keeps **Notion** in sync with the **PlanX live services** data from the public **GraphQL API**.  
It ensures every **Council** record in Notion always reflects its current live services via the **PlanX Live Services** database.

---

## ⚙️ How It Works

### 1. Fetch data from GraphQL
- Queries the PlanX GraphQL endpoint:  
  `https://hasura.editor.planx.uk/v1/graphql`
- Retrieves all councils (“teams”) and their currently online services.
- Filters results using an **allowlist** of council slugs (`ALLOWLIST_TEAMS`).
- Builds a snapshot per council:
  - **Name** (display name or slug)
  - **Description** (multiline service names)
  - **Service Count** (number of services)
  - **ExternalCustomerID** (team slug)

### 2. Update Notion
#### 🗂 PlanX Live Services database
- One page per council (team)
- Automatically **creates**, **updates**, or **archives** entries
- Populates or maintains:
  - `Name` — display name or slug  
  - `Description` — newline list of live services  
  - `Service Count` — total services  
  - `ExternalCustomerID` — team slug  

#### 🏛 Councils database
- Matches councils by `ExternalCustomerID` only (exact slug match)
- Links each service snapshot → council
- Updates `Integration Last Updated` (Date) for any council that changed

---

## 🧠 Design Principles

| Principle | Description |
|------------|-------------|
| **ID-based linking** | Uses `ExternalCustomerID` as the single source of truth (no name matching). |
| **Idempotent** | Safe to re-run — only changes are updated. |
| **One snapshot per council** | Keeps current state, not a history log. |
| **API-safe** | Uses rate limiting and pagination to respect Notion API limits. |
| **Readable structure** | Logic is modular — GraphQL fetch, Notion helpers, sync core. |

---

## 🧩 Notion Schema Requirements

### Councils (Database 1)
| Property | Type | Purpose |
|-----------|------|----------|
| **Name** | Title | Council name |
| **ExternalCustomerID** | Rich text | Must match the PlanX team slug |
| **Integration Last Updated** | Date | Updated whenever data changes |
| **PlanX Live Services** | Relation | Links to PlanX Live Services DB |

### PlanX Live Services (Database 2)
| Property | Type | Purpose |
|-----------|------|----------|
| **Name** | Title | Display name or slug |
| **Description** | Rich text | List of live services |
| **Service Count** | Number | Total number of services |
| **ExternalCustomerID** | Rich text | Team slug |
| **Councils** | Relation | Linked back to Councils DB |

---

## 🔧 Configuration
These values are maintained in `config.py` or via repository secrets

| Variable | Description |
|-----------|-------------|
| `NOTION_TOKEN` | Integration secret (entered at runtime via GHA secrets) |
| `COUNCILS_DB_ID` | Notion database ID for Councils |
| `SERVICES_DB_ID` | Notion database ID for PlanX Live Services |
| `ALLOWLIST_TEAMS` | List of council slugs to sync |
| `ARCHIVE_MISSING_SERVICE_PAGES` | If true, archives missing pages |
| `GENTLE_DELAY_SECONDS` | Delay between Notion API writes |

---

## 🛠 Maintenance Notes

- **Property names** must match exactly — Notion’s API is name-sensitive.  
- **Use single-source databases only** — merged/multi-source DBs are not supported by the Notion API.  
- **Update the whitelist** as new councils are onboarded.  
- **Safe re-runs:** the sync is idempotent — no duplicates or overwrites.  
- Add logging or a “dry-run” mode for visibility in production environments.

### Recommended future improvements
- Retry / exponential backoff for transient Notion API errors  
- “Last Seen” or “Active” status field instead of archiving  
- Export sync summary as a CSV for audit  
- Basic dashboard or log for monitoring sync runs

---

## 🧾 Runbook

1. **First Run**
   - Populates *PlanX Live Services* with one entry per council.  
   - Does not link to Councils yet.

2. **Manual Step**
   - In *Councils*, set each `ExternalCustomerID` to the correct team slug (e.g., `barnet`, `southwark`).

3. **Re-run Script**
   - Establishes links and updates `Integration Last Updated` for any council that changed.

---

## 📈 Expected Outcome

| Database | Result |
|-----------|---------|
| **PlanX Live Services** | Always up-to-date with each council’s live services. |
| **Councils** | Accurately linked and timestamped to show last sync time. |

---
