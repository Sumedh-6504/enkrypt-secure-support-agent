import os
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from enkryptai_sdk import GuardrailsClient


class APISupportAgent:
    def __init__(self, doc_path="enkrypt_docs.txt", top_k=1, cache_dir='/root/cache'):
        # 1. Setup Free Groq LLM
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        # Semantic Cache DB
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_store = Chroma(
            collection_name='semantic_cache',
            embedding_function=self.embeddings,
            persist_directory=cache_dir
        )
        self.cache_threshold = 0.90 # How similar a question needs to be

        # 2. Setup Enkrypt Guardrails
        enkrypt_key = os.getenv("ENKRYPTAI_API_KEY") or os.getenv("ENKRYPT_API_KEY")
        self.guardrails = GuardrailsClient(api_key=enkrypt_key)

        # --- NEW: Define Policy Name ---
        # Set to the exact name of the policy you created on the Enkrypt Dashboard
        self.policy_name = os.getenv("ENKRYPT_POLICY_NAME", "ESSA-Strict-Policy")

        # 3. Load Data
        if os.path.exists(doc_path):
            loader = TextLoader(doc_path, encoding="utf-8")
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = text_splitter.split_documents(docs)
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
                    {"context": self.retriever, "question": RunnablePassthrough()}
                    | self.prompt
                    | self.llm
                    | StrOutputParser()
            )
        else:
            self.chain = None

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
