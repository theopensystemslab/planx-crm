from __future__ import annotations
from dotenv import load_dotenv
from config import AppConfig, build_config, datasets, notion_dataset_props
from api_helpers import (
    fetch_json,
    query_all_database_pages,
    read_select_name,
    read_text_or_title,
    update_page_select_properties,
)

import os
from typing import Any, Dict, List, Tuple
import pandas as pd

load_dotenv()

# ----------------------------
# Datasette -> DataFrame
# ----------------------------


def datasette_json_to_dataframe(payload: Dict[str, Any]) -> pd.DataFrame:
    cols = payload.get("columns") or []
    rows = payload.get("rows") or []
    if not cols:
        raise ValueError("Datasette payload missing 'columns'.")
    return pd.DataFrame(rows, columns=cols)


# ----------------------------
# Status computation
# ----------------------------


def compute_dataset_statuses(config: AppConfig, df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: organisation, dataset, status

    Status rules:
    - Active row: resource_end_date == ""
    - Needs Improving: any ACTIVE row has severity in problem_severities
    - Live: ACTIVE rows exist and none are problems
    - Expired: rows exist but none active
    - Not Submitted: no rows exist for that dataset/org (within organisations present)
    """
    if df.empty:
        return pd.DataFrame(columns=["organisation", "dataset", "status"])

    wanted_datasets = set(datasets(config))
    df = df[df["dataset"].isin(wanted_datasets)].copy()

    df["organisation"] = df["organisation"].fillna("").astype(str).str.strip()
    df["dataset"] = df["dataset"].fillna("").astype(str).str.strip()

    df["resource_end_date"] = df["resource_end_date"].fillna("").astype(str).str.strip()
    df["is_active"] = df["resource_end_date"].eq("")

    df["severity"] = df["severity"].fillna("").astype(str).str.lower().str.strip()
    df["is_problem"] = df["severity"].isin(config.problem_severities)

    # Aggregate per org/dataset
    grouped = (
        df.groupby(["organisation", "dataset"], dropna=False)
        .agg(
            has_active=("is_active", "any"),
            has_problem_active=(
                "is_problem",
                lambda s: bool((s & df.loc[s.index, "is_active"]).any()),
            ),
        )
        .reset_index()
    )

    def derive_status(row: pd.Series) -> str:
        if bool(row["has_active"]):
            return (
                config.status_needs_improving
                if bool(row["has_problem_active"])
                else config.status_live
            )
        return config.status_expired

    grouped["status"] = grouped.apply(derive_status, axis=1)

    # Build full grid (org x datasets) so missing => Not Submitted
    orgs = sorted(grouped["organisation"].unique().tolist())
    full_grid = pd.MultiIndex.from_product(
        [orgs, datasets(config)],
        names=["organisation", "dataset"],
    ).to_frame(index=False)

    status_long = full_grid.merge(
        grouped[["organisation", "dataset", "status"]],
        on=["organisation", "dataset"],
        how="left",
    )
    status_long["status"] = status_long["status"].fillna(config.status_not_submitted)
    return status_long


# ----------------------------
# Dry Run helpers
# ----------------------------


def log_page_updates(ref: str, page_id: str, diffs: Dict[str, str]) -> None:
    pretty = ", ".join([f"{k} → {v}" for k, v in diffs.items()])
    print(f"[DRY RUN] ref={ref} page={page_id}: {pretty}")


def log_page_updates_live(ref: str, page_id: str, diffs: Dict[str, str]) -> None:
    pretty = ", ".join([f"{k} → {v}" for k, v in diffs.items()])
    print(f"[UPDATE] ref={ref} page={page_id}: {pretty}")


# ----------------------------
# Mapping helpers
# ----------------------------


def organisation_to_reference_code(config: AppConfig, organisation: str) -> str:
    org = (organisation or "").strip()
    if config.ref_code_mode == "FULL":
        return org
    if ":" in org:
        return org.split(":", 1)[1].strip()
    return org


def build_notion_updates_by_ref(
    config: AppConfig, status_long: pd.DataFrame
) -> Dict[str, Dict[str, str]]:
    """
    { ref_code: { notion_property_name: status_string } }
    """
    by_ref: Dict[str, Dict[str, str]] = {}

    for organisation, grp in status_long.groupby("organisation"):
        ref = organisation_to_reference_code(config, organisation)

        dataset_status = {row["dataset"]: row["status"] for _, row in grp.iterrows()}
        by_ref[ref] = {
            config.dataset_to_notion_prop[dataset_slug]: status
            for dataset_slug, status in dataset_status.items()
        }

    return by_ref


def build_all_not_submitted_payload(config: AppConfig) -> Dict[str, str]:
    return {prop: config.status_not_submitted for prop in notion_dataset_props(config)}


def compute_select_diffs(
    page_properties: dict,
    desired: Dict[str, str],
) -> Dict[str, str]:
    """
    Returns only the properties whose select value differs from desired.
    """
    diffs: Dict[str, str] = {}
    for prop_name, new_value in desired.items():
        current_value = read_select_name(page_properties, prop_name)
        if current_value != new_value:
            diffs[prop_name] = new_value
    return diffs


# ----------------------------
# Orchestration
# ----------------------------


def sync_notion_from_datasette(config: AppConfig) -> None:
    # 1) Datasette -> status map
    payload = fetch_json(
        config.datasette_query_url, timeout_secs=config.request_timeout_secs
    )
    df = datasette_json_to_dataframe(payload)
    statuses = compute_dataset_statuses(config, df)
    updates_by_ref = build_notion_updates_by_ref(config, statuses)

    # 2) Notion -> pages
    pages = query_all_database_pages(config)
    print(f"Loaded Notion pages: {len(pages)}")

    updated_pages = 0
    skipped_no_ref = 0
    skipped_no_change = 0
    used_not_submitted_fallback = 0
    errors: List[Tuple[str, str]] = []
    updated_logs: List[str] = []
    fallback_logs: List[str] = []
    skipped_logs: List[str] = []

    not_submitted = build_all_not_submitted_payload(config)

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

            desired = updates_by_ref.get(ref)
            if desired is None:
                desired = not_submitted
                used_not_submitted_fallback += 1
                if config.verbose_logs:
                    fallback_logs.append(
                        f"[FALLBACK] ref={ref} council={council_name} "
                        "not in dataset -> using Not Submitted"
                    )

            if config.only_update_if_changed:
                diffs = compute_select_diffs(props, desired)
                if not diffs:
                    skipped_no_change += 1
                    if config.verbose_logs:
                        skipped_logs.append(
                            f"[SKIP] ref={ref} council={council_name} "
                            "-> no changes needed"
                        )
                    continue

                if config.dry_run:
                    log_page_updates(ref, page_id, diffs)
                else:
                    if config.verbose_logs:
                        pretty = "\n".join([f"- {k} -> {v}" for k, v in diffs.items()])
                        updated_logs.append(
                            f"[UPDATE] ref={ref} council={council_name}\n{pretty}"
                        )
                    update_page_select_properties(config, page_id, diffs)

            else:
                if config.dry_run:
                    # show everything we'd write (optionally only if it differs)
                    log_page_updates(ref, page_id, desired)
                else:
                    if config.verbose_logs:
                        pretty = "\n".join(
                            [f"- {k} -> {v}" for k, v in desired.items()]
                        )
                        updated_logs.append(
                            f"[UPDATE] ref={ref} council={council_name}\n{pretty}"
                        )
                    update_page_select_properties(config, page_id, desired)

            updated_pages += 1

            if updated_pages % 25 == 0:
                print(
                    f"Progress: updated={updated_pages}, "
                    f"fallback_not_submitted={used_not_submitted_fallback}, "
                    f"no_ref={skipped_no_ref}, "
                    f"no_change={skipped_no_change}"
                )

        except Exception as e:
            errors.append((page.get("id", "unknown"), str(e)))

    if config.verbose_logs:
        if updated_logs:
            print("\n[UPDATED PAGES]")
            for line in updated_logs:
                print(line)
        if fallback_logs:
            print("\n[FALLBACKS]")
            for line in fallback_logs:
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
    print(f"Ref not in datasette: {used_not_submitted_fallback}")
    print(f"Skipped (missing Reference Code): {skipped_no_ref}")
    print(f"Skipped (no changes needed): {skipped_no_change}")
    if errors:
        print(f"Errors: {len(errors)} (first 15)")
        for pid, err in errors[:15]:
            print(f"- {pid}: {err}")


# ----------------------------
# Entry point (Colab-friendly)
# ----------------------------


def main() -> None:
    notion_token = os.environ.get("NOTION_TOKEN")
    config = build_config(notion_token=notion_token)
    sync_notion_from_datasette(config)


if __name__ == "__main__":
    main()
