# TODO: move to GH variables?

# --- Live DBs ---
COUNCILS_DB_ID = "27c35d469ad180aaacf4d8beb0ddb20c"
SERVICES_DB_ID = "28c35d469ad180e6b8ddc6de454d02dd"

# --- API ---
GRAPHQL_URL = "https://hasura.editor.planx.uk/v1/graphql"

# --- Property names ---
PROP_CUSTOMER_NAME = "Name"
PROP_CUSTOMER_EXT_ID = "ExternalCustomerID"
PROP_CUSTOMER_LAST_UPDATED = "Integration Last Updated"
PROP_CUSTOMER_SERVICES_REL = "PlanX Live Services"

PROP_SERVICE_NAME = "Name"
PROP_SERVICE_DESC = "Description"
PROP_SERVICE_COUNT = "Service Count"
PROP_SERVICE_EXT_ID = "ExternalCustomerID"
PROP_SERVICE_CUSTOMER_REL = "Councils"

# --- Behaviour ---
ARCHIVE_MISSING_SERVICE_PAGES = True
GENTLE_DELAY_SECONDS = 0.10
PAGE_SIZE = 100

# --- Allowlist ---
ALLOWLIST_TEAMS = {
    "barking-and-dagenham",
    "barnet",
    "birmingham",
    "buckinghamshire",
    "camden",
    "canterbury",
    "doncaster",
    "epsom-and-ewell",
    "gateshead",
    "gloucester",
    "horsham",
    "kingston",
    "lambeth",
    "medway",
    "newcastle",
    "south-gloucestershire",
    "southwark",
    "st-albans",
    "tewkesbury",
    "west-berkshire",
}

# --- GraphQL Query ---
GQL_QUERY = """
  query GetOnlineServicesPerTeam {
    teams(order_by: {slug: asc}) {
      id: slug
      displayName: name
      services: flows_aggregate(where: {status: {_eq: online}}, order_by: {slug: asc}) {
        service: nodes {
          name
          id: slug
        }
      }
    }
  }
"""
