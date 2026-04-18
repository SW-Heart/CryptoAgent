import psycopg2
import json
import os

from dotenv import load_dotenv
load_dotenv('.env', override=True)

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL in .env")
    exit(1)

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT id, api_key, api_secret, api_passphrase FROM exchange_accounts WHERE exchange_name = 'okx' LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No OKX accounts found")
    else:
        acct_id, api_key, api_secret, api_passphrase = row
        print(f"Found OKX account: {acct_id}")
        
        # Now we manually do an OKX request to avoid the project dependency nightmare!
        import requests
        import base64
        import hmac
        import time
        from datetime import datetime, timezone
        
        # get timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        method = "GET"
        request_path = "/api/v5/account/bills?limit=10"
        
        message = timestamp + method + request_path
        mac = hmac.new(bytes(api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        sign = base64.b64encode(d).decode('utf-8')
        
        headers = {
            "OK-ACCESS-KEY": api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": api_passphrase,
            "Content-Type": "application/json"
        }
        
        print(f"Requesting {request_path}...")
        res = requests.get(f"https://www.okx.com{request_path}", headers=headers)
        print(f"Status: {res.status_code}")
        body = res.json()
        print(json.dumps(body, indent=2))
        
except Exception as e:
    print(f"Error: {e}")

