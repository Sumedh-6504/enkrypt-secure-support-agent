import streamlit as st
import requests

# REPLACE WITH YOUR ACTUAL MODAL URL
API_URL = "https://jb23cs163--enkrypt-secure-support-agent-fastapi-app.modal.run/stream"

st.title("🛡️ Enkrypt Secure Support Agent")
st.caption("Powered by Groq, LangChain & Enkrypt AI Guardrails")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask about Enkrypt security..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # We don't need a spinner anymore because the text will start appearing instantly!
        try:
            # Add stream=True to tell the requests library to stream the connection
            response = requests.post(API_URL, json={"question": prompt}, stream=True)
            if response.status_code == 200:
                st.success("✅ Passed Input Security Checks")
                
                # Streamlit 1.31+ supports reading directly from generators.
                # We yield decoded text chunks as they arrive from the FastAPI server.
                def generate_chunks():
                    for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                        if chunk:
                            yield chunk
                
                # This magically types the text out on the screen like ChatGPT
                full_answer = st.write_stream(generate_chunks)
                
                st.session_state.messages.append({"role": "assistant", "content": full_answer})
            elif response.status_code == 403:
                error_msg = response.json().get("detail", "Blocked.")
                st.error(f"🚫 {error_msg}")
                st.session_state.messages.append({"role": "assistant", "content": f"🚫 {error_msg}"})
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Connection failed: {e}")
