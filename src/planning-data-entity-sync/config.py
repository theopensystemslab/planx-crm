from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    # ----------------------------
    # Planning Data API
    # ----------------------------
    planning_data_url: str

    # ----------------------------
    # Notion
    # ----------------------------
    notion_token: str
    notion_database_id: str
    notion_ref_code_prop: str
    notion_council_name_prop: str
    notion_pd_entity_prop: str
    notion_customer_status_prop: str
    notion_customer_status_new_value: str
    notion_version: str
    notion_base_url: str

    # ----------------------------
    # Behaviour
    # ----------------------------
    request_timeout_secs: int
    only_update_if_changed: bool
    dry_run: bool  # If true, do not perform updates
    verbose_logs: bool  # If true, log per-page details


def build_config(notion_token: str) -> AppConfig:
    """
    Construct configuration for the app.
    Pass NOTION_TOKEN in from GHA Secrets or env.
    """
    planning_data_url = (
        "https://www.planning.data.gov.uk/entity.json?"
        "dataset=local-authority&field=entity&field=dataset&field=reference&"
        "field=name&limit=500"
    )

    return AppConfig(
        planning_data_url=planning_data_url,
        notion_token=notion_token,
        notion_database_id="27c35d469ad180aaacf4d8beb0ddb20c",
        notion_ref_code_prop="Reference Code",
        notion_council_name_prop="Council Name",
        notion_pd_entity_prop="PD Entity",
        notion_customer_status_prop="Customer Status",
        notion_customer_status_new_value="New",
        notion_version="2022-06-28",
        notion_base_url="https://api.notion.com/v1",
        request_timeout_secs=60,
        only_update_if_changed=True,
        dry_run=False,
        verbose_logs=True,
    )
