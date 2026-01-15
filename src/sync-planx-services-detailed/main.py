import sync_config
import api_helpers as api
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def main():
    # Safety: only ever write to Services DB, but we will READ Councils DB.
    if not sync_config.SERVICES_DB_ID or sync_config.SERVICES_DB_ID == "REPLACE_ME":
        raise ValueError("SERVICES_DB_ID not set.")
    if not sync_config.COUNCILS_DB_ID or sync_config.COUNCILS_DB_ID == "REPLACE_ME":
        raise ValueError("COUNCILS_DB_ID not set.")
    if not sync_config.NOTION_TOKEN:
        raise ValueError("NOTION_TOKEN env var not set.")
    if not sync_config.METABASE_API_KEY:
        raise ValueError("METABASE_API_KEY env var not set.")

    notion = api.notion_client()

    # Validate we won't get type-mismatch errors mid-run
    api.validate_services_db_schema(notion)

    # 1) Fetch Metabase data
    df = api.fetch_metabase_df()
    log.info(f"Metabase rows: {len(df)}")

    # Optional: rank services per council by usage desc
    df = api.add_usage_rank_per_council(df)

    # 2) Councils lookup by reference code (READ ONLY)
    councils_by_ref = api.load_councils_by_ref_code(notion)
    log.info(f"Councils loaded (by Reference Code): {len(councils_by_ref)}")

    # 3) Existing service pages by flow_id (TITLE)
    services_idx = api.load_services_by_flow_id(notion)
    log.info(f"Existing service pages: {len(services_idx)}")

    to_create = []  # (props, council_page_id)
    to_update = []  # (page_id, props)
    to_relate = []  # (page_id, rel_ids)

    # Iterate rows
    for _, r in df.iterrows():
        row = r.to_dict()

        flow_id = (row.get("flow_id") or "").strip()
        if not flow_id:
            continue

        ref = (row.get("reference_code") or "").strip()
        council = councils_by_ref.get(ref) if ref else None

        council_page_id = council["page_id"] if council else None
        # For readability only; relation is the real reconciliation
        council_name_final = (
            council["name"] if council else (row.get("council_name") or "")
        ).strip()

        desired_props = api.build_service_props(row, council_name_final)

        cur = services_idx.get(flow_id)

        # Create
        if cur is None:
            to_create.append((desired_props, council_page_id))
            continue

        # Decide if update needed (avoid noisy updates)
        desired_ref = (
            desired_props[sync_config.SVC_PROP_REFERENCE_CODE]["rich_text"][0]["text"][
                "content"
            ]
            if desired_props[sync_config.SVC_PROP_REFERENCE_CODE]["rich_text"]
            else ""
        )
        desired_svcname = (
            desired_props[sync_config.SVC_PROP_SERVICE_NAME]["rich_text"][0]["text"][
                "content"
            ]
            if desired_props[sync_config.SVC_PROP_SERVICE_NAME]["rich_text"]
            else ""
        )
        desired_council_name = (
            desired_props[sync_config.SVC_PROP_COUNCIL_NAME]["rich_text"][0]["text"][
                "content"
            ]
            if desired_props[sync_config.SVC_PROP_COUNCIL_NAME]["rich_text"]
            else ""
        )
        desired_usage = desired_props[sync_config.SVC_PROP_USAGE]["number"]
        desired_url = desired_props[sync_config.SVC_PROP_URL]["url"]
        desired_first_online = (
            desired_props[sync_config.SVC_PROP_FIRST_ONLINE]["date"]["start"]
            if desired_props[sync_config.SVC_PROP_FIRST_ONLINE]["date"]
            else ""
        )

        changed = False
        if (cur["reference_code"] or "") != (desired_ref or ""):
            changed = True
        if (cur["service_name"] or "") != (desired_svcname or ""):
            changed = True
        if (cur["council_name"] or "") != (desired_council_name or ""):
            changed = True
        if int(cur["usage"] or 0) != int(desired_usage or 0):
            changed = True
        if (cur["url"] or "") != (desired_url or ""):
            changed = True
        if (cur["first_online"] or "") != (desired_first_online or ""):
            changed = True

        if sync_config.ENABLE_USAGE_RANK:
            desired_rank = desired_props[sync_config.SVC_PROP_USAGE_RANK]["number"]
            if int(cur.get("usage_rank_council") or 0) != int(desired_rank or 0):
                changed = True

        if changed:
            to_update.append((cur["page_id"], desired_props))

        # Relation reconciliation (join by reference_code)
        desired_rel = {council_page_id} if council_page_id else set()
        if cur["council_rel_ids"] != desired_rel:
            to_relate.append((cur["page_id"], list(desired_rel)))

        log.info(
            f"Planned -> create:{len(to_create)} update:{len(to_update)} "
            f"relate:{len(to_relate)}"
        )

    # Apply creates (Services DB only)
    for props, council_page_id in to_create:
        created = api.create_service_page(notion, props)
        api.gentle_sleep()
        if council_page_id:
            api.set_relation(
                notion,
                created["id"],
                sync_config.SVC_PROP_COUNCIL_REL,
                [council_page_id],
            )
            api.gentle_sleep()

    # Apply updates (Services DB only)
    for page_id, props in to_update:
        api.update_page(notion, page_id, props)
        api.gentle_sleep()

    # Apply relation fixes (Services DB only)
    for page_id, rel_ids in to_relate:
        api.set_relation(notion, page_id, sync_config.SVC_PROP_COUNCIL_REL, rel_ids)
        api.gentle_sleep()

    log.info("✅ Done. (Councils DB was read-only.)")


if __name__ == "__main__":
    main()
