import os

import psycopg2
from dotenv import load_dotenv

# Force reload the environment
load_dotenv(override=True)

url = os.getenv('POSTGRES_URL')

print("--- Supabase Connection Diagnostic ---")
print(f"URL found in .env: {bool(url)}")
if url:
    # Mask password for safety in logs
    masked_url = url.split('@')[-1] if '@' in url else url
    print(f"Trying to connect to: {masked_url}")
    
    try:
        conn = psycopg2.connect(url)
        print("\n✅ SUCCESS: Connection established!")
        
        # Check if vectors are enabled
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        print("✅ Database is responsive.")
        conn.close()
    except psycopg2.Error as e:
        print(f"\n❌ FAILED: {e!s}")
        if "Tenant or user not found" in str(e):
            print("\nPOSSIBLE FIXES:")
            print("1. Ensure your username is formatted as: postgres.[YOUR-PROJECT-REF]")
            print("2. Current username detected from URL looks like it might be wrong.")
            print("3. Check if you are using 'Transaction Mode' port 6543 vs 'Session Mode' 5432.")
else:
    print("❌ ERROR: POSTGRES_URL not found in .env file.")
print("---------------------------------------")
