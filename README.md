# Predikpedia

Plataforma de **research sintético**: armás audiencias de personas sintéticas (perfiles psicográficos densos generados por IA), les hacés preguntas de estudio y obtenés resultados analizados con resumen ejecutivo, KPIs, insights por perfil y citas destacadas. La idea es reemplazar o anticipar focus groups y encuestas tradicionales.

## Cómo está armado

```
Usuario ──► Portal Next.js (Vercel) ──login Supabase──► redirect ?uid=<user_id>
                                                          │
                                                          ▼
                                   App Streamlit (Render) — predikpedia.py
                                          │                    │
                                   Supabase Storage      Router LLM
                                   (datos por usuario)   (Ollama local / OpenRouter)
```

- **App principal (Streamlit):** `predikpedia.py` + paquete `app/`. Se despliega en Render (`render.yaml`).
- **Portal (Next.js 15 + Supabase Auth):** `app/page.tsx`, `app/login`, `app/register`, `app/dashboard`, `middleware.ts`. Autentica al usuario y lo redirige a la app Streamlit (`NEXT_PUBLIC_STREAMLIT_URL`) con su `uid`.
- **Persistencia:** Supabase Storage (`predikpedia-data/{user_id}/...`) si `SUPABASE_URL` está definido; si no, o si se abre Streamlit directo sin `uid`, usa el filesystem local en `data/<usuario>/` (por defecto `data/demo_user/`).

## Pantallas

| Pantalla | Qué hace |
|---|---|
| **Inicio** | Resumen de saldo, audiencias y estudios recientes. |
| **Audiencias** | Wizard de 3 pasos: definir la audiencia (nombre, descripción, cantidad), expandirla en personas sintéticas y revisarla antes de guardar. |
| **Estudios** | Wizard de 4 pasos: elegir audiencia, configurar pregunta y contexto, definir la muestra y revisar el costo antes de ejecutar. |
| **Resultados** | Resumen ejecutivo, KPIs, insights por perfil, quotes, comparación entre estudios, vista por pregunta y descargas. |
| **Configuración** | API key, carpeta de datos y opciones operativas. |

## Cómo funciona por dentro

El flujo tiene tres etapas: **crear una audiencia → correr un estudio → analizar los resultados**.

### 1. Audiencia (universo → personas sintéticas)

1. Definís un **universo**: nombre, descripción (quiénes son, contexto) y cantidad de personas.
2. Al tocar *Generar personas sintéticas* pasan dos cosas:
   - **Diseño de segmentos (1 llamada al LLM):** `audience_design_service.design_segments()` lee la descripción y devuelve de 1 a 4 segmentos (`PerfilCliente`) con su porcentaje, una descripción y, para cada atributo (rango de edad, rol, rubro, objetivo, dolor principal, motivador, objeción, sensibilidad al precio, comportamiento y canal), los valores que tienen sentido para ese segmento. Si el brief menciona segmentos o proporciones, los respeta.
   - **Expansión (sin LLM):** `universe_service.expand_universe()` reparte las personas según los porcentajes y a cada una le sortea atributos **dentro de los valores de su segmento**. El costo no depende de la cantidad de personas.
   - Si no hay modelo configurado, la llamada falla o se desmarca la opción de IA, se usa un perfil `General` con atributos genéricos (edad, rol, industria, etc. de listas fijas) y la descripción solo queda como contexto.
   - El azar usa como semilla el `id` del universo, así que expandir el mismo universo siempre da las mismas personas. Las audiencias guardadas antes de este cambio (sin `atributos`) siguen generando exactamente las mismas personas.
3. Al guardar, se persisten el universo (`universos/<id>.json`) y un snapshot de la expansión con todas las personas (`universos/expansiones/<id>_<fecha>.json`).

### 2. Estudio (una pregunta a cada persona)

1. Elegís una audiencia ya expandida, escribís título, **pregunta** y **contexto** (qué se les muestra o en qué situación están).
2. Configurás la muestra: cuántas personas usar (por defecto hasta 120) y cuántas respuestas por persona (1 a 5).
3. Al ejecutar, `estudios.py` recorre las personas **de a una, en secuencia**. Para cada una:
   - Arma un *system prompt* que le pide al modelo actuar como esa persona (perfil + atributos + contexto del estudio), responder en primera persona, con realismo y en un máximo de 150 palabras.
   - Envía la pregunta pidiendo un **JSON** con `response_text`, `sentiment`, `intent`, `main_objection`, `main_driver`, `confidence` y `quote`.
   - Guarda cada respuesta como `RespuestaEstudio`. Si el modelo falla, la registra como `[ERROR: ...]` y sigue con la siguiente.
4. Hay un botón para **detener** el estudio a mitad de camino; las respuestas obtenidas hasta ese momento se guardan igual.
5. Se persisten el estudio (`estudios/<id>.json`) y sus respuestas (`resultados/<id>.json`).

### 3. Resultados (análisis sin LLM)

`analysis_service.build_executive_report()` analiza las respuestas **con reglas y conteo de palabras**, sin llamar al modelo:

- **Temas clave:** las palabras más frecuentes de las respuestas (sin stopwords), en general y por perfil.
- **Insights por perfil:** temas dominantes y una respuesta de evidencia por perfil.
- **Objeciones y oportunidades:** respuestas que contienen patrones como "caro", "duda", "riesgo"… o "interesa", "valor", "necesito"….
- **KPIs y distribuciones:** a partir de los campos estructurados del JSON (sentimiento, intención, objeciones y drivers).
- **Próximas preguntas sugeridas** y un informe en Markdown descargable.

La página de Resultados también permite comparar estudios, ver todas las respuestas de una misma pregunta a lo largo de varias corridas y descargar los datos.

### Llamadas al LLM

Todas pasan por `LLMService.generate()`:

- En cada request, `llm_routing.resolve_provider()` decide si usar **Ollama local** u **OpenRouter** según `LLM_PROVIDER` y el horario.
- Cada proveedor se reintenta hasta 3 veces con espera exponencial (1 s, 2 s).
- Si estaba en horario local y Ollama falla, hace **fallback automático a OpenRouter**.
- La respuesta se parsea como JSON (también si viene envuelta en un bloque ` ```json `); si no se puede parsear, se usa el texto crudo.

### Créditos

`credits_service.py` tiene el modelo de créditos pay-as-you-go (USD → Predik-Credits, costo por agente), pero **hoy está desactivado**: el saldo siempre es 999.999 y los estudios no descuentan nada.

### Código preparado pero sin usar

- `domain/templates.py` define templates de estudio (Exploratorio, Concept Test, Messaging Test, Pricing Test, Feature Feedback) con prompts y salidas propias, pero el wizard de Estudios usa un prompt genérico (`template="custom"`).
- `domain/coherence_engine.py` tiene filtros de "sinceridad" y escepticismo (para evitar que el modelo sea complaciente), pero ningún flujo lo invoca todavía.

## Estructura del código

```
predikpedia.py            Entrypoint Streamlit (init, sidebar, ruteo de páginas)
app/
  config.py               Rutas de datos (PREDIKPEDIA_DATA_DIR > settings.json > ./data)
  state.py                Estado central de st.session_state
  navigation.py           Sidebar y navegación
  theme.py                CSS global
  components/             Componentes visuales (shell)
  pages/                  Una página por pantalla
  domain/                 Modelos (Universo, PerfilCliente…), templates de estudio, coherence engine
  services/               LLM (router + cliente), expansión de universos, análisis, créditos
  storage/                Repositorio de universos/estudios/resultados (Supabase o local)
tools/                    Relay de Ollama, supervisor del túnel, generador de población TooMatch
scripts/                  Arranque del relay + Cloudflare Quick Tunnel (PowerShell)
templates/ollama-qwen38/  Plantilla para correr un cliente Qwen local con Ollama
config/                   Configuraciones de poblaciones (ej. TooMatch AR 25-45)
tests/                    Tests unitarios (unittest)
docs/                     Documentación operativa (rotación de LLM)
```

## Correr en local

Requisitos: Python 3.11+, y Node 18+ solo si vas a tocar el portal.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # completar las claves
.\.venv\Scripts\streamlit.exe run predikpedia.py
```

Al abrir Streamlit directo (sin `?uid=`), la app usa almacenamiento local en `data/demo_user/`. Para otro usuario local, definir `PREDIKPEDIA_DEFAULT_USER`.

Portal Next.js:

```powershell
npm install
npm run dev
```

Necesita `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` y `NEXT_PUBLIC_STREAMLIT_URL`.

## Variables de entorno

| Variable | Uso |
|---|---|
| `LLM_PROVIDER` | `schedule` (por defecto), `local` u `openrouter`. |
| `LLM_SCHEDULE_TIMEZONE`, `LLM_LOCAL_START`, `LLM_LOCAL_END` | Franja horaria en la que se usa el modelo local (por defecto 09:30–17:30, Buenos Aires). |
| `LLM_LOCAL_BASE_URL`, `LLM_LOCAL_MODEL`, `LLM_LOCAL_API_KEY` | Endpoint compatible con OpenAI de Ollama (directo en la LAN o vía relay/túnel). |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Proveedor fuera de la franja local (por defecto `google/gemini-2.5-flash-lite`). |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Persistencia remota. Sin ellas, se usa almacenamiento local. |
| `PREDIKPEDIA_DATA_DIR` | Carpeta de datos local (sobrescribe `settings.json`). |
| `PREDIKPEDIA_DEFAULT_USER` | Usuario local al abrir Streamlit sin `uid` (por defecto `demo_user`). |

Ver `.env.example` y `.env.relay.example`.

## Rotación de LLM (Ollama local ↔ OpenRouter)

Con `LLM_PROVIDER=schedule`, el proveedor se decide en cada request: dentro de la franja horaria se usa Ollama (`qwen2.5:32b`) y fuera de ella, OpenRouter. Para que Render llegue al Ollama local, se levanta un relay autenticado y un Cloudflare Quick Tunnel con:

```powershell
.\scripts\start_llm_relay_and_tunnel.ps1
```

El supervisor actualiza `LLM_LOCAL_BASE_URL` en Render cuando cambia la URL del túnel. El detalle está en [docs/LLM_ROTATION.md](docs/LLM_ROTATION.md).

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Deploy

- **App Streamlit:** Render, con la configuración de `render.yaml`. Las variables marcadas `sync: false` se cargan a mano en el panel de Render.
- **Portal:** Vercel (Next.js). Solo maneja login y redirección; no controla el router de LLM.

## Archivos legacy

`Projects/`, `Archivo Predikpédico/` y `outputs/` contienen datos y corridas de versiones anteriores (MiroModi). La app actual no los usa: la lógica vigente vive en `app/` y los datos, en `data/` o Supabase.
