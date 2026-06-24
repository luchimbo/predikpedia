import streamlit as st

st.set_page_config(page_title="Test", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "home"

st.write(f"Página: {st.session_state.page}")

if st.button("Ir a Config"):
    st.session_state.page = "config"
    st.rerun()

if st.session_state.page == "config":
    st.success("¡Navegación funciona! Estás en Config.")
    if st.button("Volver"):
        st.session_state.page = "home"
        st.rerun()
