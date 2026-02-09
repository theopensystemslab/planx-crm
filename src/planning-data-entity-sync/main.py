from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from api_helpers import (
    create_council_page,
    fetch_json,
    query_all_database_pages,
    read_text_or_title,
    update_page_text_property,
)
from config import AppConfig, build_config

load_dotenv()


# ----------------------------
# Planning Data parsing
# ----------------------------


def _rows_to_dicts(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    # Common pattern: a single top-level key holding list[dict]
    for value in payload.values():
        if isinstance(value, list) and value:
            if isinstance(value[0], dict):
                return value

    rows = payload.get("rows")
    if isinstance(rows, list) and rows:
        if isinstance(rows[0], dict):
            return rows

        columns = payload.get("columns") or []
        if columns and isinstance(rows[0], list):
            dict_rows = []
            for row in rows:
                if not isinstance(row, list):
                    continue
                dict_rows.append({col: row[i] for i, col in enumerate(columns)})
            return dict_rows

    results = payload.get("results")
    if isinstance(results, list):
        return [row for row in results if isinstance(row, dict)]

    return []


def build_reference_maps(
    rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    entity_by_ref: Dict[str, str] = {}
    name_by_ref: Dict[str, str] = {}
    duplicates: List[Tuple[str, str, str]] = []

    for row in rows:
        ref = (row.get("reference") or "").strip()
        entity = row.get("entity")
        name = (row.get("name") or "").strip()
        if not ref or entity is None:
            continue

        entity_str = str(entity).strip()
        if ref in entity_by_ref and entity_by_ref[ref] != entity_str:
            duplicates.append((ref, entity_by_ref[ref], entity_str))
            continue

        entity_by_ref[ref] = entity_str
        if name and ref not in name_by_ref:
            name_by_ref[ref] = name

    if duplicates:
        print("[WARN] Duplicate reference codes with differing entity values:")
        for ref, prev, new in duplicates[:25]:
            print(f"- {ref}: {prev} vs {new}")
        if len(duplicates) > 25:
            print(f"... and {len(duplicates) - 25} more")

    return entity_by_ref, name_by_ref


# ----------------------------
# Dry Run helpers
# ----------------------------


def log_page_updates(ref: str, page_id: str, new_value: str) -> None:
    print(f"[DRY RUN] ref={ref} page={page_id}: PD Entity -> {new_value}")


def log_new_page(ref: str, council_name: str, pd_entity: str) -> None:
    print(
        f"[DRY RUN] create page: ref={ref} council={council_name} PD Entity={pd_entity}"
    )


# ----------------------------
# Orchestration
# ----------------------------


def detect_title_prop_name(pages: List[dict], config: AppConfig) -> str:
    for page in pages:
        props = page.get("properties") or {}
        council_prop = props.get(config.notion_council_name_prop) or {}
        if council_prop.get("type") == "title":
            return config.notion_council_name_prop
        ref_prop = props.get(config.notion_ref_code_prop) or {}
        if ref_prop.get("type") == "title":
            return config.notion_ref_code_prop
    return config.notion_council_name_prop


def sync_notion_from_planning_data(config: AppConfig) -> None:
    payload = fetch_json(
        config.planning_data_url, timeout_secs=config.request_timeout_secs
    )
    rows = _rows_to_dicts(payload)
    if not rows:
        payload_type = type(payload).__name__
        payload_keys = list(payload.keys()) if isinstance(payload, dict) else []
        raise ValueError(
            "Planning Data payload missing rows. "
            f"type={payload_type} keys={payload_keys}"
        )

    ref_to_entity, ref_to_name = build_reference_maps(rows)
    print(f"Loaded Planning Data rows: {len(rows)}")
    print(f"Reference codes mapped: {len(ref_to_entity)}")

    pages = query_all_database_pages(config)
    print(f"Loaded Notion pages: {len(pages)}")
    title_prop_name = detect_title_prop_name(pages, config)

    updated_pages = 0
    created_pages = 0
    skipped_no_ref = 0
    skipped_no_match = 0
    skipped_no_change = 0
    errors: List[Tuple[str, str]] = []
    updated_logs: List[str] = []
    skipped_logs: List[str] = []
    existing_refs: set[str] = set()

    for page in pages:
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
            existing_refs.add(ref)

            desired_entity = ref_to_entity.get(ref)
            if not desired_entity:
                skipped_no_match += 1
                if config.verbose_logs:
                    skipped_logs.append(
                        f"[SKIP] ref={ref} council={council_name} -> no PD entity match"
                    )
                continue

            current_entity = read_text_or_title(props, config.notion_pd_entity_prop)

            if config.only_update_if_changed and current_entity == desired_entity:
                skipped_no_change += 1
                if config.verbose_logs:
                    skipped_logs.append(
                        f"[SKIP] ref={ref} council={council_name} -> no changes needed"
                    )
                continue

            if config.dry_run:
                log_page_updates(ref, page_id, desired_entity)
            else:
                if config.verbose_logs:
                    from_value = current_entity or "empty"
                    log_line = (
                        f"[UPDATE] ref={ref} council={council_name} -> "
                        f"PD Entity {from_value} -> {desired_entity}"
                    )
                    updated_logs.append(log_line)
                update_page_text_property(
                    config, page_id, config.notion_pd_entity_prop, desired_entity
                )

            updated_pages += 1

            if updated_pages % 25 == 0:
                print(
                    "Progress: "
                    f"updated={updated_pages}, "
                    f"no_ref={skipped_no_ref}, "
                    f"no_match={skipped_no_match}, "
                    f"no_change={skipped_no_change}"
                )

        except Exception as e:
            errors.append((page.get("id", "unknown"), str(e)))

    missing_refs = [ref for ref in ref_to_entity.keys() if ref not in existing_refs]
    if missing_refs:
        print(f"Missing in Notion: {len(missing_refs)} (creating new pages)")
    for ref in missing_refs:
        try:
            council_name = ref_to_name.get(ref, "")
            pd_entity = ref_to_entity[ref]
            if config.dry_run:
                log_new_page(ref, council_name, pd_entity)
            else:
                create_council_page(
                    config, title_prop_name, council_name, ref, pd_entity
                )
            created_pages += 1
        except Exception as e:
            errors.append((ref, str(e)))

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
    create_label = "Would create pages" if config.dry_run else "Created pages"
    print(f"{create_label}: {created_pages}")
    print(f"Skipped (missing Reference Code): {skipped_no_ref}")
    print(f"Skipped (no PD entity match): {skipped_no_match}")
    print(f"Skipped (no changes needed): {skipped_no_change}")
    if errors:
        print(f"Errors: {len(errors)} (first 15)")
        for pid, err in errors[:15]:
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
