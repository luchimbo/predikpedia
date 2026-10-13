# Audiencias con evidencia pública

Implementación local del recorrido **pregunta → búsqueda → diagnóstico → audiencia → estudio → resultados**, alineada con el plan maestro de rediseño (secciones 5, 12–16 y continuidad de realismo).

## Abrir el recorrido

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\scripts\start_private_app.ps1"
```

Desde Inicio o Estudios, elegí **Preparar con evidencia pública**. Se requiere un servidor vinculado a `127.0.0.1`, `localhost` o `::1`, sin `?uid=`. El portal y Render no habilitan este almacenamiento privado.

Completá pregunta, público y región. Para una propuesta específica, agregá el material exacto y las condiciones indispensables (precio y moneda cuando se pregunta por compra). En opciones avanzadas podés definir pregunta cerrada, escenario histórico y fuentes reservadas para validación.

## Ollama y búsqueda

El nuevo recorrido usa `LLMService(local_only=True)` tanto al investigar y crear perfiles como al ejecutar estudios. Ignora el proveedor programado y **nunca hace fallback a OpenRouter**. El router habitual de otros estudios sigue funcionando como antes. Cada respuesta local conserva el límite total de 60 segundos.

Configurá en `.env` el endpoint y un modelo de **texto/chat instalado**:

```dotenv
LLM_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LLM_LOCAL_MODEL=nombre-del-modelo-de-texto-instalado
LLM_LOCAL_API_KEY=ollama
```

Podés consultar los modelos con `ollama list`. Un modelo de embeddings no sirve para generar perfiles ni respuestas. También puede usarse otro equipo con Ollama mediante su endpoint compatible con OpenAI. No hace falta configurar una clave de OpenRouter para este flujo.

La biblioteca `ddgs` consulta DuckDuckGo y, si falla, Bing. No requiere API paga; sí conexión a internet. Los buscadores reciben las consultas. Las páginas recuperadas se interpretan con `trafilatura`; los PDF con texto, con `pypdf`. No hay OCR ni extracción detrás de login. Se rechazan enlaces con credenciales, direcciones privadas y puertos ajenos a HTTP/HTTPS, también en redirecciones.

Límites por preparación, configurables mediante entorno:

| Variable | Inicial |
|---|---:|
| `RESEARCH_MAX_ROUNDS` | 2 |
| `RESEARCH_MAX_QUERIES` | 8 |
| `RESEARCH_MAX_DOCUMENTS` | 20 |

Cada solicitud de búsqueda o descarga usa timeout de 15 segundos; cada documento admite hasta 5 MB, 150.000 caracteres de texto y 100 páginas en PDF. Un documento que supera el límite no se aprueba como una lectura completa. Son límites operativos, no una medida de calidad. Los bloqueos y documentos inaccesibles quedan registrados. Al alcanzarlos, agregá enlaces dentro del cupo o reformulá el alcance; no hay búsqueda infinita.

## Qué aprueba el diagnóstico

Ollama propone entre dos y seis aspectos y distingue centrales de secundarios. Para porcentajes se agrega un aspecto central obligatorio de composición poblacional.

Las reglas del servicio de calidad verifican que:

- La fuente fue leída y el fragmento citado está en el texto recuperado.
- Hay fragmentos que acreditan público y región. La correspondencia lexical es conservadora: puede rechazar formulaciones equivalentes; el usuario puede inspeccionar las citas y añadir otra fuente.
- La clasificación y el alcance no convierten una aproximación en un dato directo.
- La fecha está respaldada, es compatible con el escenario y cumple la vigencia del aspecto cuando corresponde.
- El origen y método citados existen. Se requiere un origen con método documentado o corroboración de orígenes y contenidos distintos; copias no agregan evidencia independiente.
- No hay contradicciones centrales ni vacíos de cobertura reportados en la revisión.
- Las proporciones tienen población, método y ponderación identificables. Los porcentajes de los grupos deben aparecer explícitamente en las citas y cubrir el 100% del público; no se normalizan porcentajes incompletos para aparentar cobertura.

Los estados son **Suficiente para explorar**, **Alcance limitado** e **Insuficiente**. Solo el primero permite crear o reutilizar una audiencia. El alcance limitado propone una reformulación, pero no habilita el botón hasta reevaluarla. Un aspecto secundario puede seguir desconocido y se conserva como tal.

Estos controles evalúan trazabilidad y pertinencia; no certifican la veracidad de una publicación, representatividad del público ni precisión predictiva. No hay puntaje global de confianza. El control de fragmentos no sustituye una revisión semántica humana.

## Audiencias y participantes

Los atributos generados requieren referencias a hallazgos aprobados y correspondencia lexical con sus citas. Los detalles sin respaldo se reemplazan por `No especificado`. Los nombres de grupos y arquetipos sin respaldo usan etiquetas neutrales. Si el diseño queda sin atributos sustentados, falla y conserva el expediente: no hay fallback a personas genéricas.

En exploración, grupos y arquetipos usan pesos iguales, identificados como decisiones de simulación. En estimación de proporciones, los grupos requieren porcentajes documentados; los pesos internos de arquetipos siguen siendo decisiones de simulación. Las combinaciones de atributos no equivalen a microdatos observados.

El perfil recibe únicamente evidencia vinculada a sus atributos (hasta seis hallazgos relevantes), diferenciada de experiencias personales. La investigación completa no se muestra a todos los participantes. El estímulo es el material y las condiciones que aportó el usuario. Antes de ejecutar se comprueba que las personas conserven sus atributos y contexto fundamentados, y se congela la muestra efectiva con las referencias recibidas. Las respuestas quedan asociadas a esas referencias.

El nuevo estudio se prepara como encuesta independiente, una respuesta por participante y memoria desactivada. La audiencia inicia con 50 personas y admite hasta 1000, sin ejecutar ese experimento automáticamente.

## Persistencia y versiones

Los expedientes, documentos y snapshots viven en la misma SQLite privada por usuario que la evidencia y memoria existentes: `PREDIKPEDIA_PRIVATE_DIR` o `~/.predikpedia/private/<hash_usuario>/evidence.sqlite3`. No se agregan documentos descargados al `data/` versionado.

Se guardan checkpoints por etapa, búsqueda y documento analizado. Un rerun normal no ejecuta búsquedas. Reintentar análisis no vuelve a analizar documentos ya completados. Las búsquedas terminadas conservan sus URLs para retomar una lectura interrumpida. Los documentos leídos se reutilizan con una ventana de caché de hasta 30 días, reducida según la vigencia exigida, y sus hallazgos se reevaluan por brief.

Cambiar pregunta, público, región, estímulo, fecha, opciones u objetivo crea una nueva preparación, dejando disponible la anterior. Revisar fuentes de una preparación que ya creó una audiencia también crea una versión nueva. Los snapshots congelados contienen documentos, diagnóstico, supuestos y procedencia de los atributos.

Los campos opcionales `Universo.research_snapshot_id`, `Estudio.research_snapshot_id` y `Estudio.local_only` conservan compatibilidad con JSON viejos. Al ejecutar se comprueba que pregunta, opciones y estímulo coincidan con el expediente aprobado. Reutilizar otra audiencia exige igual público, región y objetivo de composición, perfiles iguales al snapshot original y respaldo vigente de atributos y porcentajes, sin cambiar sus personas o identidades. Los informes opcionales con IA de estos estudios también usan solo Ollama.

## Resultados y validación

Resultados muestra el fundamento de la audiencia y permite descargar fuentes, diagnóstico y expediente congelado. La comparación contra encuestas reales sigue en Validación.

Las URLs reservadas como referencia de evaluación se omiten de la búsqueda y del diagnóstico. Una comparación contra una fuente que coincide con una URL o título utilizado se bloquea. El control depende de identificar la fuente: versiones distintas, nombres ambiguos o documentos que reproducen otro estudio requieren revisión manual. Una referencia usada para construir perfiles no constituye una evaluación independiente.

La evaluación futura debe comparar el flujo anterior y el nuevo con pregunta, muestra y modelo iguales, usando datos reales excluidos de la construcción. Esta implementación no ejecuta las 1000 respuestas ni reentrena modelos.

## Verificación

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests
& ".\.venv\Scripts\python.exe" -m pip check
```

`tests/test_public_research.py` verifica citas, fechas, cobertura, independencia, límites, recuperación, exclusión de benchmarks, compatibilidad, generación sin fallback, identidad, ejecución local y recorrido Streamlit con proveedores simulados. Las consultas y lecturas reales se verifican por separado, sin depender de ellas en la suite.
