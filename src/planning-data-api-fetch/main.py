from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

from dotenv import load_dotenv

from api_helpers import (
    fetch_json,
    query_all_database_pages,
    read_checkbox,
    read_text_or_title,
    update_page_checkbox_properties,
)
from config import AppConfig, build_config

load_dotenv()


# ----------------------------
# Planning Data helpers
# ----------------------------


def build_planning_data_url(
    config: AppConfig, dataset: str, organisation_entity: str
) -> str:
    params = {
        "dataset": dataset,
        "organisation_entity": organisation_entity,
        "limit": 1,
    }
    return f"{config.planning_data_base_url}?{urlencode(params)}"


def extract_count(payload: Any) -> int:
    if isinstance(payload, dict):
        count = payload.get("count")
        if isinstance(count, int):
            return count
    return 0


# ----------------------------
# Dry Run helpers
# ----------------------------


def log_page_updates(ref: str, page_id: str, diffs: Dict[str, bool]) -> None:
    pretty = ", ".join([f"{k} → {v}" for k, v in diffs.items()])
    print(f"[DRY RUN] ref={ref} page={page_id}: {pretty}")


# ----------------------------
# Orchestration
# ----------------------------


def sync_notion_from_planning_data(config: AppConfig) -> None:
    selected_datasets = [
        d
        for d, enabled in config.dataset_enabled.items()
        if enabled and d in config.dataset_to_notion_prop
    ]
    if not selected_datasets:
        raise ValueError("No datasets enabled in config.dataset_enabled.")
    print(f"Datasets enabled: {', '.join(selected_datasets)}")

    filter_payload = {
        "and": [
            {"property": config.notion_ref_code_prop, "title": {"is_not_empty": True}},
            {
                "property": config.notion_pd_entity_prop,
                "rich_text": {"is_not_empty": True},
            },
        ]
    }
    pages = query_all_database_pages(config, filter_payload=filter_payload)
    print(f"Loaded Notion pages: {len(pages)}")

    updated_pages = 0
    skipped_no_ref = 0
    skipped_no_pd_entity = 0
    skipped_no_change = 0
    errors: List[Tuple[str, str]] = []
    updated_logs: List[str] = []
    skipped_logs: List[str] = []

    for page in pages:
        council_name = ""
        try:
            page_id = page.get("id")
            props = page.get("properties") or {}

            ref = read_text_or_title(props, config.notion_ref_code_prop)
            council_name = (
                read_text_or_title(props, config.notion_council_name_prop) or ""
            )
            if not ref:
                skipped_no_ref += 1
                if config.verbose_logs:
                    name_part = f" council={council_name}" if council_name else ""
                    skipped_logs.append(
                        f"[SKIP] {name_part.strip()} -> missing reference code"
                    )
                continue

            pd_entity = read_text_or_title(props, config.notion_pd_entity_prop)
            if not pd_entity:
                skipped_no_pd_entity += 1
                if config.verbose_logs:
                    skipped_logs.append(
                        f"[SKIP] ref={ref} council={council_name} -> missing PD Entity"
                    )
                continue

            desired: Dict[str, bool] = {}
            for dataset in selected_datasets:
                prop_name = config.dataset_to_notion_prop[dataset]
                url = build_planning_data_url(config, dataset, pd_entity)
                payload = fetch_json(url, timeout_secs=config.request_timeout_secs)
                desired[prop_name] = extract_count(payload) > 0

            diffs: Dict[str, bool] = {}
            if config.only_update_if_changed:
                for prop_name, new_value in desired.items():
                    current_value = read_checkbox(props, prop_name)
                    if current_value != new_value:
                        diffs[prop_name] = new_value

                if not diffs:
                    skipped_no_change += 1
                    if config.verbose_logs:
                        skipped_logs.append(
                            f"[SKIP] ref={ref} council={council_name} -> no changes"
                        )
                    continue
            else:
                diffs = desired

            if config.dry_run:
                log_page_updates(ref, page_id, diffs)
            else:
                if config.verbose_logs:
                    pretty = ", ".join([f"{k} → {v}" for k, v in diffs.items()])
                    updated_logs.append(
                        f"[UPDATE] ref={ref} council={council_name}: {pretty}"
                    )
                update_page_checkbox_properties(config, page_id, diffs)

            updated_pages += 1

            if updated_pages % 25 == 0:
                print(
                    "Progress: "
                    f"updated={updated_pages}, "
                    f"no_ref={skipped_no_ref}, "
                    f"no_pd_entity={skipped_no_pd_entity}, "
                    f"no_change={skipped_no_change}"
                )

        except Exception as e:
            label = council_name or "unknown council"
            errors.append((label, str(e)))

    if config.verbose_logs:
        if updated_logs:
            print("\n[UPDATED PAGES]")
            for line in updated_logs:
                print(line)
        if skipped_logs:
            print("\n[SKIPPED]")
            for line in skipped_logs:
                print(line)

    print("\n[SUMMARY]")
    print(f"Loaded Notion pages: {len(pages)}")
    print("✅ Finished")
    label = "Would update pages" if config.dry_run else "Updated pages"
    print(f"{label}: {updated_pages}")
    print(f"Skipped (missing Reference Code): {skipped_no_ref}")
    print(f"Skipped (missing PD Entity): {skipped_no_pd_entity}")
    print(f"Skipped (no changes needed): {skipped_no_change}")
    if errors:
        print(f"Errors: {len(errors)}")
        for pid, err in errors:
            print(f"- {pid}: {err}")


# ----------------------------
# Entry point
# ----------------------------


def main() -> None:
    notion_token = os.environ.get("NOTION_TOKEN")
    config = build_config(notion_token=notion_token)
    sync_notion_from_planning_data(config)


if __name__ == "__main__":
    main()
