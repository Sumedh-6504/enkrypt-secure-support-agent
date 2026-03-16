import streamlit as st
import requests

# REPLACE WITH YOUR ACTUAL MODAL URL
API_URL = "https://jb23cs163--enkrypt-secure-support-agent-fastapi-app.modal.run/ask"

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
        with st.spinner("Thinking (and Security Scanning)..."):
            try:
                response = requests.post(API_URL, json={"question": prompt})

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "No answer found.")
                    st.success("✅ Passed Security Checks")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                elif response.status_code == 403:
                    error_msg = response.json().get("detail", "Blocked.")
                    st.error(f"🚫 {error_msg}")
                    st.session_state.messages.append({"role": "assistant", "content": f"🚫 {error_msg}"})

                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")