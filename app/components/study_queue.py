"""Display local worker state from the durable queue."""
import streamlit as st

from app.services.study_queue import progress_for, study_jobs, worker_online
from app.state import go_to_page


def render_job(study, job, online, *, show_link=False, refresh=False):
    labels = {
        "queued": "En cola" if online else "En espera · worker apagado",
        "running": "En ejecución" if online else "Interrumpido · se reanuda al iniciar el worker",
        "done": "Terminado",
        "failed": "Requiere revisión",
    }
    valid, processed = progress_for(study)
    st.caption(f"{labels[job.status]} · {processed} de {study.respuestas_planeadas} procesadas · {valid} válidas")
    if show_link and st.button("Ver estudio", key=f"queue_open_{study.id}"):
        st.session_state["res_study_id"] = study.id
        go_to_page("Resultados")
    if refresh and job.status in {"queued", "running"}:
        st.button("Actualizar estado", key=f"queue_refresh_{study.id}")


def render_recent_jobs(studies):
    jobs = study_jobs()
    queued = [study for study in studies if study.id in jobs]
    if not queued:
        return
    st.subheader("Estudios en segundo plano")
    online = worker_online()
    for study in queued[:5]:
        st.write(study.titulo)
        render_job(study, jobs[study.id], online, show_link=True)
    if any(job.status in {"queued", "running"} for job in jobs.values()):
        st.button("Actualizar estado", key="queue_home_refresh")
