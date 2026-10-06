"""Survey/interview/social execution with frozen context and provenance."""

import random
from collections.abc import Callable
from uuid import NAMESPACE_URL, uuid5

from app.domain.models import Estudio, RespuestaEstudio
from app.services.evidence_service import evidence_for_persona, redact_contacts
from app.services.llm_service import LLMError
from app.services.study_response_service import build_system_prompt, build_user_prompt, parse_study_response
from app.storage.evidence_repository import EvidenceRepository, identity_for


def social_graph(persona_ids: list[str], seed: int = 42) -> dict[str, list[str]]:
    """Seeded ring: at most two peers, no self-exposure, undirected and reproducible."""
    ids = sorted(persona_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("La muestra tiene IDs repetidos. Regenerá la expansión antes de ejecutar.")
    random.Random(seed).shuffle(ids)
    graph = {}
    for i, identity in enumerate(ids):
        graph[identity] = sorted({ids[(i - 1) % len(ids)], ids[(i + 1) % len(ids)]} - {identity})
    return graph


def planned_tasks(study: Estudio, count: int) -> int:
    if study.mode == "social":
        return count * 2
    if study.mode == "interview":
        return count * (1 + len(study.follow_up_questions))
    return count * study.respuestas_por_persona


def run_simulation(study: Estudio, personas: list[dict], engine, *, store: EvidenceRepository | None = None,
                   on_response: Callable | None = None, should_stop: Callable | None = None) -> list[RespuestaEstudio]:
    if study.mode not in {"survey", "interview", "social"}:
        raise ValueError("La modalidad de estudio no es válida.")
    if not personas or len({p.get("persona_id") for p in personas}) != len(personas) or any(not p.get("persona_id") for p in personas):
        raise ValueError("La muestra necesita personas con identificadores únicos.")
    if study.mode == "social" and len(personas) < 2:
        raise ValueError("La interacción necesita al menos dos personas.")
    if study.mode != "survey" and study.respuestas_por_persona != 1:
        raise ValueError("Entrevistas e interacción usan una respuesta por pregunta y ronda.")
    if study.mode == "survey" and study.memory_enabled:
        raise ValueError("Las encuestas independientes no pueden usar historial de entrevistas.")
    if study.mode != "interview" and study.follow_up_questions:
        raise ValueError("Las preguntas de seguimiento se usan solo en entrevistas.")
    if len(study.follow_up_questions) > 4 or any(not isinstance(q, str) or not q.strip() for q in study.follow_up_questions):
        raise ValueError("Escribí hasta cuatro preguntas de seguimiento, sin líneas vacías.")
    if not 1 <= study.respuestas_por_persona <= 5:
        raise ValueError("Elegí entre una y cinco repeticiones.")
    if store is None and (study.memory_enabled or any(p.get("evidence_refs") or p.get("evidence_source_ids") for p in personas)):
        raise ValueError("Esta audiencia necesita su almacenamiento privado de evidencia y memoria. Abrila en el equipo donde fue creada.")
    study.interaction_graph = social_graph([p["persona_id"] for p in personas], study.social_seed) if study.mode == "social" else {}
    identities = {p["persona_id"]: (store.register_agent(study.universo_id, p) if store else identity_for(study.universo_id, p)) for p in personas}
    # Freeze BEFORE generation: no within-round or order-dependent memory leak.
    evidence = {p["persona_id"]: evidence_for_persona(store, p) if store else [] for p in personas}
    for p in personas:
        if store and any(store.source(sid) is None for sid in p.get("evidence_source_ids", [])):
            raise ValueError("Falta una fuente de origen de la audiencia. Recuperá el almacenamiento privado antes de ejecutar.")
        expected = set(p.get("evidence_refs") or [])
        available = {item["case_ref"] for item in evidence[p["persona_id"]]}
        if not expected.issubset(available):
            raise ValueError("Falta evidencia vinculada a una persona. Revisá las fuentes en el equipo donde se creó la audiencia.")
    history = {pid: (store.history(identity, exclude_study=study.id) if store and study.memory_enabled else []) for pid, identity in identities.items()}
    if store:
        store.start_run(study.id, {"study": study.to_dict(), "identities": identities,
                                   "evidence": evidence, "history": history})
        if store.run_responses(study.id):
            raise ValueError("Esta corrida ya tiene respuestas guardadas. Creá un estudio nuevo para no volver a consultar agentes.")
    answers, baseline = [], {}
    stopped = False

    def respond(persona, question, index, repetition, phase, round_number, local_history, peers):
        nonlocal stopped
        if should_stop and should_stop():
            stopped = True
            return None
        pid = persona["persona_id"]
        response_id = str(uuid5(NAMESPACE_URL, f"predikpedia:response:{study.id}:{identities[pid]}:{phase}:{index}:{repetition}"))
        attributes = dict(estudio_id=study.id, persona_id=pid, perfil=persona.get("perfil") or "General",
                          repeticion=repetition, pregunta=question, contexto=study.contexto,
                          response_id=response_id, identity_id=identities[pid], phase=phase,
                          round_number=round_number, question_index=index,
                          evidence_refs=[item["case_ref"] for item in evidence[pid]],
                          memory_refs=[item["id"] for item in local_history],
                          exposure_ids=[item["response_id"] for item in peers])
        try:
            if phase == "after_interaction" and (pid not in baseline or not peers):
                raise LLMError("No hay respuesta inicial y opiniones válidas de vecinos para esta ronda.")
            system = build_system_prompt(persona, study.contexto, evidence=evidence[pid], memory=local_history,
                                         exposure=peers, mode=study.mode)
            raw = engine.generate(system_prompt=system, user_prompt=build_user_prompt(question), agent_id=pid, expect_json=True)
            result = parse_study_response(raw)
            text = redact_contacts(result.pop("response_text"))
            # Contacts generated by a model never become portable results or future memory.
            for key in ("quote", "main_objection", "main_driver"):
                result[key] = redact_contacts(result[key])
            if result["quote"] not in text:
                result["quote"] = text[:120]
            metadata = engine.get_request_metadata() if hasattr(engine, "get_request_metadata") else {}
            if not isinstance(metadata, dict):
                metadata = {}
            metadata = {key: metadata[key] for key in ("provider", "model", "mode", "scheduled_provider", "fallback_used") if key in metadata}
            answer = RespuestaEstudio(**attributes, respuesta=text, sintesis=text[:180], llm_metadata=metadata, **result)
        except LLMError:
            # Exception strings can contain request data; persist a generic failure.
            answer = RespuestaEstudio(**attributes, respuesta="[ERROR: El participante no devolvió una respuesta válida]", sintesis="Error de LLM",
                                      error="El participante no devolvió una respuesta válida")
        if store:
            store.checkpoint(answer.to_dict(), remember=study.memory_enabled and study.mode != "survey")
        answers.append(answer)
        if on_response:
            on_response(answer, len(answers), planned_tasks(study, len(personas)))
        return answer

    for persona in personas:
        pid = persona["persona_id"]
        local_history = list(history[pid])
        questions = [study.pregunta, *study.follow_up_questions] if study.mode == "interview" else [study.pregunta] * (study.respuestas_por_persona if study.mode == "survey" else 1)
        for index, question in enumerate(questions, 1):
            answer = respond(persona, question, index if study.mode == "interview" else 1,
                             index if study.mode == "survey" else 1, "interview" if study.mode == "interview" else "individual",
                             1, local_history, [])
            if stopped:
                break
            if not answer.respuesta.startswith("[ERROR:"):
                if study.mode == "interview":
                    local_history.append({"id": answer.response_id, "kind": "simulated_interview",
                                          "question": question, "response": answer.respuesta, "origin": "synthetic_output_not_source_fact"})
                elif study.mode == "social":
                    baseline[pid] = answer
        if stopped:
            break
    if study.mode == "social" and not stopped:
        for persona in personas:
            pid = persona["persona_id"]
            own = baseline.get(pid)
            own_history = list(history[pid])
            if own:
                own_history.append({"id": own.response_id, "kind": "individual_baseline", "question": study.pregunta,
                                    "response": own.respuesta, "origin": "synthetic_output_not_source_fact"})
            peers = [{"persona_id": peer, "response_id": baseline[peer].response_id, "response": baseline[peer].respuesta[:800],
                      "origin": "synthetic_peer_opinion_not_source_fact"}
                     for peer in study.interaction_graph[pid] if peer in baseline]
            respond(persona, study.pregunta, 1, 1, "after_interaction", 2, own_history, peers)
            if stopped:
                break
    return answers
