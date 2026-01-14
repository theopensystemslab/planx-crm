# config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set
from urllib.parse import urlencode, quote_plus


@dataclass(frozen=True)
class AppConfig:
    # ----------------------------
    # Datasette
    # ----------------------------
    datasette_query_url: str

    # ----------------------------
    # Notion
    # ----------------------------
    notion_token: str
    notion_database_id: str
    notion_ref_code_prop: str
    notion_council_name_prop: str
    notion_version: str
    notion_base_url: str

    # ----------------------------
    # Dataset mapping + status values
    # ----------------------------
    dataset_to_notion_prop: Dict[str, str]
    status_live: str
    status_needs_improving: str
    status_not_submitted: str
    status_expired: str
    problem_severities: Set[str]

    # ----------------------------
    # Behaviour
    # ----------------------------
    request_timeout_secs: int
    ref_code_mode: str  # "CODE" | "FULL"
    only_update_if_changed: bool
    dry_run: bool  # If true, do not perform updates
    verbose_logs: bool  # If true, log per-page details


def build_config(notion_token: str) -> AppConfig:
    """
    Construct configuration for the app.
    Pass NOTION_TOKEN in from GHA Secrets.
    """

    BASE_URL = "https://datasette.planning.data.gov.uk/performance.json"

    sql_query = """
    SELECT
    rowid,
    organisation,
    organisation_name,
    cohort,
    dataset,
    collection,
    resource_start_date,
    resource_end_date,
    count_issues,
    severity,
    responsibility,
    issue_type,
    endpoint,
    endpoint_url,
    resource,
    date,
    field
    FROM endpoint_dataset_issue_type_summary
    WHERE
    organisation LIKE '%local-auth%'
    AND cohort IS NOT NULL
    AND cohort != ''
    AND dataset IN (
        'article-4-direction-area',
        'conservation-area',
        'listed-building-outline',
        'tree-preservation-zone',
        'tree'
    )
    ORDER BY
    organisation_name,
    dataset,
    resource_start_date DESC,
    rowid DESC;
    """.strip()

    params = {"sql": sql_query}

    query_string = urlencode(params, quote_via=quote_plus)
    datasette_query_url = f"{BASE_URL}?{query_string}"

    dataset_to_notion_prop = {
        "article-4-direction-area": "Dataset - Article 4 Direction Area",
        "conservation-area": "Dataset - Conservation Area",
        "listed-building-outline": "Dataset - Listed Building Outline",
        "tree-preservation-zone": "Dataset - TPZ",
        "tree": "Dataset - Trees",
    }

    return AppConfig(
        datasette_query_url=datasette_query_url,
        notion_token=notion_token,
        notion_database_id="27c35d469ad180aaacf4d8beb0ddb20c",
        notion_ref_code_prop="Reference Code",
        notion_council_name_prop="Council Name",
        notion_version="2022-06-28",
        notion_base_url="https://api.notion.com/v1",
        dataset_to_notion_prop=dataset_to_notion_prop,
        status_live="Live",
        status_needs_improving="Needs Improving",
        status_not_submitted="Not Submitted",
        status_expired="Expired",
        problem_severities={"error", "notice"},
        request_timeout_secs=60,
        ref_code_mode="CODE",
        only_update_if_changed=True,
        dry_run=False,  # use this if you dont want to update notion pages
        verbose_logs=True,
    )


def datasets(config: AppConfig) -> List[str]:
    return list(config.dataset_to_notion_prop.keys())


def notion_dataset_props(config: AppConfig) -> List[str]:
    return list(config.dataset_to_notion_prop.values())
