import sqlite3
import os

db_path = os.path.join('local_cache', 'essa.db')

if not os.path.exists(db_path):
    print(f"Error: {db_path} not found!")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check Registry
        cursor.execute("SELECT count(*) FROM knowledge_base_registry")
        registry_count = cursor.fetchone()[0]
        print(f"Knowledge Base Registry: {registry_count} entries found.")
        
        # Check Logs
        cursor.execute("SELECT count(*) FROM security_logs")
        log_count = cursor.fetchone()[0]
        print(f"Security Logs: {log_count} entries found.")
        
        # Sample log
        if log_count > 0:
            cursor.execute("SELECT question, status FROM security_logs ORDER BY id DESC LIMIT 1")
            sample = cursor.fetchone()
            q_text = sample[0][:50] if sample[0] else "N/A"
            print(f"Latest security event: '{q_text}...' -> Result: {sample[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error reading database: {str(e)}")
