import streamlit as st

st.set_page_config(page_title="Debug", layout="wide")

# Test 1: Botón simple
st.title("Test de navegación")

if "page" not in st.session_state:
    st.session_state.page = "home"

st.write(f"Página actual: {st.session_state.page}")

if st.button("Ir a Configuración"):
    st.session_state.page = "config"
    st.rerun()

# Test 2: Sidebar con radio
with st.sidebar:
    st.write("Sidebar")
    nav = st.radio("Navegar", ["home", "config"], index=0 if st.session_state.page == "home" else 1)
    if nav != st.session_state.page:
        st.session_state.page = nav
        st.rerun()

if st.session_state.page == "home":
    st.write("Estás en HOME")
elif st.session_state.page == "config":
    st.write("Estás en CONFIGURACIÓN")
    if st.button("Volver a Home"):
        st.session_state.page = "home"
        st.rerun()
