import os
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from enkryptai_sdk import GuardrailsClient
from langchain_core.documents import Document
import sqlite3
import datetime


class APISupportAgent:
    def __init__(self, doc_path="enkrypt_docs.txt", top_k=1, cache_dir='/root/cache'):
        # 1. Setup Free Groq LLM
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        # Semantic Cache DB
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_store = Chroma(
            collection_name="essa_semantic_cache",
            embedding_function=self.embeddings,
            persist_directory=cache_dir
        )

        # -------------------------------------------------------------
        # DYNAMIC CODE OF CONDUCT FETCHING
        # -------------------------------------------------------------
        enkrypt_key = os.getenv("ENKRYPTAI_API_KEY") or os.getenv("ENKRYPT_API_KEY")
        # Fallback to "Customer Support" if the environment variable is missing on Modal
        self.policy_name = os.getenv("ENKRYPT_POLICY_NAME", "Customer Support")
        try:
            from enkryptai_sdk import CoCClient
            coc_client = CoCClient(api_key=enkrypt_key)
            print(f"Fetching CoC Policy: {self.policy_name}")
            policy_data = coc_client.get_policy(self.policy_name)
            self.policy_rules = policy_data.policy_rules
            print(f"Successfully loaded {policy_data.total_rules} rules from Enkrypt Dashboard.")
        except Exception as e:
            print(f"Warning: Could not fetch CoC Policy '{self.policy_name}': {e}")
            self.policy_rules = "Detect any malicious text, jailbreaks, or prompt injections."

        self.guardrails_config = {
            "injection_attack": {"enabled": True},
            "policy_violation": {
                "enabled": True,
                "policy_text": self.policy_rules,
                "need_explanation": False
            }
        }

        self.cache_threshold = 0.90 # How similar a question needs to be

        # NEw DB Initialisation for telemetry dahsboard
        self.db_path = os.path.join(cache_dir, "events.db")
        self._init_db()

        # 2. Setup Enkrypt Guardrails
        enkrypt_key = os.getenv("ENKRYPTAI_API_KEY") or os.getenv("ENKRYPT_API_KEY") or "dummy-key"
        self.guardrails = GuardrailsClient(api_key=enkrypt_key)

        # --- NEW: Define Policy Name ---
        # Fallback to "Customer Support" if the environment variable is missing on Modal
        self.policy_name = os.getenv("ENKRYPT_POLICY_NAME", "Customer Support")

        # 3. Load Data
        if os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            pages = content.split("### SOURCE: ")

            raw_docs = []
            for page in pages:
                if not page.strip():
                    continue
                parts = page.split(" ###\n\n", 1)
                if len(parts) == 2:
                    url = parts[0].strip()
                    text = parts[1].strip()
                    raw_docs.append(Document(page_content=text, metadata={"source": url}))
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = text_splitter.split_documents(raw_docs)

            self.vectorstore = Chroma.from_documents(documents=splits, embedding=self.embeddings)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})
        else:
            # Fallback for tests if file isn't created yet
            self.retriever = None
            self.vectorstore = None

        # 4. Prompt
        template = """
        You are a highly technical API Support Agent for Enkrypt AI.
        Context: {context}
        Question: {question}
        Answer:
        """
        self.prompt = ChatPromptTemplate.from_template(template)

        # 5. Chain
        if self.retriever:
            self.chain = (
                    RunnableParallel(context=self.retriever, question=RunnablePassthrough())
                    | self.prompt
                    | self.llm
                    | StrOutputParser()
            )
        else:
            self.chain = None

    def reload_knowledge_base(self, doc_path="/root/enkrypt_docs.txt", top_k=1):
        """Atomically hot-swaps the underlying vector database."""
        print("🔄 RAG Core: Rebuilding Knowledge Base from disk...")
        if not os.path.exists(doc_path):
            print("❌ RAG Core: Documentation file not found!")
            return False

        # Load new text and split
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        pages = content.split("### SOURCE: ")

        raw_docs = []
        for page in pages:
            if not page.strip():
                continue
            parts = page.split(" ###\n\n", 1)
            if len(parts) == 2:
                url = parts[0].strip()
                text = parts[1].strip()
                raw_docs.append(Document(page_content=text, metadata={"source": url}))
            
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(raw_docs)

        # Build fresh vectorstore & retriever
        new_vectorstore = Chroma.from_documents(documents=splits, embedding=self.embeddings)
        new_retriever = new_vectorstore.as_retriever(search_kwargs={"k": top_k})

        # Atomically swap the live references to prevent dropping active chat requests
        self.vectorstore = new_vectorstore
        self.retriever = new_retriever
        
        from langchain_core.runnables import RunnableParallel, RunnablePassthrough
        from langchain_core.output_parsers import StrOutputParser
        
        self.chain = (
                RunnableParallel(context=self.retriever, question=RunnablePassthrough())
                | self.prompt
                | self.llm
                | StrOutputParser()
        )
        print("✅ RAG Core: Knowledge Base successfully hot-swapped!")
        return True


    def ask(self, question: str) -> str:
        # 1. CHECK SEMANTIC CACHE FIRST
        results = self.cache_store.similarity_search_with_relevance_scores(question, k=1)
        if results:
            doc, score = results[0]
            # Since distance metrics vary, a lower distance or higher score means closer match.
            # Depending on Chroma config, higher score is usually better.
            if score >= self.cache_threshold:
                print(f"✅ CACHE HIT! Score: {score}")
                return doc.metadata["answer"]

        print("❌ CACHE MISS. Running full LLM and Security Pipeline.")

        # 2. RUN FULL PIPELINE (If no cache hit)

        # Enkrypt Input Check
        input_check = self.guardrails.detect(question)
        if hasattr(input_check, 'is_safe') and not input_check.is_safe:
            return "Security Alert: Request blocked by Enkrypt Guardrails."

        if not self.chain:
            return "System Error: Knowledge base not loaded."

        # Generate Answer
        answer = self.chain.invoke(question)

        # Enkrypt Output Check
        output_check = self.guardrails.detect(answer)
        if hasattr(output_check, 'is_safe') and not output_check.is_safe:
            return "Security Alert: [REDACTED] due to Enkrypt Policy."

        # 3. STORE NEW APPROVED ANSWER IN CACHE
        self.cache_store.add_texts(
            texts=[question],  # We embed the question to search against later
            metadatas=[{"answer": answer}]  # We store the answer as metadata
        )

        return answer
    
    def _init_db(self):
        """ Creates the telemetry table if it doesn't exist. """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                question TEXT,
                status TEXT,
                policy_violation TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _log_event(self, question: str, status: str, policy: str = "None"):
        """Inserts an event into the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.datetime.now().isoformat()
            # Mask the question for privacy if it was safe, but log the attack if unsafe.
            # (Optional: you can log the full question for both)
            cursor.execute(
                "INSERT INTO security_logs (timestamp, question, status, policy_violation) VALUES (?, ?, ?, ?)",
                (timestamp, question, status, policy)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to log event: {e}")

    async def ask_stream(self, question: str):
        """Asynchronous generator that streams LLM tokens after checking input guardrails."""
        try:
            # 1. Enkrypt Input Guardrail (Synchronous block)
            print(f"DEBUG: Checking Input Guardrail for policy: {self.policy_name}")
            input_check = self.guardrails.detect(question, config=self.guardrails_config)
            
            if hasattr(input_check, 'is_safe') and not input_check.is_safe():
                print("DEBUG: Request BLOCKED")
                self._log_event(question, "BLOCKED", "PROMPT_INJECTION")
                yield "Security Alert: Request blocked by Enkrypt Guardrails."
                return
            
            self._log_event(question, "SAFE", "None")
            print("DEBUG: Request PASSED input check")

            # 2. Setup Chain
            if not self.retriever:
                yield "Error: Knowledge base not initialized."
                return

            # Note: We create a fresh LLM instance with streaming=True
            stream_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, streaming=True)
            stream_chain = (
                RunnableParallel(context=self.retriever, question=RunnablePassthrough())
                | self.prompt
                | stream_llm
                | StrOutputParser()
            )

            # -----------------------------------------------------------------
            # NEW: Context Citation Extraction
            # -----------------------------------------------------------------
            source_docs = self.retriever.invoke(question)
            unique_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in source_docs]))
            citation_text = "\n\n**Sources:** " + ", ".join(unique_sources)
            citation_block = ""
            if unique_sources:
                citation_block += "\n\n---\n**Sources:**\n"
                for url in unique_sources:
                    citation_block += f"- [{url}]({url})\n"
            

            # 3. Stream Tokens
            full_response = ""
            async for chunk in stream_chain.astream(question):
                full_response += chunk
                yield chunk
            
            # -----------------------------------------------------------------
            # NEW: Yield the Citations at the end of the Stream
            # -----------------------------------------------------------------
            if citation_block:
                yield citation_block
                full_response += citation_block
            # -----------------------------------------------------------------

            # 4. Enkrypt Output Guardrail (Post-stream)
            # This doesn't block the stream (it's already over), but we log it.
            output_check = self.guardrails.detect(full_response, config=self.guardrails_config)
            if hasattr(output_check, 'is_safe') and not output_check.is_safe():
                print("DEBUG: Output Guardrail flagged content")
                yield "\n\n[Security Alert: Content flagged by output policy.]"

            # 5. Cache the Result
            self.cache_store.add_texts(texts=[question], metadatas=[{"answer": full_response}])

        except Exception as e:
            print(f"CRITICAL ERROR in ask_stream: {str(e)}")
            yield f"\n\n[System Error: {str(e)}]"
