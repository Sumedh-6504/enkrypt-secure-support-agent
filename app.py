import modal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from agent import APISupportAgent
from fastapi.responses import StreamingResponse
import sqlite3

# 1. Define Image & Add Files
image = (
    modal.Image.debian_slim()
    # Fix for the sklearn warning
    .env({"SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL": "True"})
    # Install dependencies
    .pip_install(
        "scikit-learn",
        "langchain",
        "langchain-community",
        "langchain-groq",
        "langchain-huggingface",
        "sentence-transformers",
        "chromadb",
        "fastapi",
        "enkryptai-sdk",
        "pandas",
        "tabulate"
    )
    # Add your local files directly to the image
    .add_local_file("agent.py", "/root/agent.py")
    .add_local_file("enkrypt_docs.txt", "/root/enkrypt_docs.txt")
)

app = modal.App("enkrypt-secure-support-agent", image=image)

# Create a volume to persist the Cache database
volume = modal.Volume.from_name('essa_cache_volume', create_if_missing=True)

web_app = FastAPI(
    title="Enkrypt Secure API Support RAG",
    description="A highly secure, TDD-tested API support agent protected by Enkrypt Guardrails.",
    version="1.0.0"
)


class QueryRequest(BaseModel):
    question: str


support_agent: Optional[APISupportAgent] = None


@app.function(
    secrets=[
        modal.Secret.from_name("my_groq_secret"),
        modal.Secret.from_name("my-enkrypt-secret")
    ],
    volumes = {"/root/cache": volume}
)
@modal.asgi_app()
def fastapi_app():
    global support_agent
    # Initialize the agent using the files we baked into the image
    support_agent = APISupportAgent(doc_path="/root/enkrypt_docs.txt", top_k=1)
    return web_app


@web_app.get("/")
async def root():
    return {
        "message": "Enkrypt Secure Agent is Running 🛡️",
        "endpoints": ["/docs", "/health", "/ask"]
    }

@web_app.get("/health")
async def health_check():
    return {"status": "healthy", "guardrails": "active", "retrieval_strictness": "top_k=1"}


@web_app.post("/ask")
async def ask_agent(request: QueryRequest):
    global support_agent

    # Cold start check
    if support_agent is None:
        support_agent = APISupportAgent(doc_path="/root/enkrypt_docs.txt", top_k=1)

    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        answer = support_agent.ask(request.question)

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
    global support_agent

    if support_agent is None:
        support_agent = APISupportAgent(doc_path="/root/enkrypt_docs.txt", top_k=1)

    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # FastAPI's StreamingResponse takes an async generator and streams it to the client
    return StreamingResponse(
        support_agent.ask_stream(request.question), 
        media_type="text/event-stream"
    )

@web_app.get("/telemetry")
async def get_telemetry_logs():
    db_path = "/root/cache/events.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count total safe vs blocked
        cursor.execute("SELECT status, COUNT(*) FROM security_logs GROUP BY status")
        counts = dict(cursor.fetchall())
        
        # Get the 10 most recent blocked attacks
        cursor.execute("SELECT timestamp, question, policy_violation FROM security_logs WHERE status='BLOCKED' ORDER BY id DESC LIMIT 10")
        blocked_logs = [
            {"time": row[0], "query": row[1], "violation": row[2]} 
            for row in cursor.fetchall()
        ]
        conn.close()
        
        return {
            "metrics": counts,
            "recent_attacks": blocked_logs
        }
    except Exception as e:
        return {"error": str(e)}
