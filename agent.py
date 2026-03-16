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
    def __init__(self, doc_path="enkrypt_docs.txt", top_k=1):
        # 1. Setup Free Groq LLM
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

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
        # --- NEW: Enkrypt Input Check w/ Policy ---
        try:
            # Attempt to use the explicit policy name from the dashboard
            input_check = self.guardrails.detect(text=question, policy_name=self.policy_name)
        except TypeError:
            # Fallback if the SDK structure differs
            input_check = self.guardrails.detect(question)

        if hasattr(input_check, 'is_safe') and not input_check.is_safe:
            return "Security Alert: Request blocked by Enkrypt Guardrails."

        if not self.chain:
            return "System Error: Knowledge base not loaded."

        # Generate Answer
        answer = self.chain.invoke(question)

        # --- NEW: Enkrypt Output Check w/ Policy ---
        try:
            output_check = self.guardrails.detect(text=answer, policy_name=self.policy_name)
        except TypeError:
            output_check = self.guardrails.detect(answer)

        if hasattr(output_check, 'is_safe') and not output_check.is_safe:
            return "Security Alert: [REDACTED] due to Enkrypt Policy."

        return answer