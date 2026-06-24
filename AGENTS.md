# AGENTS.md

## Entrypoints reales

- La app principal es `predikpedia.py`; ejecutala con Streamlit, no con `python predikpedia.py`.
- `main.py` es un flujo CLI viejo de simulacion/demo y no refleja la app actual.
- `ui_universos.py` contiene el flujo de audiencias/universos dentro de la app Streamlit.
- `engine_universos.py` es el puente entre `Universo`/`PerfilCliente` y el flujo viejo basado en filas `Agent_ID`/`Backstory`.
- `README.md` esta desactualizado para la app real; para comportamiento actual confia en `predikpedia.py`, `ui_universos.py`, `app_paths.py` y `storage_universos.py`.

## Comandos verificados

- Usar el venv del repo en Windows PowerShell:
  - `& ".\.venv\Scripts\streamlit.exe" run "predikpedia.py"`
  - `& ".\.venv\Scripts\python.exe" -m py_compile "predikpedia.py" "ui_universos.py" "engine_llm.py" "storage_universos.py" "app_paths.py"`
- Smoke start headless de la UI:
  - `& ".\.venv\Scripts\streamlit.exe" run "predikpedia.py" --server.headless true --server.port 8510`

## Dependencias y entorno

- El repo trae `.venv/` versionado; excluilo de busquedas y ediciones porque contamina `glob`/`grep` con miles de resultados.
- `requirements.txt` es incompleto para la app real: el codigo tambien importa `streamlit`, `pandas`, `plotly` y `google.generativeai`.
- `engine_llm.py` hace `load_dotenv()` al importar y selecciona proveedor por prefijo de clave:
  - `OPENROUTER_API_KEY` si empieza con `sk-or`
  - `GEMINI_API_KEY` si empieza con `AIza`
- En la sidebar actual, una sola entrada de API se copia a ambas variables; si el proveedor "cambia solo", revisa el prefijo de la clave antes de tocar logica.
- El repo sigue usando `google.generativeai`; al importar vas a ver un warning de deprecacion.

## Persistencia y rutas que sorprenden

- Importar `predikpedia.py` o `storage_universos.py` crea directorios en `c:/MiroModi/...` mediante `ensure_legacy_runtime_dirs()`.
- La persistencia principal no vive solo en el repo:
  - universos: `c:/MiroModi/Archivo Predikpédico/universos`
  - expansiones: `c:/MiroModi/Archivo Predikpédico/universos/expansiones`
  - estudios: `c:/MiroModi/Archivo Predikpédico/estudios`
  - resultados: `c:/MiroModi/Archivo Predikpédico/resultados`
  - checkpoints: `c:/MiroModi/Archivo Predikpédico/checkpoints`
  - ledger de creditos: `c:/MiroModi/Archivo Predikpédico/credits_ledger.json`
- La biblioteca de universos escanea tanto rutas legacy como carpetas locales del repo (`backend/uploads/simulations`, `Archivo Predikpédico`, `Projects`, raiz). No asumas que los datos de prueba estan en un solo lugar.
- `models_universos.py` serializa directo a JSON; cambiar nombres de campos rompe compatibilidad con datos ya guardados.

## Hotspots de arquitectura

- `predikpedia.py` es monolitico: shell visual, CSS, sidebar, simulacion OASIS, resultados, creditos y metodologia viven ahi.
- `ui_universos.py` tambien es monolitico: creacion de universos, expansion, ejecucion de estudios y lectura historica.
- Antes de hacer cambios grandes de UI/UX, lee ambos archivos completos; muchos comportamientos dependen del orden de render y de `st.session_state` disperso.
- `credits_engine.py` tambien escribe fuera del repo y usa rutas hardcodeadas; no lo trates como modulo aislado de UI.
- `engine_llm.py` devuelve errores del proveedor como strings de respuesta; no supongas que toda respuesta string es un resultado valido del modelo.

## Roadmap vigente

- `PLAN_REDISENO_TOTAL_PREDIKPEDIA.md` es el documento maestro del rediseño vigente.
- Si vas a tocar navegacion, shell visual, layout, jerarquia de pantallas o UX principal, leelo antes de editar.
- No hagas tweaks cosmeticos aislados en UI que contradigan ese plan; prioriza cambios alineados con el rediseño total.

## Verificacion y limites actuales

- No se encontraron CI, workflows, linter, formatter, typecheck ni suite automatizada del proyecto.
- Verifica cambios con smoke tests puntuales; no asumas que existe `pytest` util para este repo.
- `test_connection.py` no es una smoke test confiable por defecto en Windows PowerShell: imprime emoji (puede fallar por `cp1252`) y asume que `InferenceEngine.api_key` existe.
