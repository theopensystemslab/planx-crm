import requests
import config
from datetime import datetime, timezone


# ───────────────────────── GraphQL Client ─────────────────────────
def gql_request(query, variables=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(
        config.GRAPHQL_URL,
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_external_snapshot():
    """
    Returns dict keyed by team_id (slug), for WHITELIST_TEAMS only:
      team_id -> { "display_name": str, "description": str, "service_count": int }
    """
    print(f"--- Fetching GraphQL from {config.GRAPHQL_URL} ---")
    d = gql_request(config.GQL_QUERY)
    out = {}
    for t in d.get("teams", []):
        slug = (t.get("id") or "").strip()
        if slug not in config.ALLOWLIST_TEAMS:
            continue
        display_name = (t.get("displayName") or slug).strip()
        nodes = t.get("services", {}).get("service", []) or []
        names = [(s.get("name") or "").strip() for s in nodes if s.get("name")]
        out[slug] = {
            "display_name": display_name,
            "description": "\n".join(names) if names else "",
            "service_count": len(names),
        }
    print(f"• External snapshot teams: {len(out)}")
    return out


# ───────────────────────── Notion Helpers ───────────────────────
def paginate_db(notion_client, database_id, **kwargs):
    cursor = None
    while True:
        resp = notion_client.databases.query(
            database_id=database_id,
            start_cursor=cursor,
            page_size=config.PAGE_SIZE,
            **kwargs,
        )
        for r in resp["results"]:
            yield r
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def title_val(prop):
    return prop.get("title", [])[0]["plain_text"] if prop.get("title") else ""


def text_val(prop):
    return prop.get("rich_text", [])[0]["plain_text"] if prop.get("rich_text") else None


def number_val(prop):
    return prop.get("number") if isinstance(prop, dict) else None


def relation_ids(prop):
    return (
        [x["id"] for x in (prop.get("relation") or [])]
        if isinstance(prop, dict)
        else []
    )


def set_relation(notion_client, page_id, prop_name, ids):
    notion_client.pages.update(
        page_id=page_id, properties={prop_name: {"relation": [{"id": i} for i in ids]}}
    )


def update_props(notion_client, page_id, props):
    notion_client.pages.update(page_id=page_id, properties=props)


def create_service_page(
    notion_client,
    ext_customer_id,
    name,
    description,
    service_count,
    customer_page_id=None,
):
    props = {
        config.PROP_SERVICE_NAME: {"title": [{"text": {"content": name}}]},
        config.PROP_SERVICE_DESC: {"rich_text": [{"text": {"content": description}}]},
        config.PROP_SERVICE_EXT_ID: {
            "rich_text": [{"text": {"content": ext_customer_id}}]
        },
        config.PROP_SERVICE_COUNT: {"number": service_count},
    }
    if customer_page_id:
        props[config.PROP_SERVICE_CUSTOMER_REL] = {
            "relation": [{"id": customer_page_id}]
        }
    return notion_client.pages.create(
        parent={"database_id": config.SERVICES_DB_ID}, properties=props
    )


def update_customer_last_updated(notion_client, customer_page_id):
    notion_client.pages.update(
        page_id=customer_page_id,
        properties={
            config.PROP_CUSTOMER_LAST_UPDATED: {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            }
        },
    )


def archive_page(notion_client, page_id):
    notion_client.pages.update(page_id=page_id, archived=True)
