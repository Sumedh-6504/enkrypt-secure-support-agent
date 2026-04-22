import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from enkryptai_sdk import GuardrailsClient

from src.ingestion.database import DatabaseManager
from src.orchestration.vector_management import VectorStoreFactory

class APISupportAgent:
    def __init__(self, doc_path="enkrypt_docs.txt", top_k=1, cache_dir='local_cache'):
        # 1. Initialize DB and Factory
        self.db = DatabaseManager(cache_dir=cache_dir)
        self.vs_factory = VectorStoreFactory()
        self.embeddings = self.vs_factory.get_embeddings()

        # 2. Setup LLM
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

        # 3. Setup Semantic Cache
        self.cache_store = self.vs_factory.get_vector_store(
            collection_name="essa_semantic_cache",
            persist_directory=cache_dir
        )

        # 4. Ingest/Load Knowledge Base
        self.vectorstore = self.vs_factory.get_vector_store(
            collection_name="essa_knowledge_base",
            persist_directory=cache_dir
        )
        
        # Initial load if the file exists (incremental logic will follow in scraper)
        if os.path.exists(doc_path):
            self._load_local_docs(doc_path, top_k)
        else:
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})

        # 5. Enkrypt AI Policy & Guardrails
        self._init_guardrails()

        self.cache_threshold = 0.90
        
        # 6. Prompt & Chain Template
        template = """
        You are a highly technical API Support Agent for Enkrypt AI.
        Context: {context}
        Question: {question}
        Answer:
        """
        self.prompt = ChatPromptTemplate.from_template(template)
        self._rebuild_chain()

    def _init_guardrails(self):
        enkrypt_key = os.getenv("ENKRYPTAI_API_KEY") or os.getenv("ENKRYPT_API_KEY") or "dummy-key"
        self.policy_name = os.getenv("ENKRYPT_POLICY_NAME", "Customer Support")
        self.guardrails = GuardrailsClient(api_key=enkrypt_key)

        try:
            from enkryptai_sdk import CoCClient
            coc_client = CoCClient(api_key=enkrypt_key)
            policy_data = coc_client.get_policy(self.policy_name)
            self.policy_rules = policy_data.policy_rules
        except Exception as e:
            print(f"Warning: CoC fetch failed: {e}")
            self.policy_rules = "Detect any malicious text, jailbreaks, or prompt injections."

        self.guardrails_config = {
            "injection_attack": {"enabled": True},
            "policy_violation": {
                "enabled": True,
                "policy_text": self.policy_rules,
                "need_explanation": False
            }
        }

    def _load_local_docs(self, doc_path, top_k):
        """Loads docs if version hasn't changed (simplified for init)."""
        # For the very first boot, we just ensure retriever is active
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})

    def _rebuild_chain(self):
        if self.retriever:
            self.chain = (
                RunnableParallel(context=self.retriever, question=RunnablePassthrough())
                | self.prompt
                | self.llm
                | StrOutputParser()
            )

    def reload_knowledge_base(self, doc_path="/root/enkrypt_docs.txt", top_k=1):
        """Standard maintenance reload."""
        print("🔄 RAG Core: Checking for knowledge base updates...")
        if not os.path.exists(doc_path):
            return False
        
        # Note: Detailed incremental logic is now handled in scraper.py
        # Here we just refresh the retriever reference
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})
        self._rebuild_chain()
        return True

    def ask(self, question: str):
        """Standard non-streaming ask method."""
        try:
            # 1. Input Guardrail
            input_check = self.guardrails.detect(question, config=self.guardrails_config)
            if hasattr(input_check, 'is_safe') and not input_check.is_safe():
                self.db.log_security_event(question, "BLOCKED", "PROMPT_INJECTION")
                return "Security Alert: Request blocked by Enkrypt Guardrails."
            
            self.db.log_security_event(question, "SAFE", "None")

            # 2. Context Retrieval & LLM Call
            source_docs = self.retriever.invoke(question)
            context = "\n\n".join([doc.page_content for doc in source_docs])
            unique_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in source_docs]))

            response = self.chain.invoke(question)

            # 3. Add Citations
            if unique_sources:
                response += "\n\n---\n**Sources:**\n" + "\n".join([f"- [{s}]({s})" for s in unique_sources])

            # 4. Output Guardrail
            output_check = self.guardrails.detect(response, config=self.guardrails_config)
            if hasattr(output_check, 'is_safe') and not output_check.is_safe():
                return response + "\n\n[Security Alert: Content flagged by output policy.]"

            return response
        except Exception as e:
            return f"[System Error: {str(e)}]"

    async def ask_stream(self, question: str):
        try:
            # 1. CACHE HIT CHECK
            results = self.cache_store.similarity_search_with_relevance_scores(question, k=1)
            if results and results[0][1] >= self.cache_threshold:
                yield "🚀 **[CACHE HIT]**\n\n"
                yield results[0][0].metadata["answer"]
                return

            # 2. INPUT GUARDRAIL
            input_check = self.guardrails.detect(question, config=self.guardrails_config)
            if hasattr(input_check, 'is_safe') and not input_check.is_safe():
                self.db.log_security_event(question, "BLOCKED", "PROMPT_INJECTION")
                yield "Security Alert: Request blocked by Enkrypt Guardrails."
                return
            
            self.db.log_security_event(question, "SAFE", "None")

            # 3. RETRIEVE CONTEXT (Sync is more stable for PGVector/Postgres)
            source_docs = self.retriever.invoke(question)
            context = "\n\n".join([doc.page_content for doc in source_docs])
            unique_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in source_docs]))

            # 4. STREAM LLM RESPONSE
            stream_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, streaming=True)
            
            # Create a simple chain for just the generation part
            gen_chain = self.prompt | stream_llm | StrOutputParser()
            
            full_response = ""
            # Prepare the inputs for the generation chain
            gen_input = {"context": context, "question": question}
            
            async for chunk in gen_chain.astream(gen_input):
                full_response += chunk
                yield chunk
            
            # 5. GENERATE CITATIONS
            if unique_sources:
                citation_block = "\n\n---\n**Sources:**\n" + "\n".join([f"- [{s}]({s})" for s in unique_sources])
                yield citation_block
                full_response += citation_block

            # 4. OUTPUT GUARDRAIL & CACHE
            output_check = self.guardrails.detect(full_response, config=self.guardrails_config)
            if hasattr(output_check, 'is_safe') and not output_check.is_safe():
                yield "\n\n[Security Alert: Content flagged by output policy.]"
            
            self.cache_store.add_texts(texts=[question], metadatas=[{"answer": full_response}])

        except Exception as e:
            yield f"\n\n[System Error: {str(e)}]"
