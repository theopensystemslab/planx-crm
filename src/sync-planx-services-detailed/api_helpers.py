from __future__ import annotations

import time
import requests
import pandas as pd
from notion_client import Client

import sync_config


# ───────────────────────── Notion client ─────────────────────────
def notion_client() -> Client:
    if not sync_config.NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN env var not set.")
    return Client(auth=sync_config.NOTION_TOKEN)


# ───────────────────────── Metabase ──────────────────────────────
def fetch_metabase_df() -> pd.DataFrame:
    """
    Returns a dataframe with columns:
      reference_code, council_name, team_slug, flow_id, service_name,
      service_slug, usage, first_online_at, url
    """
    if not sync_config.METABASE_API_KEY:
        raise ValueError("METABASE_API_KEY env var not set.")

    json_url = f"{sync_config.METABASE_URL.rstrip('/')}/api/card/{sync_config.CARD_ID}/query/json"
    headers = {"x-api-key": sync_config.METABASE_API_KEY, "Content-Type": "application/json"}

    r = requests.post(json_url, headers=headers, json={}, timeout=sync_config.TIMEOUT_SECONDS)
    r.raise_for_status()

    df = pd.DataFrame(r.json())

    expected = {
        "reference_code", "council_name", "team_slug", "flow_id", "service_name",
        "service_slug", "usage", "first_online_at", "url"
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Metabase response missing columns: {sorted(missing)}")

    # Normalize text fields
    for col in ["reference_code", "council_name", "team_slug", "flow_id", "service_name", "service_slug", "url"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Normalize usage
    df["usage"] = pd.to_numeric(df["usage"], errors="coerce").fillna(0).astype(int)

    return df


def add_usage_rank_per_council(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds df["usage_rank_council"] where 1 = highest usage within each reference_code.
    """
    if not sync_config.ENABLE_USAGE_RANK:
        return df

    if "reference_code" not in df.columns or "usage" not in df.columns:
        return df

    df = df.copy()
    df["usage_rank_council"] = (
        df.groupby("reference_code")["usage"]
          .rank(method="first", ascending=False)
          .astype(int)
    )
    return df


# ───────────────────────── Notion paging + prop readers ───────────
def paginate_db(notion: Client, database_id: str, **kwargs):
    cursor = None
    while True:
        resp = notion.databases.query(
            database_id=database_id,
            start_cursor=cursor,
            page_size=sync_config.PAGE_SIZE,
            **kwargs,
        )
        for r in resp["results"]:
            yield r
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def title_val(prop: dict) -> str:
    if not isinstance(prop, dict):
        return ""
    t = prop.get("title") or []
    return t[0].get("plain_text") if t else ""


def rich_text_val(prop: dict) -> str | None:
    if not isinstance(prop, dict):
        return None
    rt = prop.get("rich_text") or []
    return rt[0].get("plain_text") if rt else None


def number_val(prop: dict) -> int | float | None:
    if not isinstance(prop, dict):
        return None
    return prop.get("number")


def date_val(prop: dict) -> str | None:
    if not isinstance(prop, dict):
        return None
    d = prop.get("date")
    return d.get("start") if isinstance(d, dict) else None


def url_val(prop: dict) -> str | None:
    if not isinstance(prop, dict):
        return None
    return prop.get("url")


def relation_ids(prop: dict) -> list[str]:
    if not isinstance(prop, dict):
        return []
    rel = prop.get("relation") or []
    return [x.get("id") for x in rel if x.get("id")]


# ───────────────────────── Councils lookup (READ ONLY) ────────────
def load_councils_by_ref_code(notion: Client) -> dict[str, dict]:
    """
    Returns:
      { "CMD": {"page_id": "...", "name": "Camden"} }
    """
    if not sync_config.COUNCILS_DB_ID or sync_config.COUNCILS_DB_ID == "REPLACE_ME":
        raise ValueError("COUNCILS_DB_ID not set (needed for reference-code reconciliation).")

    by_ref: dict[str, dict] = {}
    for c in paginate_db(notion, sync_config.COUNCILS_DB_ID):
        p = c["properties"]
        ref = rich_text_val(p.get(sync_config.COUNCIL_PROP_REF_CODE, {}))
        name = title_val(p.get(sync_config.COUNCIL_PROP_NAME, {})) or ""
        if ref:
            by_ref[ref.strip()] = {"page_id": c["id"], "name": name.strip()}
    return by_ref


# ───────────────────────── Services index (WRITE target) ───────────
def load_services_by_flow_id(notion: Client) -> dict[str, dict]:
    """
    Keyed by Flow Id (Title).
    """
    if not sync_config.SERVICES_DB_ID or sync_config.SERVICES_DB_ID == "REPLACE_ME":
        raise ValueError("SERVICES_DB_ID not set.")

    idx: dict[str, dict] = {}
    for s in paginate_db(notion, sync_config.SERVICES_DB_ID):
        p = s["properties"]

        flow_id = title_val(p.get(sync_config.SVC_PROP_FLOW_ID, {}))
        if not flow_id:
            continue
        flow_id = flow_id.strip()

        cur = {
            "page_id": s["id"],
            "reference_code": rich_text_val(p.get(sync_config.SVC_PROP_REFERENCE_CODE, {})) or "",
            "council_name": rich_text_val(p.get(sync_config.SVC_PROP_COUNCIL_NAME, {})) or "",
            "service_name": rich_text_val(p.get(sync_config.SVC_PROP_SERVICE_NAME, {})) or "",
            "usage": number_val(p.get(sync_config.SVC_PROP_USAGE, {})) or 0,
            "first_online": date_val(p.get(sync_config.SVC_PROP_FIRST_ONLINE, {})) or "",
            "url": url_val(p.get(sync_config.SVC_PROP_URL, {})) or "",
            "council_rel_ids": set(relation_ids(p.get(sync_config.SVC_PROP_COUNCIL_REL, {}))),
        }

        if sync_config.ENABLE_USAGE_RANK:
            cur["usage_rank_council"] = number_val(p.get(sync_config.SVC_PROP_USAGE_RANK, {})) or 0

        idx[flow_id] = cur

    return idx


# ───────────────────────── Build props + write helpers ─────────────
def build_service_props(row: dict, council_name_final: str) -> dict:
    flow_id = str(row.get("flow_id") or "").strip()
    ref = str(row.get("reference_code") or "").strip()
    svc_name = str(row.get("service_name") or "").strip()
    usage = int(row.get("usage") or 0)
    url = str(row.get("url") or "").strip()
    first_online = row.get("first_online_at")

    props = {
        # TITLE
        sync_config.SVC_PROP_FLOW_ID: {"title": [{"text": {"content": flow_id}}]},

        # rich_text
        sync_config.SVC_PROP_REFERENCE_CODE: {"rich_text": [{"text": {"content": ref}}]},
        sync_config.SVC_PROP_SERVICE_NAME: {"rich_text": [{"text": {"content": svc_name}}]},
        sync_config.SVC_PROP_COUNCIL_NAME: {"rich_text": [{"text": {"content": str(council_name_final or "")}}]},

        # number/url/date
        sync_config.SVC_PROP_USAGE: {"number": usage},
        sync_config.SVC_PROP_URL: {"url": url},
        sync_config.SVC_PROP_FIRST_ONLINE: {"date": {"start": str(first_online)}} if first_online else {"date": None},
    }

    if sync_config.ENABLE_USAGE_RANK:
        rank = int(row.get("usage_rank_council") or 0)
        props[sync_config.SVC_PROP_USAGE_RANK] = {"number": rank}

    return props


def create_service_page(notion: Client, props: dict) -> dict:
    return notion.pages.create(parent={"database_id": sync_config.SERVICES_DB_ID}, properties=props)


def update_page(notion: Client, page_id: str, props: dict) -> dict:
    return notion.pages.update(page_id=page_id, properties=props)


def set_relation(notion: Client, page_id: str, prop_name: str, ids: list[str]) -> dict:
    return notion.pages.update(
        page_id=page_id,
        properties={prop_name: {"relation": [{"id": i} for i in ids]}},
    )


def gentle_sleep():
    time.sleep(sync_config.GENTLE_DELAY_SECONDS)


# ───────────────────────── Schema checks (fail fast) ───────────────
def assert_prop_type(db: dict, prop_name: str, expected: str):
    actual = db["properties"][prop_name]["type"]
    if actual != expected:
        raise ValueError(f"Notion schema mismatch: '{prop_name}' is '{actual}' but expected '{expected}'.")


def validate_services_db_schema(notion: Client):
    db = notion.databases.retrieve(database_id=sync_config.SERVICES_DB_ID)

    assert_prop_type(db, sync_config.SVC_PROP_FLOW_ID, "title")
    assert_prop_type(db, sync_config.SVC_PROP_REFERENCE_CODE, "rich_text")
    assert_prop_type(db, sync_config.SVC_PROP_SERVICE_NAME, "rich_text")
    assert_prop_type(db, sync_config.SVC_PROP_USAGE, "number")
    assert_prop_type(db, sync_config.SVC_PROP_FIRST_ONLINE, "date")
    assert_prop_type(db, sync_config.SVC_PROP_URL, "url")
    assert_prop_type(db, sync_config.SVC_PROP_COUNCIL_REL, "relation")

    if sync_config.ENABLE_USAGE_RANK:
        assert_prop_type(db, sync_config.SVC_PROP_USAGE_RANK, "number")