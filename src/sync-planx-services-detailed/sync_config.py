import os

# ───────────────────────── Metabase ─────────────────────────
METABASE_URL = "https://metabase.editor.planx.uk"
METABASE_API_KEY = os.environ.get("METABASE_API_KEY")
CARD_ID = 1220
TIMEOUT_SECONDS = 60

# ───────────────────────── Notion ───────────────────────────
# Read from env (recommended)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

# DB IDs (set these)
COUNCILS_DB_ID = "27c35d469ad180aaacf4d8beb0ddb20c"
SERVICES_DB_ID = "2e235d469ad18014a673cd7719bb400a"  # Live Services - Detailed (write target)

# Pagination / throttling
PAGE_SIZE = 100
GENTLE_DELAY_SECONDS = 0.15

# ───────────────────────── Councils DB props ─────────────────
COUNCIL_PROP_NAME = "Council Name"               # title
COUNCIL_PROP_REF_CODE = "Reference Code" # rich_text

# ───────────────────────── Detailed Services DB props ─────────
# Flow Id MUST be Title
SVC_PROP_FLOW_ID = "Flow Id"                 # title
SVC_PROP_REFERENCE_CODE = "Reference Code"   # rich_text
SVC_PROP_COUNCIL_NAME = "Council Name"       # rich_text (optional but handy)
SVC_PROP_SERVICE_NAME = "Service Name"       # rich_text
SVC_PROP_USAGE = "Usage"                     # number
SVC_PROP_FIRST_ONLINE = "First Online"       # date
SVC_PROP_URL = "URL"                         # url

# Relation from detailed services -> councils
SVC_PROP_COUNCIL_REL = "Councils"             # relation

# Optional ordering per council (recommended)
ENABLE_USAGE_RANK = True
SVC_PROP_USAGE_RANK = "Rank" # number