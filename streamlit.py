import streamlit as st
import requests
import pandas as pd

API_URL = "https://jb23cs163--enkrypt-secure-support-agent-fastapi-app.modal.run/stream"
TELEMETRY_URL = "https://jb23cs163--enkrypt-secure-support-agent-fastapi-app.modal.run/telemetry"

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["💬 Support Chat", "🛡️ Admin Dashboard"])

if page == "💬 Support Chat":
    st.title("🛡️ Enkrypt Secure Support Agent")
    st.caption("Powered by Groq, LangChain & Enkrypt AI Guardrails")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())

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
            try:
                # Add stream=True to tell the requests library to stream the connection
                payload = {"question": prompt, "session_id": st.session_state.session_id}
                response = requests.post(API_URL, json=payload, stream=True)
                if response.status_code == 200:
                    # We start reading without showing success yet
                    def generate_chunks():
                        has_started = False
                        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                            if chunk:
                                # If the first chunk is our Security Alert, don't show success
                                if "Security Alert" in chunk and not has_started:
                                    st.error(f"🚫 {chunk}")
                                    yield chunk
                                    return
                                
                                if not has_started:
                                    st.success("✅ Passed Input Security Checks")
                                    has_started = True
                                
                                yield chunk
                    
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

elif page == "🛡️ Admin Dashboard":
    st.title("Admin Telemetry Dashboard")
    st.caption("Real-time Guardrail Analytics")
    
    # Simple password protection
    pwd = st.text_input("Admin Password", type="password")
    
    # Let's say the password is 'admin123' for now
    if pwd == "admin123":
        try:
            res = requests.get(TELEMETRY_URL)
            if res.status_code == 200:
                data = res.json()
                metrics = data.get("metrics", {})
                attacks = data.get("recent_attacks", [])
                
                # 1. Display Metric Cards
                col1, col2 = st.columns(2)
                col1.metric("Safe Requests ✅", metrics.get("SAFE", 0))
                col2.metric("Blocked Attacks 🚫", metrics.get("BLOCKED", 0))
                
                # 2. Add a clean Bar Chart for better visualization
                st.subheader("Traffic Analysis")
                chart_data = pd.DataFrame({
                    'Status': ['Safe', 'Blocked'],
                    'Count': [metrics.get("SAFE", 0), metrics.get("BLOCKED", 0)]
                })
                st.bar_chart(chart_data.set_index('Status'), color="#4d94ff")

                st.divider()
                
                # 3. Display Raw Attack Logs
                st.subheader("Recent Blocked Events")
                if attacks:
                    # Convert list of dicts to a clean Pandas DataFrame
                    df = pd.DataFrame(attacks)
                    st.dataframe(df, width='content')
                else:
                    st.info("No attacks logged yet! Try sending a jailbreak prompt in the chat.")
            else:
                st.error("Failed to load telemetry data from Modal.")
        except Exception as e:
            st.error(f"API Error: {e}")
