"""
app.py — Streamlit chat interface.

Run with:
    streamlit run app.py
"""

import streamlit as st
from agent import chat

st.set_page_config(page_title="Ecolab RAG Agent", page_icon="💧")
st.title("💧 Ecolab RAG Agent")
st.caption("Water Treatment · Hygiene · Sustainability")

# Session state
if "history" not in st.session_state:
    st.session_state.history = []

# Render past messages
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# New user input
if prompt := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply, st.session_state.history = chat(prompt, st.session_state.history)
        st.markdown(reply)

# Sidebar reset
with st.sidebar:
    st.header("Session")
    if st.button("🔄 Reset conversation"):
        st.session_state.history = []
        st.rerun()
    st.write(f"Messages: {len(st.session_state.history)}")
