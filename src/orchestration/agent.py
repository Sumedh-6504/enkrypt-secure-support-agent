import os
import asyncio
from typing import AsyncGenerator
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from enkryptai_sdk import GuardrailsClient

from src.ingestion.database import DatabaseManager
from src.orchestration.vector_management import VectorStoreFactory

class APISupportAgent:
    def __init__(self, top_k=1, cache_dir='local_cache'):
        # 1. Initialize DB and Factory
        self.db = DatabaseManager(cache_dir=cache_dir)
        
        # 🌟 BIFURCATION HAPPENS HERE: 
        # VectorStoreFactory automatically uses Postgres/PGVector if VECTOR_MODE=production
        # or SQLite/Chroma if VECTOR_MODE=local. 
        self.vs_factory = VectorStoreFactory()
        self.embeddings = self.vs_factory.get_embeddings()

        # 2. Setup LLM
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

        # 3. Setup Semantic Cache
        self.cache_store = self.vs_factory.get_vector_store(
            collection_name="essa_semantic_cache",
            persist_directory=cache_dir
        )

        # 4. Connect to Knowledge Base (Decoupled from local text files)
        self.vectorstore = self.vs_factory.get_vector_store(
            collection_name="essa_knowledge_base",
            persist_directory=cache_dir
        )
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})

        # 5. Enkrypt AI Policy & Guardrails
        self._init_guardrails()

        self.cache_threshold = 0.90
        
        # 6. Prompt & Chain Template
        template = """
        You are a highly technical and professional API Support Agent for Enkrypt AI.
        Your primary goal is to help developers integrate and troubleshoot Enkrypt AI products.

        Follow these core rules:
        1. **Strict Context:** Use ONLY the provided Context and Previous Conversation History to answer the Question. Do not use outside knowledge.
        2. **Clarity & Formatting:** Use Markdown formatting for your responses. Use `inline code` for variable names and ```language blocks``` for code snippets.
        3. **Honesty:** If the provided Context does not contain the answer, politely state: "I'm sorry, but I don't have enough information in my current knowledge base to answer that." Do not guess.
        4. **Tone:** Be concise, direct, and developer-friendly. Avoid fluff.
        5. **No Hallucinated Links:** Do NOT generate fake URLs or include your own citations. The system will automatically append the correct source links at the end.
        
        Context: 
        {context}
        
        Question: {question}
        
        Answer:
        """
        self.prompt = ChatPromptTemplate.from_template(template)
        
        # Simpler chain expecting a dict with 'context' and 'question'
        self.chain = self.prompt | self.llm | StrOutputParser()

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

    async def ask(self, question: str, session_id: str = "default_session"):
        """Standard asynchronous ask method."""
        try:
            # 0. Load Conversation History
            history = await asyncio.to_thread(self.db.get_chat_session, session_id)

            # 1. Input Guardrail
            input_check = await asyncio.to_thread(self.guardrails.detect, question, config=self.guardrails_config)
            if hasattr(input_check, 'is_safe') and not input_check.is_safe():
                self.db.log_security_event(question, "BLOCKED", "PROMPT_INJECTION")
                return "Security Alert: Request blocked by Enkrypt Guardrails."
            
            self.db.log_security_event(question, "SAFE", "None")

            # 2. Context Retrieval (Sync wrapped in thread to avoid asyncpg engine requirement for PGVector)
            source_docs = await asyncio.to_thread(self.retriever.invoke, question)
            context = "\n\n".join([doc.page_content for doc in source_docs])
            
            # Inject History into Context
            if history:
                context = f"Previous Conversation History:\n{history}\n\nDocument Context:\n{context}"
            unique_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in source_docs]))

            # 3. LLM Call
            response = await self.chain.ainvoke({"context": context, "question": question})

            # 4. Add Citations
            if unique_sources:
                response += "\n\n---\n**Sources:**\n" + "\n".join([f"- [{s}]({s})" for s in unique_sources])

            # 5. Output Guardrail
            output_check = await asyncio.to_thread(self.guardrails.detect, response, config=self.guardrails_config)
            if hasattr(output_check, 'is_safe') and not output_check.is_safe():
                return response + "\n\n[Security Alert: Content flagged by output policy.]"

            # 6. Save Updated History
            new_history = history + f"\nUser: {question}\nAgent: {response}\n"
            if len(new_history) > 4000:
                new_history = new_history[-4000:]
            await asyncio.to_thread(self.db.update_chat_session, session_id, new_history)

            return response
        except Exception as e:
            return f"[System Error: {str(e)}]"

    async def ask_stream(self, question: str, session_id: str = "default_session") -> AsyncGenerator[str, None]:
        try:
            # 0. Load Conversation History
            history = await asyncio.to_thread(self.db.get_chat_session, session_id)

            # 1. CACHE HIT CHECK
            results = await asyncio.to_thread(self.cache_store.similarity_search_with_relevance_scores, question, k=1)
            if results and results[0][1] >= self.cache_threshold:
                yield "🚀 **[CACHE HIT]**\n\n"
                yield results[0][0].metadata["answer"]
                return

            # 2. INPUT GUARDRAIL
            input_check = await asyncio.to_thread(self.guardrails.detect, question, config=self.guardrails_config)
            if hasattr(input_check, 'is_safe') and not input_check.is_safe():
                self.db.log_security_event(question, "BLOCKED", "PROMPT_INJECTION")
                yield "Security Alert: Request blocked by Enkrypt Guardrails."
                return
            
            self.db.log_security_event(question, "SAFE", "None")

            # 3. RETRIEVE CONTEXT (Sync wrapped in thread to avoid asyncpg engine requirement)
            source_docs = await asyncio.to_thread(self.retriever.invoke, question)
            context = "\n\n".join([doc.page_content for doc in source_docs])
            
            # Inject History into Context
            if history:
                context = f"Previous Conversation History:\n{history}\n\nDocument Context:\n{context}"
                
            unique_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in source_docs]))

            # 4. STREAM LLM RESPONSE
            full_response = ""
            gen_input = {"context": context, "question": question}
            
            async for chunk in self.chain.astream(gen_input):
                full_response += chunk
                yield chunk
            
            # 5. GENERATE CITATIONS
            if unique_sources:
                citation_block = "\n\n---\n**Sources:**\n" + "\n".join([f"- [{s}]({s})" for s in unique_sources])
                yield citation_block
                full_response += citation_block

            # 6. OUTPUT GUARDRAIL & CACHE
            output_check = await asyncio.to_thread(self.guardrails.detect, full_response, config=self.guardrails_config)
            if hasattr(output_check, 'is_safe') and not output_check.is_safe():
                yield "\n\n[Security Alert: Content flagged by output policy.]"
            
            await asyncio.to_thread(self.cache_store.add_texts, texts=[question], metadatas=[{"answer": full_response}])

            # 7. Save Updated History
            new_history = history + f"\nUser: {question}\nAgent: {full_response}\n"
            if len(new_history) > 4000:
                new_history = new_history[-4000:]
            await asyncio.to_thread(self.db.update_chat_session, session_id, new_history)

        except Exception as e:
            yield f"\n\n[System Error: {str(e)}]"
