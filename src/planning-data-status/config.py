# config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set


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
    dry_run: bool  # ✅ NEW


def build_config(notion_token: str) -> AppConfig:
    """
    Construct configuration for the app.
    Pass NOTION_TOKEN in from GHA Secrets.
    """

    datasette_query_url = (
        "https://datasette.planning.data.gov.uk/performance.json?"
        "sql=SELECT%0D%0A++rowid%2C%0D%0A++organisation%2C%0D%0A++organisation_name%2C%0D%0A++cohort%2C%0D%0A++dataset%2C%0D%0A++collection%2C%0D%0A++resource_start_date%2C%0D%0A++resource_end_date%2C%0D%0A++count_issues%2C%0D%0A++severity%2C%0D%0A++responsibility%2C%0D%0A++issue_type%2C%0D%0A++endpoint%2C%0D%0A++endpoint_url%2C%0D%0A++resource%2C%0D%0A++date%2C%0D%0A++field%0D%0AFROM+endpoint_dataset_issue_type_summary%0D%0AWHERE%0D%0A++organisation+LIKE+%27%25local-auth%25%27%0D%0A++AND+%28%22cohort%22+is+not+null+and+%22cohort%22+%21%3D+%22%22%29%0D%0A++++++AND+%28%0D%0A++++++dataset+%3D+%27article-4-direction-area%27%0D%0A++++++OR+dataset+%3D+%27conservation-area%27%0D%0A++++++OR+dataset+%3D+%27listed-building-outline%27%0D%0A++++++OR+dataset+%3D+%27tree-preservation-zone%27%0D%0A++++++OR+dataset+%3D+%27tree%27%0D%0A++++%29%0D%0A++%0D%0AORDER+BY%0D%0A++organisation_name%2C%0D%0A++dataset%2C%0D%0A++resource_start_date+DESC%2C%0D%0A++rowid+DESC%3B"
    )

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
        dry_run=False, #use this if you dont want to update notion pages
    )


def datasets(config: AppConfig) -> List[str]:
    return list(config.dataset_to_notion_prop.keys())


def notion_dataset_props(config: AppConfig) -> List[str]:
    return list(config.dataset_to_notion_prop.values())