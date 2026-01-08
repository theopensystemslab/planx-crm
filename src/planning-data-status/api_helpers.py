# api_helpers.py
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from config import AppConfig


# ----------------------------
# Generic HTTP helpers
# ----------------------------

def fetch_json(url: str, timeout_secs: int) -> Dict[str, Any]:
    if not url:
        raise ValueError("Missing URL.")
    resp = requests.get(url, timeout=timeout_secs)
    resp.raise_for_status()
    return resp.json()


def request_with_retry(
    method: str,
    url: str,
    headers: Dict[str, str],
    timeout_secs: int,
    json_body: Optional[dict] = None,
    max_attempts: int = 7,
) -> requests.Response:
    backoff = 1.0

    for _ in range(max_attempts):
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            timeout=timeout_secs,
        )

        # Notion rate-limits with 429 + Retry-After
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            sleep_s = float(retry_after) if retry_after else backoff
            time.sleep(sleep_s)
            backoff = min(backoff * 2, 30)
            continue

        # transient server-side errors
        if 500 <= resp.status_code < 600:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        return resp

    return resp


# ----------------------------
# Notion helpers
# ----------------------------

def build_notion_headers(config: AppConfig) -> Dict[str, str]:
    if not config.notion_token:
        raise ValueError("Missing Notion token.")
    return {
        "Authorization": f"Bearer {config.notion_token}",
        "Notion-Version": config.notion_version,
        "Content-Type": "application/json",
    }


def query_all_database_pages(config: AppConfig, page_size: int = 100) -> List[dict]:
    """
    Returns ALL page objects in the database via Notion's paginated query endpoint.
    """
    url = f"{config.notion_base_url}/databases/{config.notion_database_id}/query"
    headers = build_notion_headers(config)

    pages: List[dict] = []
    payload: Dict[str, Any] = {"page_size": page_size}

    while True:
        resp = request_with_retry(
            "POST",
            url,
            headers=headers,
            timeout_secs=config.request_timeout_secs,
            json_body=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        pages.extend(data.get("results") or [])

        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")

    return pages


def update_page_select_properties(config: AppConfig, page_id: str, updates: Dict[str, str]) -> None:
    """
    updates: { property_name: select_option_name }
    """
    if not updates:
        return

    url = f"{config.notion_base_url}/pages/{page_id}"
    headers = build_notion_headers(config)

    properties_payload = {k: {"select": {"name": v}} for k, v in updates.items()}
    resp = request_with_retry(
        "PATCH",
        url,
        headers=headers,
        timeout_secs=config.request_timeout_secs,
        json_body={"properties": properties_payload},
    )
    resp.raise_for_status()


def read_select_name(page_properties: dict, prop_name: str) -> Optional[str]:
    prop = page_properties.get(prop_name)
    if not prop or prop.get("type") != "select":
        return None
    sel = prop.get("select")
    return sel.get("name") if sel else None


def read_text_or_title(page_properties: dict, prop_name: str) -> Optional[str]:
    """
    Reads a Notion property that might be rich_text or title.
    Returns the first plain_text value, stripped.
    """
    prop = page_properties.get(prop_name)
    if not prop:
        return None

    ptype = prop.get("type")
    if ptype == "rich_text":
        arr = prop.get("rich_text") or []
        if not arr:
            return None
        value = (arr[0].get("plain_text") or "").strip()
        return value or None

    if ptype == "title":
        arr = prop.get("title") or []
        if not arr:
            return None
        value = (arr[0].get("plain_text") or "").strip()
        return value or None

    return None