"""Question-first local preparation, embedded in Estudios and the existing shell."""

import json
import os

import streamlit as st

from app.components.evidence import session_store
from app.components.shell import render_page_intro, render_section_title
from app.domain.research_models import ResearchBrief
from app.services.public_research_service import PublicResearchService
from app.services.llm_service import LLMError
from app.services.universe_service import build_expansion_snapshot
from app.storage.repository import save_expansion, save_universe, list_universes
from app.storage.research_repository import ResearchRepository

STATUS = {"sufficient": "Suficiente para explorar", "limited": "Alcance limitado", "insufficient": "Insuficiente"}
ASPECTS = {"backed": "Respaldado", "approximate": "Aproximado", "unknown": "Desconocido"}


def render_diagnosis(project, documents, *, key="research", export=True):
    diagnosis = project.diagnosis
    if not diagnosis:
        return
    st.subheader(STATUS.get(diagnosis["status"], "Insuficiente"))
    st.write("Pregunta evaluada: " + project.brief.question)
    st.caption("Este diagnóstico evalúa el fundamento de la audiencia. La precisión de sus respuestas todavía no está validada.")
    rows = [{"Aspecto": row["label"], "Estado": ASPECTS[row["status"]],
             "Importancia": "Central" if row["critical"] else "Secundario",
             "Motivo": row["reason"], "Pendiente": " ".join(row["issues"])} for row in diagnosis.get("rows", [])]
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    for reason in diagnosis.get("reasons", []):
        st.warning(reason)
    if diagnosis.get("suggested_scope"):
        st.info("Alcance sugerido: " + diagnosis["suggested_scope"] + ". Reformulá el brief y volvé a evaluarlo antes de continuar.")
    with st.expander("Fuentes, fragmentos y límites"):
        for limit in diagnosis.get("limitations", []):
            st.write("• " + limit)
        st.write("La composición es una decisión equilibrada de simulación." if diagnosis.get("composition") == "balanced_simulation"
                 else "La composición requiere porcentajes documentados para cada grupo.")
        for doc in documents:
            st.write(doc.title or doc.url)
            st.link_button("Abrir fuente", doc.url, key=f"{key}_source_{doc.id}")
            st.caption(f"Leída: {doc.fetched_at[:10]} · Publicación: {doc.published_at or 'Desconocida'} · " +
                       ("Excluida" if doc.id in project.excluded_ids else "Disponible" if doc.status == "read" else doc.error))
            findings = [f for f in project.findings if f["document_id"] == doc.id]
            for finding in findings:
                st.text(finding.get("quote", ""))
        if export:
            report = {"project": project.to_dict(), "documents": [d.to_dict() for d in documents]}
            st.download_button("Descargar fuentes y diagnóstico", json.dumps(report, ensure_ascii=False, indent=2),
                               file_name=f"evidencia_{project.id}.json", mime="application/json", key=f"{key}_export")


def _form(project):
    brief = project.brief if project else None
    # Durable values belong to the project, not to widgets that disappear between stages.
    with st.form("research_brief_form"):
        question = st.text_area("Pregunta", value=brief.question if brief else "", key="research_question")
        audience = st.text_area("¿A quién querés preguntarle?", value=brief.audience if brief else "", key="research_audience",
                                placeholder="Ejemplo: músicos principiantes que graban en casa")
        region = st.text_input("País o región", value=brief.region if brief else "", key="research_region")
        stimulus = st.text_area("Material que van a evaluar", value=brief.stimulus if brief else "", key="research_stimulus",
                                help="Pegá el guion, anuncio o propuesta. Si estudiás un tema general, podés dejarlo vacío.")
        with st.expander("Objetivo y condiciones del estudio"):
            goal = st.selectbox("Objetivo", ["explore", "proportions"], index=1 if brief and brief.goal == "proportions" else 0,
                                format_func={"explore": "Explorar respuestas", "proportions": "Estimar proporciones"}.get,
                                key="research_goal")
            price = st.text_input("Precio y moneda de la propuesta", value=brief.price if brief else "", key="research_price")
            situation = st.text_area("Situación en la que responden", value=brief.situation if brief else "", key="research_situation")
            as_of = st.text_input("Fecha del escenario (AAAA-MM-DD)", value=brief.as_of if brief else "", key="research_date",
                                 help="Vacío: fecha actual. Para escenarios históricos, las fuentes se evalúan a esa fecha.")
            options = st.text_area("Opciones de respuesta (opcional, una por línea)",
                                   value="\n".join(brief.options) if brief else "", key="research_options")
            holdouts = st.text_area("Fuentes reservadas para validar después (enlaces, uno por línea)",
                                    value="\n".join(brief.holdout_urls) if brief else "", key="research_holdouts",
                                    help="Estos documentos no se usarán para construir la audiencia.")
        submitted = st.form_submit_button("Preparar evidencia", type="primary", use_container_width=True)
    return submitted, dict(question=question.strip(), audience=audience.strip(), region=region.strip(),
                           stimulus=stimulus.strip(), goal=goal, price=price.strip(), situation=situation.strip(),
                           as_of=as_of.strip(), options=[s.strip() for s in options.splitlines() if s.strip()],
                           holdout_urls=[s.strip() for s in holdouts.splitlines() if s.strip()])


def handoff(project, universe_id, snapshot_id):
    st.session_state.update(est_preselect_universe=universe_id, est_pregunta=project.brief.question,
                            est_contexto=project.brief.participant_stimulus, est_mode="survey", est_rpp=1,
                            est_memory=False, est_tipo="cerrada" if project.brief.options else "abierta",
                            est_opciones="\n".join(project.brief.options), est_public_snapshot=snapshot_id,
                            est_public_universe_id=universe_id,
                            public_research_mode=False)
    st.rerun()


def render_public_research():
    render_page_intro("Estudios", "Preparar con evidencia pública",
                      "Escribí tu pregunta y público. Revisá el fundamento antes de crear la audiencia.")
    if st.button("Volver a mis audiencias", key="research_back"):
        st.session_state["public_research_mode"] = False
        st.rerun()
    store = session_store()
    if not store:
        st.info("Este recorrido funciona en tu equipo. Iniciá la app con scripts/start_private_app.ps1.")
        return
    repo = ResearchRepository(store)
    projects = repo.list_projects()
    choices = [""] + [p.id for p in projects]
    if "research_picker_next" in st.session_state:
        st.session_state["research_picker"] = st.session_state.pop("research_picker_next")
    selected = st.selectbox("Preparaciones guardadas", choices, key="research_picker",
                            format_func=lambda pid: "Nueva preparación" if not pid else next(
                                p.brief.question[:75] + " · " + p.created_at[:10] for p in projects if p.id == pid))
    project_id = st.session_state.get("research_project_id", "") or selected
    if st.session_state.get("research_picker_previous", "") != selected:
        project_id = selected
        st.session_state["research_project_id"] = selected
        for key in ("question", "audience", "region", "stimulus", "goal", "price", "situation", "date", "options", "holdouts"):
            st.session_state.pop("research_" + key, None)
    st.session_state["research_picker_previous"] = selected
    project = repo.get(project_id) if project_id else None
    if project and st.button("Nueva preparación", key="research_new"):
        st.session_state["research_picker_next"] = ""
        st.session_state["research_project_id"] = ""
        st.session_state["research_picker_previous"] = "__reset__"
        st.rerun()
    service = PublicResearchService(repo, max_rounds=int(os.getenv("RESEARCH_MAX_ROUNDS", "2")),
                                    max_queries=int(os.getenv("RESEARCH_MAX_QUERIES", "8")),
                                    max_documents=int(os.getenv("RESEARCH_MAX_DOCUMENTS", "20")))
    submitted, values = _form(project)
    if submitted:
        try:
            brief = ResearchBrief(**values)
            if not project or brief.signature != project.brief.signature:
                project = service.new_project(brief, project.id if project else "")
                st.session_state["research_project_id"] = project.id
                st.session_state["research_picker_next"] = project.id
            with st.status("Buscando y revisando evidencia…", expanded=True) as status:
                st.write("El procesamiento usa Ollama. Los documentos y avances quedan en este equipo.")
                service.prepare(project)
                status.update(label="Preparación guardada", state="complete")
        except Exception as exc:
            st.error("No se pudo completar la preparación. " + (str(exc) if isinstance(exc, ValueError) else
                     "Revisá Ollama y las dependencias. El avance disponible quedó guardado."))
        if project:
            project = repo.get(project.id)
    if not project:
        return
    # Unsaved changes invalidate the visible gate too; never build from a stale approved form.
    try:
        changed = ResearchBrief(**values).signature != project.brief.signature
    except ValueError:
        changed = True
    documents = repo.documents(project.document_ids)
    render_diagnosis(project, documents)
    if changed:
        st.info("Cambiaste el brief. Tocá Preparar evidencia para guardar una nueva versión y reevaluarla.")
    with st.expander("Completar o revisar fuentes"):
        with st.form("research_sources_form"):
            excluded = st.multiselect("Fuentes que querés excluir", [d.id for d in documents],
                                     default=project.excluded_ids, format_func=lambda did: next(
                                         d.title or d.url for d in documents if d.id == did), key=f"research_exclude_{project.id}")
            links = st.text_area("Agregar enlaces públicos (uno por línea)", key=f"research_links_{project.id}")
            focus = st.text_input("Vacío específico que querés investigar", key=f"research_focus_{project.id}")
            review = st.form_submit_button("Revisar evidencia")
        if review and not changed:
            try:
                if project.universe_id:
                    old_project = project
                    project = service.new_project(old_project.brief, old_project.id)
                    project.dimensions, project.required_inputs = old_project.dimensions, old_project.required_inputs
                    project.document_ids = list(old_project.document_ids)
                    project.findings = list(old_project.findings)
                    project.events = [e for e in old_project.events if e.get("type") == "analyzed"]
                    st.session_state["research_project_id"] = project.id
                    st.session_state["research_picker_next"] = project.id
                project.excluded_ids = excluded
                project.audit = {}
                service.refresh_diagnosis(project)
                service.add_urls(project, [url.strip() for url in links.splitlines() if url.strip()])
                with st.spinner("Revisando fuentes…"):
                    service.plan(project)
                    if focus:
                        service.search_round(project, focus)
                    service.analyze(project)
                st.rerun()
            except Exception:
                st.error("La revisión no pudo terminar. Se conservó el avance; revisá Ollama y reintentá.")
        elif review:
            st.warning("Guardá el brief actualizado antes de revisar fuentes.")
        st.caption(f"Búsquedas: {len(project.queries)}/{service.max_queries} · Documentos: {len(documents)}/{service.max_documents}")
        for event in project.events:
            if event.get("message"):
                st.caption(event["message"])
    can_build = bool(project.diagnosis.get("can_build")) and not changed
    if project.universe_id:
        if st.button("Usar esta audiencia en el estudio", key="research_use", type="primary", disabled=not can_build):
            handoff(project, project.universe_id, project.snapshot_id)
        return
    if not can_build:
        return
    render_section_title("Crear la audiencia")
    available = [u for u in list_universes() if u.research_snapshot_id]
    if available:
        with st.expander("Reutilizar una audiencia guardada"):
            chosen = st.selectbox("Audiencia existente", [u.id for u in available],
                                  format_func=lambda uid: next(u.nombre for u in available if u.id == uid), key="research_reuse_choice")
            if st.button("Preparar estudio con esta audiencia", key="research_reuse"):
                try:
                    universe = next(u for u in available if u.id == chosen)
                    snapshot_id = service.reuse_audience(project, universe)
                    project.universe_id, project.snapshot_id = universe.id, snapshot_id
                    repo.save(project)
                    handoff(project, universe.id, snapshot_id)
                except ValueError as exc:
                    st.error(str(exc))
    with st.form("research_build_form"):
        name = st.text_input("Nombre de la audiencia", value="Audiencia con evidencia pública")
        count = int(st.number_input("Participantes", min_value=1, max_value=1000, value=50))
        st.caption("Los pesos internos son decisiones de simulación. Más participantes no demuestra mayor precisión.")
        build = st.form_submit_button("Crear audiencia y preparar estudio", type="primary", use_container_width=True)
    if build:
        try:
            with st.spinner("Creando perfiles con sus fuentes…"):
                universe, personas, snapshot_id = service.build_audience(project, name, count)
                save_universe(universe)
                save_expansion(universe.id, build_expansion_snapshot(universe, personas))
                project.universe_id, project.snapshot_id, project.stage = universe.id, snapshot_id, "audience"
                repo.save(project)
            handoff(project, universe.id, snapshot_id)
        except Exception as exc:
            st.error("No se pudo crear la audiencia. " + (str(exc) if isinstance(exc, (ValueError, LLMError)) else
                     "Se conservó el expediente; reintentá o revisá las fuentes."))
