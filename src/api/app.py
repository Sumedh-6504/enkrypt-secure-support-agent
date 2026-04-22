import modal
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# 1. Define Image & Add Source
image = (
    modal.Image.debian_slim()
    .env({"SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL": "True"})
    .pip_install(
        "scikit-learn",
        "langchain",
        "langchain-community",
        "langchain-groq",
        "langchain-huggingface",
        "langchain-postgres",
        "sentence-transformers",
        "chromadb",
        "fastapi",
        "enkryptai-sdk",
        "pandas",
        "tabulate",
        "httpx",
        "beautifulsoup4",
        "markdownify",
        "psycopg2-binary"
    )
    # Add the entire src directory so all modules are available in Modal
    .add_local_python_source("src")
)

app = modal.App("enkrypt-secure-support-agent", image=image)

# Create a volume for local caching/telemetry if not in production mode
volume = modal.Volume.from_name('essa_cache_volume', create_if_missing=True)

web_app = FastAPI(
    title="Enkrypt Secure API Support RAG",
    description="A highly secure, TDD-tested API support agent protected by Enkrypt Guardrails.",
    version="1.0.0"
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

# Global agent instance for warm-starting
support_agent: Optional[any] = None

def get_agent():
    """Lazy initializer for the agent."""
    global support_agent
    if support_agent is None:
        from src.orchestration.agent import APISupportAgent
        # Initialized without doc_path; relies on VECTOR_MODE and DB/Supabase
        support_agent = APISupportAgent(top_k=1, cache_dir="/root/cache")
    return support_agent

@app.function(
    secrets=[
        modal.Secret.from_name("my_groq_secret"),
        modal.Secret.from_name("my-enkrypt-secret"),
        modal.Secret.from_name("postgres-secret")
    ],
    volumes={"/root/cache": volume}
)
@modal.asgi_app()
def fastapi_app():
    # Warm up the agent on boot
    get_agent()
    return web_app

@web_app.get("/")
async def root():
    return {
        "message": "Enkrypt Secure Agent is Running 🛡️",
        "status": "online",
        "version": "1.0.0"
    }

@web_app.post("/ask")
async def ask_agent(request: QueryRequest):
    agent = get_agent()
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # 🌟 FIXED: Awaiting the now-async ask method
        answer = await agent.ask(request.question)

        # Check for guardrail blocks in the response
        if "Security Alert" in answer or "[REDACTED]" in answer:
            raise HTTPException(status_code=403, detail=f"Request blocked by Enkrypt Guardrails: {answer}")

        return {
            "question": request.question,
            "answer": answer,
            "security_status": "Passed Enkrypt Guardrails",
            "context_used": "top_k=1"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@web_app.post("/stream")
async def ask_agent_stream(request: QueryRequest):
    agent = get_agent()
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    return StreamingResponse(
        agent.ask_stream(request.question), 
        media_type="text/event-stream"
    )

@web_app.get("/telemetry")
async def get_telemetry_logs():
    """Admin endpoint to fetch logs from the DB (Postgres or local SQLite)."""
    agent = get_agent()
    try:
        # Using the agent's DB manager to fetch logs generically
        conn = agent.db._get_connection()
        cursor = conn.cursor()
        
        # 1. Metrics
        if agent.db.db_type == "postgres":
            cursor.execute("SELECT status, COUNT(*) FROM security_logs GROUP BY status")
        else:
            cursor.execute("SELECT status, COUNT(*) FROM security_logs GROUP BY status")
        metrics = dict(cursor.fetchall())
        
        # 2. Recent Attacks
        if agent.db.db_type == "postgres":
            cursor.execute("SELECT timestamp, question, policy_violation FROM security_logs WHERE status='BLOCKED' ORDER BY id DESC LIMIT 10")
        else:
            cursor.execute("SELECT timestamp, question, policy_violation FROM security_logs WHERE status='BLOCKED' ORDER BY id DESC LIMIT 10")
        
        attacks = [
            {"time": str(row[0]), "query": row[1], "violation": row[2]} 
            for row in cursor.fetchall()
        ]
        conn.close()
        
        return {"metrics": metrics, "recent_attacks": attacks}
    except Exception as e:
        return {"error": str(e)}

@web_app.post("/webhooks/update-docs")
async def handle_github_webhook(
    background_tasks: BackgroundTasks,
    authorization: str = Header(None)
):
    """Triggers the scraper to refresh knowledge base."""
    expected_token = os.getenv("WEBHOOK_SECRET", "enkrypt123")
    if not authorization or authorization != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    async def run_update():
        from src.ingestion.scraper import run_scraper
        await run_scraper()
        
    background_tasks.add_task(run_update)
    return {"status": "Accepted", "message": "Knowledge base update triggered."}
