# Predikpedia: fiabilidad, aprendizaje con datos reales y contexto (roadmap)

> Etapa 0 (arreglar lo roto y simplificar el flujo) ya está implementada. De la Fase 2, la población desde datos reales también (Audiencias → "Subir datos reales"). En el modo "Describir con palabras", la IA ahora escribe arquetipos (personas completas y coherentes) por grupo en vez de listas sueltas de valores, y el % de cada grupo se puede corregir en Revisar. Fase 1 y el resto de las Fases 2 y 3 siguen pendientes.

## Context

Querés saber si la app puede aprender de resultados reales que ya tenés, hasta qué punto más contexto mejora las predicciones y qué hace falta para que los resultados sean fiables. Abajo va primero la respuesta (cómo funciona hoy, sacada del código) y después un plan para agregar un circuito de validación y aprendizaje.

---

## 1. Cómo funciona hoy (de punta a punta)

1. **Audiencia → segmentos** (`app/services/audience_design_service.py`): una sola llamada al LLM convierte tu brief en 2 a 6 segmentos con un % cada uno y, por atributo, una lista de 3 a 8 valores posibles (edad, rol, industria, dolor, motivador, objeción, sensibilidad al precio, comportamiento y canal).
2. **Expansión en personas** (`app/services/universe_service.py:_build_persona`): para cada persona se **sortea cada atributo por separado**, con semilla fija. No hay ningún dato real detrás; las combinaciones salen al azar (por ejemplo, "18-25 + Decisor + sensibilidad Baja" puede salir aunque no tenga sentido).
3. **Estudio** (`app/pages/estudios.py:_execute_study`): por cada persona se hace 1 llamada al LLM. El prompt lleva un perfil de unas 10 líneas cortas, el "contexto" que escribiste y la pregunta, y la respuesta vuelve en JSON (texto, sentiment, intent, objeción, driver, confidence). No se fija `temperature` y las preguntas son siempre abiertas.
4. **Análisis** (`app/services/analysis_service.py`): conteo de palabras clave, regex para separar "objeciones" de "oportunidades" y las respuestas más largas como destacadas. No es estadística.

**Lo que existe pero no se usa:** `app/domain/coherence_engine.py` (filtro de sinceridad por NSE y umbral de escepticismo) y las reglas de `methodology_v1.md` no están conectados al flujo actual. `Results_Opinaia_1500.csv` tampoco se usa en ningún lado.

## 2. ¿Puede aprender de resultados reales?

**Hoy no.** Cada estudio arranca de cero: el modelo no se reentrena, los resultados guardados nunca vuelven a entrar en un prompt y no hay ningún lugar donde cargar un resultado real para comparar. Lo que sale es lo que el LLM "imagina" de cada estereotipo.

Una app así puede "aprender" de 4 maneras, de menor a mayor esfuerzo:

| Mecanismo | Qué hace | Datos que pide |
|---|---|---|
| **A. Medir** (benchmark) | Corre la simulación sobre un estudio cuyo resultado real ya conocés y calcula el error | 1 estudio real con su distribución de respuestas |
| **B. Población real** | Arma las personas con filas reales (microdatos de una encuesta) en vez de sortear atributos | Un CSV por respondente (como el de Opinaia) |
| **C. Anclaje (few-shot o RAG)** | Mete en el prompt respuestas reales de personas parecidas | Respuestas reales abiertas o cerradas por segmento |
| **D. Corrección aprendida** | Usa el sesgo medido en estudios pasados (por ejemplo, "la simulación sobreestima la aceptación +15 pts en NSE D/E") para corregir los estudios nuevos | Varios benchmarks acumulados |
| E. Fine-tuning | Reentrena un modelo, por ejemplo el de Ollama con LoRA | Miles de respuestas reales; es el último paso |

**A va primero: sin medir no hay forma de saber si algo mejora.**

## 3. ¿Cuánto contexto hace falta?

Tu intuición va bien encaminada, con un matiz: **lo que ayuda es el contexto que cambia la decisión, no la cantidad de texto.**

- **Ayuda mucho:**
  - Datos duros de la situación: precio en moneda local, ingreso típico, alternativas que ya usan y momento (inflación, elecciones).
  - Que la composición de la población sea correcta, incluidas las combinaciones de atributos.
  - Ejemplos reales de cómo responde ese segmento.
- **Ayuda poco o empeora:** biografías largas inventadas, adjetivos de personalidad o reglas de "actuá crudo". Suelen meter más estereotipo y menos varianza real. Los LLM tienden a ser complacientes, a homogeneizar respuestas y a caricaturizar segmentos.
- **El punto de rendimientos decrecientes no se puede adivinar: se mide.** Con un estudio real de referencia se corre la misma pregunta en niveles crecientes de contexto:
  - **L0:** solo el segmento.
  - **L1:** + atributos.
  - **L2:** + ficha de situación con datos duros.
  - **L3:** + población desde microdatos reales.
  - **L4:** + ejemplos reales.

  Para cada nivel se mide la distancia contra el resultado real y, donde la curva se aplana, ahí está "cuánto contexto es suficiente" para ese tipo de pregunta.

**Requisito para todo esto:** el resultado real tiene que ser comparable. Con pregunta cerrada y opciones (por ejemplo, "¿A quién votarías? A/B/C" o "¿Comprarías a $X? Sí/No/Tal vez") se puede medir el error en puntos porcentuales. Con respuesta abierta solo se puede comparar de forma cualitativa.

---

## 4. Plan de implementación propuesto

**Orden:** primero que la app funcione y se entienda (Etapa 0); después medir y aprender (Fases 1 a 3). No tiene sentido calibrar resultados que el usuario no logra generar o leer.

### Etapa 0: Arreglar lo roto y simplificar el flujo (va primero)

Problemas concretos encontrados en el código:

| # | Problema | Dónde | Efecto |
|---|---|---|---|
| 1 | El botón "Ir a Estudios →" se crea **dentro** del handler de "Guardar audiencia" | `app/pages/audiencias.py:266` | Al hacer click, Streamlit recarga, el botón ya no existe y no pasa nada |
| 2 | Mismo problema con "Ver resultados →", que vive dentro del handler de "Ejecutar estudio" | `app/pages/estudios.py:385` | El usuario termina el estudio y queda trabado |
| 3 | El botón "⛔ Detener" dentro del loop dispara una recarga que **mata la ejecución**, y las respuestas recién se guardan al final | `app/pages/estudios.py:280-371` | Detener = perder todo. Queda un estudio guardado sin resultados |
| 4 | Errores del LLM se guardan como respuestas `"[ERROR: ...]"` | `estudios.py:355` | Ensucian el análisis y los conteos |
| 5 | El sidebar muestra "API: Falta" si no hay clave de OpenRouter, aunque Ollama local esté andando; el inicio habla de "OpenRouter o Gemini" | `app/navigation.py`, `app/pages/home.py` | Mensajes contradictorios y desactualizados |
| 6 | Conceptos internos expuestos ("universo", "expansión", "RPP", "expansión reciente") | Audiencias, Estudios e Inicio | El usuario tiene que entender el sistema para usarlo |
| 7 | El estudio son 4 pasos con decisiones técnicas (personas a procesar, respuestas por persona) antes de ver valor | `estudios.py` | Demasiadas decisiones |
| 8 | Resultados son 4 pestañas (análisis, preguntas, comparar, biblioteca) con el análisis real escondido detrás de un botón "Analizar con IA" | `app/pages/resultados.py` | No queda claro qué mirar |

Cambios propuestos, alineados con `PLAN_REDISENO_TOTAL_PREDIKPEDIA.md` (§5 principios, §12 journey, Fases 2 a 4):

1. **Arreglar la navegación post-acción (bugs 1 y 2):** guardar en `session_state` un flag "acaba de guardar o terminar" y dibujar el botón siguiente fuera del handler, o navegar directo con `go_to_page` al terminar.
2. **Ejecución robusta (bugs 3 y 4):**
   - Guardar los resultados de forma incremental, cada N respuestas, con `save_study_results`.
   - Sacar el botón Detener del loop. Si el usuario recarga, lo ya respondido queda guardado.
   - Las respuestas con error se guardan aparte (marca `error`) y no cuentan en el análisis.
3. **Estado del modelo consistente (bug 5):** sidebar e inicio usan `LLMService().is_ready()` y `get_provider_label()`, y se borra el texto de Gemini.
4. **Flujo simplificado en 3 pasos visibles:** Audiencia → Pregunta → Resultados.
   - Audiencias: brief → "Generar" → vista previa → guardar. La expansión queda implícita y se guarda junto a la audiencia, sin usar esa palabra.
   - Estudios: elegir audiencia y escribir la pregunta en una sola pantalla. Tamaño de muestra y respuestas por persona van a "Opciones avanzadas" con defaults razonables.
   - Resultados: una pantalla principal con un resumen ejecutivo arriba (distribuciones de sentiment, intent y opción elegida, más las objeciones y drivers principales) y el detalle debajo. Comparar y descargas pasan a secundarios.
5. **Lenguaje para no técnicos:** reemplazar "universo/expansión/RPP" por "audiencia/personas/respuestas" en toda la UI, sin renombrar campos JSON (ver `AGENTS.md`).

Etapa 0 no toca modelos de datos, salvo el campo opcional de error, así que los datos guardados siguen cargando.

### Supuesto para las Fases 1 a 3

Supuesto: tus resultados reales son tipo encuesta (pregunta cerrada + % por opción, idealmente con microdatos por respondente como `Results_Opinaia_1500.csv`). Si son otra cosa (ventas reales, tasas de conversión), cambian las fases 1 y 2.

### Fase 1: Medir (benchmark y preguntas cerradas)
- **Preguntas cerradas en Estudios:**
  - Agregar un campo opcional `opciones: List[str]` a `Estudio`, con default vacío para no romper el JSON guardado.
  - Agregar el campo `opcion_elegida` a `RespuestaEstudio`.
  - En `app/pages/estudios.py`, `_build_user_prompt` pide elegir una opción cuando la lista existe.
  - Fijar una `temperature` explícita en `LLMService.generate` (parámetro opcional).
- **Nuevo modelo `Benchmark`** en `app/domain/models.py`: pregunta, opciones, distribución real total y por segmento, n, fuente y fecha. Se guarda en `storage/repository.py` igual que los estudios, en `benchmarks/*.json`.
- **Nuevo `app/services/calibration_service.py`:**
  - Distribución simulada vs. real.
  - Error absoluto medio en puntos porcentuales y distancia de variación total, total y por segmento.
  - Margen de error esperable dado el n real.
- **UI:** una pestaña "Validación" en `app/pages/resultados.py` para cargar el resultado real (CSV o manual) y ver la comparación. Va dentro del shell actual, alineado con `PLAN_REDISENO_TOTAL_PREDIKPEDIA.md`.
- **Script `tools/run_context_ablation.py`:** corre un benchmark en los niveles L0 a L4 y deja un reporte. Es lo que responde "cuánto contexto".

### Fase 2: Anclar en datos reales
- **Importar población desde microdatos** (en `app/services/universe_service.py`): `expand_from_rows(csv)` crea una `PersonaSintetica` por fila (o remuestrea filas), de modo que se respeta la distribución conjunta real en vez del sorteo independiente.
- **"Ficha de situación" estructurada** en el estudio: precio, moneda, alternativas y coyuntura. Se inyecta en el system prompt.
- **Anclaje opcional:** k respuestas reales del mismo segmento como ejemplos en el prompt.
- **Conectar `CoherenceEngine.build_sincerity_filter_prompt`** cuando la persona tenga NSE. Medir con el benchmark si suma o resta antes de dejarlo activo.

### Fase 3: Corrección aprendida
- Con 3 o más benchmarks, estimar el sesgo por segmento y opción y ofrecer "resultado corregido" junto al bruto, siempre mostrando los dos.

### Archivos clave
- `app/domain/models.py`: campos nuevos opcionales y `Benchmark`.
- `app/pages/estudios.py` y `app/pages/resultados.py`.
- `app/services/llm_service.py`: temperature.
- `app/services/universe_service.py`: importar desde filas.
- `app/services/calibration_service.py` y `tools/run_context_ablation.py`: nuevos.
- `app/storage/repository.py`: CRUD de benchmarks.

## 5. Verificación

**Etapa 0:**
- Con Playwright y Chromium preinstalado, smoke headless del recorrido completo con un LLM simulado o Ollama: crear audiencia → "Ir a Estudios" navega → ejecutar → "Ver resultados" navega → aparece el resumen.
- Recargar a mitad de un estudio y comprobar que las respuestas parciales quedan guardadas.
- Con solo Ollama configurado, el sidebar dice "listo".

**Fases 1 a 3:**
- Tests con `unittest` en `tests/`:
  - `test_calibration.py`: métricas con distribuciones conocidas.
  - `test_population_import.py`: el CSV respeta las marginales.
  - Que los JSON viejos sigan cargando (compatibilidad de `from_dict`).
- `python -m unittest discover -s tests` y `py_compile` de los archivos tocados.
- Smoke headless de Streamlit en el puerto 8510: crear un estudio cerrado, cargar un benchmark y ver la pestaña Validación.
- Prueba real: correr la ablación con un estudio tuyo de resultado conocido y revisar el reporte de error por nivel de contexto.
