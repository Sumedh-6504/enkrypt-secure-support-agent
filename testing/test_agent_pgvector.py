import asyncio
import os
from dotenv import load_dotenv
from agent import APISupportAgent

# Ensure environment is loaded
load_dotenv(override=True)

async def main():
    print("🤖 Initializing AI Support Agent (Production Mode)...")
    try:
        agent = APISupportAgent()
        question = "How do I integrate Enkrypt AI with Python?"
        
        print(f"\n❓ Question: {question}")
        print("-" * 30)
        
        async for chunk in agent.ask_stream(question):
            print(chunk, end="", flush=True)
            
        print("\n" + "-" * 30)
        print("\n✅ Test complete!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
