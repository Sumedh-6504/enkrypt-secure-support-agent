import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
load_dotenv()

try:
    from langchain_postgres.vectorstores import PGVector
except ImportError:
    PGVector = None

class VectorStoreFactory:
    def __init__(self, mode=None, embedding_model="all-MiniLM-L6-v2"):
        self.mode = mode or os.getenv("VECTOR_MODE", "local")
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.postgres_url = os.getenv("POSTGRES_URL")

    def get_vector_store(self, collection_name="essa_knowledge_base", persist_directory='local_cache'):
        if self.mode == "production" and self.postgres_url:
            if not PGVector:
                raise ImportError("langchain-postgres is required for PGVector. Run 'pip install langchain-postgres'")
            
            # Note: collection_name in PGVector refers to a specific table/collection in Postgres
            return PGVector(
                embeddings=self.embeddings,
                collection_name=collection_name,
                connection=self.postgres_url,
                use_jsonb=True,
            )
        else:
            # Default to local Chroma
            os.makedirs(persist_directory, exist_ok=True)
            return Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=persist_directory
            )

    def get_embeddings(self):
        return self.embeddings
