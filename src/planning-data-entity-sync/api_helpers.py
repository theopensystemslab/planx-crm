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
    resp = request_with_retry("GET", url, timeout_secs=timeout_secs)
    resp.raise_for_status()
    return resp.json()


def request_with_retry(
    method: str,
    url: str,
    timeout_secs: int,
    headers: Optional[Dict[str, str]] = None,
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


def update_page_text_property(
    config: AppConfig, page_id: str, prop_name: str, value: str
) -> None:
    """
    Updates a rich_text property to the given string value.
    """
    if value is None:
        return

    url = f"{config.notion_base_url}/pages/{page_id}"
    headers = build_notion_headers(config)

    properties_payload = {prop_name: {"rich_text": [{"text": {"content": value}}]}}
    resp = request_with_retry(
        "PATCH",
        url,
        headers=headers,
        timeout_secs=config.request_timeout_secs,
        json_body={"properties": properties_payload},
    )
    resp.raise_for_status()


def create_council_page(
    config: AppConfig,
    title_prop_name: str,
    council_name: str,
    reference_code: str,
    pd_entity: str,
) -> None:
    url = f"{config.notion_base_url}/pages"
    headers = build_notion_headers(config)

    title_value = (
        reference_code
        if title_prop_name == config.notion_ref_code_prop
        else council_name
    )
    title_value = title_value or council_name or reference_code
    properties_payload = {
        title_prop_name: {"title": [{"text": {"content": title_value}}]},
        config.notion_pd_entity_prop: {"rich_text": [{"text": {"content": pd_entity}}]},
        config.notion_customer_status_prop: {
            "select": {"name": config.notion_customer_status_new_value}
        },
    }

    if config.notion_council_name_prop != title_prop_name:
        properties_payload[config.notion_council_name_prop] = {
            "rich_text": [{"text": {"content": council_name}}]
        }

    if config.notion_ref_code_prop != title_prop_name:
        properties_payload[config.notion_ref_code_prop] = {
            "rich_text": [{"text": {"content": reference_code}}]
        }

    resp = request_with_retry(
        "POST",
        url,
        headers=headers,
        timeout_secs=config.request_timeout_secs,
        json_body={
            "parent": {"database_id": config.notion_database_id},
            "properties": properties_payload,
        },
    )
    resp.raise_for_status()


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
