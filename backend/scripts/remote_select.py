import httpx, sys, os, json
from dotenv import load_dotenv

load_dotenv()

# Carrega as configurações (ajuste o path se necessário)
# Se estiver rodando da raiz:
sys.path.append(os.getcwd())

def run_remote_query(sql: str):
    # IPs conhecidos da VPS (pode ser ajustado)
    ip = "178.18.255.15"
    url = f"https://{ip}/api/sync/sql-query"
    
    # O war-token é guardado no seu .env como TOKEN_REMOTES
    
    token = os.getenv("TOKEN_REMOTES")
    
    print(f"📡 Enviando query para a VPS ({ip})...")
    
    headers = {
        "x-war-token": token,
        "ngrok-skip-browser-warning": "true"
    }
    
    try:
        # verify=False pois a VPS pode usar certificado autogerado
        with httpx.Client(timeout=30.0, verify=False) as client:
            resp = client.post(url, json={"query": sql}, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    results = data.get("results", [])
                    print(f"✅ SUCESSO: {len(results)} linhas retornadas.\n")
                    if results:
                        # Print formatado como tabela simples ou JSON
                        print(json.dumps(results, indent=2, ensure_ascii=False))
                else:
                    print(f"❌ ERRO NA QUERY: {data.get('message')}")
            else:
                print(f"❌ ERRO DE CONEXÃO: {resp.status_code} - {resp.text}")
                
    except Exception as e:
        print(f"💥 FALHA CRÍTICA: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/remote_select.py \"SELECT * FROM raw_products LIMIT 5\"")
    else:
        query = " ".join(sys.argv[1:])
        run_remote_query(query)
