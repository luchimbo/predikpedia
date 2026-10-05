# AGENTS.md

## Entrypoints reales

- La app principal es `predikpedia.py` + el paquete `app/`; ejecutala con Streamlit, no con `python predikpedia.py`.
- `predikpedia.py` solo inicializa (usuario, storage, estado, creditos, sidebar) y rutea a `app/pages/*`. La logica vive en `app/`.
- El portal Next.js (`app/*.tsx`, `app/login`, `app/register`, `app/dashboard`, `middleware.ts`, `lib/supabase`) convive en la misma carpeta `app/` que el paquete Python. Solo hace login con Supabase y redirige a Streamlit con `?uid=<user_id>` (`NEXT_PUBLIC_STREAMLIT_URL`).
- `README.md` describe la app actual.
- Los archivos legacy de MiroModi (`main.py`, `ui_universos.py`, `engine_*.py`, `core_logic.py`, `credits_engine.py`, `storage_universos.py`) ya no existen; su logica se migro a `app/`. `Projects/`, `Archivo Predikpédico/` y `outputs/` son datos viejos que la app no usa.

## Mapa del paquete `app/`

- `config.py`: rutas de datos. Prioridad: `PREDIKPEDIA_DATA_DIR` > `settings.json` en la raiz > `./data/`. `set_user()` cambia a `data/<user_id>/`.
- `state.py`: claves y defaults de `st.session_state`.
- `navigation.py`: sidebar y `NAV_OPTIONS` (Inicio, Audiencias, Estudios, Resultados, Configuracion).
- `pages/`: una pagina por pantalla. `audiencias.py` (wizard 2 pasos: describir y revisar), `estudios.py` (una sola pantalla; guarda respuestas incrementalmente y navega a Resultados), `resultados.py` (resumen del estudio arriba; preguntas, comparacion y descargas como vistas secundarias). `biblioteca.py`, `preguntas.py` y `reportes.py` son vistas auxiliares.
- `domain/`: `models.py` (`Universo`, `PerfilCliente`, etc.), `templates.py` (templates de estudio), `coherence_engine.py`.
- `services/`: `llm_routing.py` (eleccion de proveedor), `llm_service.py` (cliente LLM), `universe_service.py` (expansion de personas), `analysis_service.py`, `credits_service.py`.
- `storage/repository.py`: CRUD de universos, estudios y resultados. Usa Supabase si hay `SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_URL`; si no, filesystem local.

## Comandos verificados

- Usar el venv del repo en Windows PowerShell:
  - `& ".\.venv\Scripts\streamlit.exe" run "predikpedia.py"`
  - `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests`
  - `& ".\.venv\Scripts\python.exe" -m py_compile "predikpedia.py" "app\services\llm_service.py" "app\services\llm_routing.py"`
- Smoke start headless de la UI:
  - `& ".\.venv\Scripts\streamlit.exe" run "predikpedia.py" --server.headless true --server.port 8510`
- Portal: `npm install` y `npm run dev`.

## Dependencias y entorno

- El repo trae `.venv/` y `node_modules/` locales; excluilos de busquedas y ediciones porque contaminan `glob`/`grep`.
- `requirements.txt` no incluye `pandas`, aunque el codigo lo importa.
- El proveedor LLM ya no se elige por prefijo de clave. Lo decide `app/services/llm_routing.py` en cada request:
  - `LLM_PROVIDER=schedule` (default): Ollama local entre `LLM_LOCAL_START` (inclusive) y `LLM_LOCAL_END` (exclusiva) en `LLM_SCHEDULE_TIMEZONE`; OpenRouter fuera de esa franja.
  - `LLM_PROVIDER=local` u `openrouter` fuerzan el proveedor.
  - Local: `LLM_LOCAL_BASE_URL`, `LLM_LOCAL_MODEL`, `LLM_LOCAL_API_KEY`. OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
- Render llega al Ollama local con `tools/ollama_relay.py` + Cloudflare Quick Tunnel (`scripts/start_llm_relay_and_tunnel.ps1`, `tools/supervise_quick_tunnel.py`). Ver `docs/LLM_ROTATION.md`.
- Secretos locales: `.env` y `.env.relay.local`, ambos ignorados. Nunca commitear claves reales.

## Persistencia y rutas

- Al abrir Streamlit directo (sin `?uid=`), la app fuerza storage local con el usuario `PREDIKPEDIA_DEFAULT_USER` (default `demo_user`) y datos en `data/demo_user/`.
- Con `?uid=` desde el portal, usa Supabase Storage en `predikpedia-data/{user_id}/{universos,universos/expansiones,estudios,resultados}/*.json`.
- `data/<user_id>/` esta versionado en el repo.
- `app/domain/models.py` serializa directo a JSON; cambiar nombres de campos rompe compatibilidad con datos ya guardados (locales y en Supabase).

## Hotspots de arquitectura

- Muchos comportamientos dependen del orden de render y de `st.session_state`; revisa `app/state.py` y la pagina involucrada antes de tocar el flujo.
- Los wizards de Audiencias y Estudios guardan el paso actual y los inputs en session state; cuidado con keys de widgets que se pierden entre reruns.
- `llm_service.py` puede devolver errores del proveedor; no supongas que toda respuesta es un resultado valido del modelo.

## Roadmap vigente

- `PLAN_REDISENO_TOTAL_PREDIKPEDIA.md` es el documento maestro del rediseño vigente.
- Si vas a tocar navegacion, shell visual, layout, jerarquia de pantallas o UX principal, leelo antes de editar.
- No hagas tweaks cosmeticos aislados en UI que contradigan ese plan; prioriza cambios alineados con el rediseño total.

## Deploy y verificacion

- App Streamlit en Render (`render.yaml`); variables `sync: false` se cargan a mano en Render.
- Portal en Vercel; sus variables no controlan el router LLM.
- No hay CI, linter ni typecheck. La suite en `tests/` usa `unittest` (no `pytest`); complementala con smoke tests puntuales de la UI.
