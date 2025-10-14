import requests
import json
import sys

def fetch_and_log_data():
    """
    Fetches list of teams and their associated online services from the PlanX GraphQL API 
    """
    api_url = "https://hasura.editor.planx.uk/v1/graphql"

    print(f"--- Starting data fetch from: {api_url} ---")

    body = {
        "operationName": "GetOnlineServicesPerTeam",
        "query": """
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
    }

    try:
        response = requests.post(api_url, json=body, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
          print("❌ GraphQL API returned errors:")
          print(json.dumps(data["errors"], indent=2))
          # Exit to make the GitHub Action fail
          sys.exit(1) 

        print("✅ Fetch successful!")
        print("--- Response Data ---")
        # Log out for now, we actually want to use the Notion API here
        print(json.dumps(data, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred during the request: {e}")
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON from the response.")

    print("--- Script finished ---")

if __name__ == "__main__":
    fetch_and_log_data()