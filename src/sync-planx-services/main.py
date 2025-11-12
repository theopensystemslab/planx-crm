import os
import sys
import time
import logging
from notion_client import Client
from dotenv import load_dotenv

import config
import api_helpers as api

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


# ───────────────────────── Load Notion state ─────────────────────
def load_councils_by_ext(notion):
    """
    Return ext -> council_id for councils that already have ExternalCustomerID set
    """
    by_ext = {}
    for c in api.paginate_db(notion, config.COUNCILS_DB_ID):
        props = c["properties"]
        ext = api.text_val(props.get(config.PROP_CUSTOMER_EXT_ID, {}))
        if ext:
            by_ext[ext] = c["id"]
    log.info(f"Loaded {len(by_ext)} councils with ExternalCustomerIDs.")
    return by_ext


def load_services_index(notion):
    """
    ext_cust_id -> current service page snapshot (assumes one snapshot page per team)
    """
    idx = {}
    for s in api.paginate_db(notion, config.SERVICES_DB_ID):
        p = s["properties"]
        ext_id = api.text_val(p.get(config.PROP_SERVICE_EXT_ID, {})) or ""
        if not ext_id:
            continue
        idx[ext_id] = {
            "page_id": s["id"],
            "name": api.title_val(p.get(config.PROP_SERVICE_NAME, {})) or "",
            "description": api.text_val(p.get(config.PROP_SERVICE_DESC, {})) or "",
            "service_count": api.number_val(p.get(config.PROP_SERVICE_COUNT, {})),
            "rel_customer_ids": set(
                api.relation_ids(p.get(config.PROP_SERVICE_CUSTOMER_REL, {}))
            ),
        }
    log.info(f"Loaded {len(idx)} existing service pages.")
    return idx


# ───────────────────────── Main sync ─────────────────────────────
def main_sync(notion):
    """
    Runs the main data synchronization logic.
    """
    external = api.fetch_external_snapshot()

    councils_by_ext = load_councils_by_ext(notion)
    services_index = load_services_index(notion)

    to_create_services, to_update_services, to_relink, to_archive = [], [], [], []
    customers_changed = set()  # Councils to stamp 'Integration Last Updated'

    # Upserts & relinks for all whitelisted teams from GraphQL
    for slug, data in external.items():
        display_name = data["display_name"]
        description = data["description"]
        service_count = data["service_count"]
        target_cid = councils_by_ext.get(slug)

        cur = services_index.get(slug)
        if cur is None:
            to_create_services.append(
                (slug, display_name, description, service_count, target_cid)
            )
            if target_cid:
                customers_changed.add(target_cid)
        else:
            props = {}
            if (cur["name"] or "") != (display_name or ""):
                props[config.PROP_SERVICE_NAME] = {
                    "title": [{"text": {"content": display_name}}]
                }
            if (cur["description"] or "") != (description or ""):
                props[config.PROP_SERVICE_DESC] = {
                    "rich_text": [{"text": {"content": description}}]
                }
            if (cur["service_count"] or 0) != (service_count or 0):
                props[config.PROP_SERVICE_COUNT] = {"number": service_count}

            props[config.PROP_SERVICE_EXT_ID] = {
                "rich_text": [{"text": {"content": slug}}]
            }

            if props:
                to_update_services.append((cur["page_id"], props))
                if target_cid:
                    customers_changed.add(target_cid)

            desired_rel = {target_cid} if target_cid else set()
            if cur["rel_customer_ids"] != desired_rel:
                to_relink.append((cur["page_id"], list(desired_rel)))
                if target_cid:
                    customers_changed.add(target_cid)

    # Archive service pages no longer present in the external whitelist snapshot
    if config.ARCHIVE_MISSING_SERVICE_PAGES:
        for ext_id, cur in services_index.items():
            if ext_id in config.ALLOWLIST_TEAMS and ext_id not in external:
                to_archive.append((cur["page_id"], list(cur["rel_customer_ids"])))
                for prev_cid in cur["rel_customer_ids"]:
                    customers_changed.add(prev_cid)

    log.info(
        f"Planned → create:{len(to_create_services)} "
        f"update:{len(to_update_services)} "
        f"relink:{len(to_relink)} "
        f"archive:{len(to_archive)}"
    )

    # --- Apply changes ---
    for slug, name, desc, svc_count, cid in to_create_services:
        api.create_service_page(
            notion, slug, name, desc, svc_count, customer_page_id=cid
        )
        time.sleep(config.GENTLE_DELAY_SECONDS)

    for page_id, props in to_update_services:
        api.update_props(notion, page_id, props)
        time.sleep(config.GENTLE_DELAY_SECONDS)

    for page_id, rel_ids in to_relink:
        api.set_relation(
            notion, page_id, config.PROP_SERVICE_CUSTOMER_REL, rel_ids
        )
        time.sleep(config.GENTLE_DELAY_SECONDS)

    for page_id, prev_rel in to_archive:
        api.archive_page(notion, page_id)
        time.sleep(config.GENTLE_DELAY_SECONDS)

    # Stamp 'Integration Last Updated'
    log.info(f"Stamping 'Last Updated' for {len(customers_changed)} councils...")
    for cid in customers_changed:
        try:
            api.update_customer_last_updated(notion, cid)
            log.info(f"  ↳ Last Updated set for council {cid}")
        except Exception as e:
            log.warning(f"  ⚠️ Failed to update Last Updated for {cid}: {e}")
        time.sleep(config.GENTLE_DELAY_SECONDS)

    log.info("✅ LIVE sync finished.")


# ───────────────────────── Run ─────────────────────────────
if __name__ == "__main__":
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

    if not NOTION_TOKEN:
        log.error("FATAL: NOTION_TOKEN environment variable not set.")
        sys.exit(1)

    log.info("--- Starting Notion LIVE sync ---")

    notion = Client(auth=NOTION_TOKEN)

    try:
        main_sync(notion)
    except Exception as e:
        log.error("--- 🚨 Sync failed with uncaught exception ---")
        log.error(e, exc_info=True)
        sys.exit(1)
