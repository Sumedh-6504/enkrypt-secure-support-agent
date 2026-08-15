import os
from typing import Any

import modal
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def download_model():
    """Bake the HuggingFace model weights into the Modal image to prevent 30s cold starts."""
    from langchain_huggingface import HuggingFaceEmbeddings
    HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

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
        "langchain-chroma",
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
    .run_function(download_model)
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
    session_id: str = "default_session"

# Global agent instance for warm-starting
support_agent: Any | None = None

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
        modal.Secret.from_name("pgvector-db")
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

@web_app.get("/health/db")
async def health_db():
    """Diagnostic endpoint to verify if Modal is successfully hitting Supabase Postgres."""
    agent = get_agent()
    status = "disconnected"
    error = None
    
    try:
        conn = agent.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        conn.close()
        if result and result[0] == 1:
            status = "connected"
    except Exception as e:  # noqa: BLE001
        error = str(e)
        
    return {
        "vector_mode": os.getenv("VECTOR_MODE", "not_set"),
        "db_type": agent.db.db_type,
        "database_status": status,
        "error": error
    }

@web_app.post("/ask")
async def ask_agent(request: QueryRequest):
    agent = get_agent()
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # result is now a structured dict
        result = await agent.ask(request.question, request.session_id)

        # Check for guardrail blocks in the status
        if result.get("security_status") == "Blocked":
            return {
                "question": request.question,
                "answer": result["answer"],
                "citations": [],
                "reasoning": result.get("reasoning", []),
                "security_status": "Blocked"
            }

        return {
            "question": request.question,
            "answer": result["answer"],
            "citations": result.get("citations", []),
            "reasoning": result.get("reasoning", []),
            "security_status": result.get("security_status", "Passed"),
            "context_used": "top_k=1"
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

@web_app.post("/stream")
async def ask_agent_stream(request: QueryRequest):
    agent = get_agent()
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    return StreamingResponse(
        agent.ask_stream(request.question, request.session_id), 
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
    except Exception as e:  # noqa: BLE001
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
