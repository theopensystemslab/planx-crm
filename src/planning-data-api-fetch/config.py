from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict


@dataclass(frozen=True)
class AppConfig:
    # ----------------------------
    # Planning Data API
    # ----------------------------
    planning_data_base_url: str
    dataset_to_notion_prop: Dict[str, str]
    dataset_enabled: Dict[str, bool]

    # ----------------------------
    # Notion
    # ----------------------------
    notion_token: str
    notion_database_id: str
    notion_ref_code_prop: str
    notion_council_name_prop: str
    notion_pd_entity_prop: str
    notion_version: str
    notion_base_url: str

    # ----------------------------
    # Behaviour
    # ----------------------------
    request_timeout_secs: int
    only_update_if_changed: bool
    dry_run: bool
    verbose_logs: bool


def build_config(notion_token: str) -> AppConfig:
    dry_run_env = os.environ.get("DRY_RUN")
    dry_run = (
        dry_run_env.strip().lower() in {"1", "true", "yes", "y", "on"}
        if dry_run_env is not None
        else False
    )
    dataset_to_notion_prop = {
        "article-4-direction-area": "PD-Article4",
        "conservation-area": "PD-ConservationArea",
        "listed-building-outline": "PD-ListedBuildingOutline",
        "tree": "PD-Trees",
        "tree-preservation-zone": "PD-TreePreservationZone",
    }
    return AppConfig(
        planning_data_base_url="https://www.planning.data.gov.uk/entity.json",
        dataset_to_notion_prop=dataset_to_notion_prop,
        dataset_enabled={
            # Toggle datasets on/off here
            "article-4-direction-area": True,
            "conservation-area": True,
            "listed-building-outline": True,
            "tree": True,
            "tree-preservation-zone": True,
        },
        notion_token=notion_token,
        notion_database_id="27c35d469ad180aaacf4d8beb0ddb20c",
        notion_ref_code_prop="Reference Code",
        notion_council_name_prop="Council Name",
        notion_pd_entity_prop="PD Entity",
        notion_version="2022-06-28",
        notion_base_url="https://api.notion.com/v1",
        request_timeout_secs=60,
        only_update_if_changed=True,
        dry_run=dry_run,
        verbose_logs=True,
    )
