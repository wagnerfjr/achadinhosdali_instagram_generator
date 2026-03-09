import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def run_query(sql: str) -> list[dict]:
    """
    Executes a SQL query on the remote VPS database.
    Reuses the HTTP logic from the existing CLI script.
    """
    ip = "178.18.255.15"
    url = f"https://{ip}/api/sync/sql-query"
    token = os.getenv("TOKEN_REMOTES")
    
    if not token:
        print("❌ TOKEN_REMOTES not found in .env")
        return []
        
    headers = {
        "x-war-token": token,
        "ngrok-skip-browser-warning": "true"
    }
    
    try:
        # verify=False for self-signed certs as in original script
        with httpx.Client(timeout=30.0, verify=False) as client:
            resp = client.post(url, json={"query": sql}, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("results", [])
                else:
                    print(f"❌ Query Error: {data.get('message')}")
                    return []
            else:
                print(f"❌ Connection Error: {resp.status_code} - {resp.text}")
                return []
                
    except Exception as e:
        print(f"💥 Critical Failure: {e}")
        return []
