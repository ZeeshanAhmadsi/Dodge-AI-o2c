
import json
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.analytical.tools.sql import _generate_sql
from app.services.analytical.tools.schema import _get_page_schema

def test_google_ads_generation():
    print("Testing SQL generation for 'google ads' enum matching...")
    
    schema = _get_page_schema("PID_LEAD_PAGE")
    user_question = "show all the leads to me from google ads"
    org_id = "68b6a7b220761d49073872af"
    
    # Mock column values that fetch_column_values would return
    column_values = {
        "Lead": {
            "source": ["WEBSITE", "LANDING_PAGE", "FACEBOOK_ADS", "GOOGLE_ADS", "LINKEDIN_ADS"]
        }
    }
    
    sql = _generate_sql(
        schema=schema,
        user_question=user_question,
        org_id=org_id,
        column_values=column_values
    )
    
    print("\nGENERATED SQL:")
    print("-" * 50)
    print(sql)
    print("-" * 50)
    
    # Assertions
    if "GOOGLE_ADS" in sql and "=" in sql:
        print("\nSUCCESS: SQL uses exact match 'GOOGLE_ADS' with '=' operator.")
    elif "GOOGLE_ADS" in sql and "ILIKE" in sql:
        print("\nPARTIAL SUCCESS: SQL uses 'GOOGLE_ADS' but still uses 'ILIKE'.")
    elif "google ads" in sql.lower():
        print("\nFAILURE: SQL still uses user string 'google ads'.")
    else:
        print("\nUNKNOWN: SQL content unexpected.")

if __name__ == "__main__":
    test_google_ads_generation()
