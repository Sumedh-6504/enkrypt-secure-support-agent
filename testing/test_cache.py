import os
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("ENKRYPT_API_KEY"):
    print("Please set the ENKRYPT_API_KEY environment variable")
    exit(1)

if not os.getenv("GROQ_API_KEY"):
    print("Please set the GROQ_API_KEY environment variable")
    exit(1)

# if not os.getenv("ENKRYPT_POLICY_NAME"):
#     print("Please set the ENKRYPT_POLICY_NAME environment variable")
#     exit(1)

from src.orchestration.agent import APISupportAgent
import time

agent = APISupportAgent(cache_dir='./local_cache')

print("First call (Cache Miss)...")
start = time.time()
res1 = agent.ask("What is Enkrypt AI?")
print(f"Time: {time.time() - start:.2f}s")
print(res1)

print("\nSecond call (Cache Hit)...")
start = time.time()
res2 = agent.ask("What is Enkrypt AI?")
print(f"Time: {time.time() - start:.2f}s")
print(res2)

print("\nThird call (Different Question)...")
start = time.time()
res3 = agent.ask("How do I reset my password?")
print(f"Time: {time.time() - start:.2f}s")
print(res3)