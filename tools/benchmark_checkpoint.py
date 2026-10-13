"""Guardas de reanudación, sin acceso a red ni filesystem."""

from app.domain.models import Estudio, RespuestaEstudio


def prepare_resume(stored: Estudio, requested: Estudio, answers: list[RespuestaEstudio], personas: list[dict],
                   stored_manifest: dict, requested_manifest: dict, retry_errors: bool = False):
    fields = ("universo_id", "pregunta", "contexto", "opciones", "temperature", "modo_cerrada", "respuestas_planeadas")
    if any(getattr(stored, key) != getattr(requested, key) for key in fields):
        raise ValueError("La reanudación cambia pregunta, audiencia, contexto, opciones, temperature, modo o n.")
    if stored.mode != "survey" or stored.respuestas_por_persona != 1:
        raise ValueError("Solo se reanudan experimentos de encuesta con una respuesta por persona.")
    if stored_manifest != requested_manifest:
        raise ValueError("Cambió el prompt, la población, el benchmark o el modelo/proveedor desde el checkpoint.")
    wanted = {p["persona_id"] for p in personas}
    seen, saved = set(), []
    for answer in answers:
        if answer.persona_id not in wanted or answer.persona_id in seen or answer.estudio_id != stored.id:
            raise ValueError("El checkpoint tiene personas duplicadas, ajenas o de otro estudio.")
        seen.add(answer.persona_id)
        if not (retry_errors and answer.error):
            saved.append(answer)
    completed = {a.persona_id for a in saved}
    return saved, [p for p in personas if p["persona_id"] not in completed]
