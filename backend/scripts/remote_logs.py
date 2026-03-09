import httpx
import sys
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

def get_remote_logs(lines: int = 100):
    # VPS Configuration from environment or hardcoded fallback
    ip = "178.18.255.15"  # Found in previous commands
    url = f"http://{ip}/api/sync/logs"
    
    token = os.getenv("TOKEN_REMOTES")
    
    print(f"📡 Buscando as últimas {lines} linhas de log da VPS ({ip})...")
    
    headers = {
        "x-war-token": token
    }
    
    try:
        # Using timeout for the request
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params={"lines": lines}, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                if "logs" in data:
                    print("-" * 50)
                    print(data["logs"])
                    print("-" * 50)
                else:
                    print(f"❌ Resposta inesperada: {data}")
            else:
                print(f"❌ ERRO DE CONEXÃO: {resp.status_code} - {resp.text}")
                
    except Exception as e:
        print(f"💥 FALHA CRÍTICA: {e}")

if __name__ == "__main__":
    lines = 100
    if len(sys.argv) > 1:
        try:
            lines = int(sys.argv[1])
        except:
            pass
    get_remote_logs(lines)
