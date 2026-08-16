import streamlit as st
from console.components.signal_feed import render_signal_feed

st.set_page_config(page_title="EDGE-TF Console")

st.title("EDGE-TF Operator Console")

render_signal_feed()
