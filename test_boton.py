import streamlit as st

st.title("Test mínimo de botones")

if 'clicks' not in st.session_state:
    st.session_state.clicks = 0

st.write(f"Contador: {st.session_state.clicks}")

if st.button("Hacer click"):
    st.session_state.clicks += 1
    st.rerun()

st.write("Si el contador aumenta al tocar el botón, Streamlit funciona correctamente.")
