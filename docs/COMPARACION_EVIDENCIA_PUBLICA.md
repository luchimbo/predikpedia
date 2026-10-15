# Flujo anterior contra evidencia pública

## Protocolo (congelado el 13 de octubre de 2026, antes de buscar o consultar al modelo)

Pregunta: ¿una audiencia armada con evidencia pública se acerca más a una encuesta real que una audiencia
armada solo con la descripción del público?

- **Benchmark:** ICG UTDT, septiembre 2026 (`bench_icg_2026_09_20261006_122319`), pregunta de evaluación del
  gobierno con seis opciones. Es el que tiene más referencias previas con el mismo modelo.
- **Igual en los dos brazos:** pregunta, opciones, contexto (`tools/contextos/argentina_2026_09.txt`), 200 personas,
  modo `probabilidades`, temperature 1, Qwen local (`qwen2.5:32b-predikpedia-ctx8192`), sin respaldo remoto.
  El texto que describe al público es el mismo: "Población adulta (18 años o más) de Argentina. Región: Argentina".
- **Brazo A, flujo anterior:** `design_segments` escribe grupos y arquetipos desde ese texto. Se arman **dos**
  audiencias independientes (A1 y A2) para ver cuánto varía el resultado solo por rediseñar la audiencia.
- **Brazo B, evidencia pública:** `PublicResearchService.prepare` con los límites por defecto (2 rondas, 8 búsquedas,
  20 documentos), objetivo "explorar", fecha del escenario 2026-08-31 y la página del ICG como fuente reservada.
  La audiencia se crea solo si el diagnóstico da "Suficiente para explorar". **Si no lo da, ese es el resultado**:
  no se relajan las reglas ni se agregan enlaces a mano para forzarlo.
- **Métrica:** promedio de las probabilidades por persona contra la distribución real: MAE total y saldo
  (Muy bien + Bien − Mal − Muy mal). No hay métrica por grupo: los grupos de cada audiencia son distintos entre sí
  y distintos de las zonas del benchmark.
- **Referencias ya medidas, misma pregunta y modelo:** personas reales de la encuesta (microdatos ICG) 8,88 pp;
  20% por opción sustantiva 6,67 pp. Saldo real −13,8.
- **Lectura fijada de antemano:** una diferencia de MAE menor a 3 pp entre A y B no se interpreta. Si A1 y A2
  difieren entre sí más que A contra B, el resultado es no concluyente.
- **Control de filtración:** después de preparar se revisan los documentos leídos buscando resultados del propio
  ICG de septiembre. Un documento sin fecha detectable puede pasar el filtro de fecha; si aparece, se informa.
- **Límites conocidos antes de correr:** una sola pregunta, política, donde el contexto ya trae los datos duros;
  un solo expediente para B; en modo explorar los grupos de B pesan igual por diseño.

Reproducir: `tools/compare_evidence_flows.py` (`prepare`, `old`, `new`). Resúmenes en `tools/experiments_log.jsonl`;
audiencias y respuestas en `data/privado/`, documentos web en la SQLite privada del usuario.

## Resultado (13 y 14 de octubre de 2026)

### Brazo B: no se pudo crear la audiencia

Expediente `7fc63d366933482ebd3a1e79be9c98c3`: 6 búsquedas, 20 documentos (16 leídos), 125 hallazgos extraídos y
**0 válidos**. Diagnóstico **Insuficiente**: los cinco aspectos centrales (inflación, economía, empleo, salarios y
opinión pública) quedaron como aproximados. Según el protocolo no se relajaron reglas ni se agregaron enlaces.

| Motivo de rechazo (un hallazgo puede tener varios) | Hallazgos |
|---|---:|
| La cita no acredita público y región | 125 |
| Publicación posterior a la fecha del escenario | 101 |
| El fragmento no aparece literal en el documento | 48 |
| Evidencia aproximada | 19 |
| Origen o método citado que no está en la fuente | 11 |

- **Público y región bloquea todo:** 15 hallazgos fallaron solo por eso. La regla pide una oración del documento que
  nombre al público con al menos la mitad de sus términos ("población", "adulta", "años", "Argentina"); las notas de
  inflación, empleo o salarios no describen así a quién se refieren. Para preguntas a la población general, esta
  regla impide construir audiencias aunque las fuentes sean pertinentes.
- **Fechas, en parte por el diseño de esta prueba:** el escenario se fijó al 31/08 para no filtrar el ICG, pero el
  contexto habla de septiembre y el modelo buscó "septiembre 2026". Trajo notas de septiembre y octubre.
- **Opinión pública:** no apareció ninguna fuente sobre la evaluación del gobierno; la revisión lo marcó como vacío central.
- **Filtración:** ningún documento leído menciona el ICG, la Di Tella ni la UTDT.
- **Operación:** la preparación se cortó tres veces por la máquina de Ollama (dos `segmentation fault` del proceso del
  modelo, que funcionaron al reintentar, y una respuesta de más de 60 s). Había reiniciado sola a las 19:54 UTC.
  Los checkpoints permitieron retomar sin repetir búsquedas ni análisis.

### Brazo A: dos audiencias del flujo anterior

| Corrida | Grupos que escribió la IA | Válidas | MAE (pp) | Saldo (pp) |
|---|---|---:|---:|---:|
| A1 `study_cmp_20261013_173535_59f5fc` | Jóvenes profesionales 50 · Maduros consolidados 50 | 200 | 9,11 | +6,5 |
| A2 `study_cmp_20261013_174737_80d379` | Adultos jóvenes 35 · Adultos establecidos 65 | 200 | 8,88 | +4,8 |
| Referencia: personas reales del ICG (6/10) | Zonas, microdatos | 199 | 8,88 | −3,7 |
| Referencia: 20% por opción sustantiva | — | — | 6,67 | 0,0 |
| **Real** | — | — | — | **−13,8** |

A2 se cortó en 180 filas (7 con error) al cerrarse la sesión y se completó con `--resume-study`, que conserva las
válidas y consulta solo a las faltantes y fallidas.

| Opción | Real | A1 | A2 | Personas reales |
|---|---:|---:|---:|---:|
| Muy bien | 9,0 | 10,7 | 11,0 | 10,4 |
| Bien | 22,9 | 23,9 | 23,0 | 20,8 |
| Regular | 22,4 | 36,6 | 35,8 | 33,0 |
| Mal | 10,9 | 20,7 | 21,1 | 24,7 |
| Muy mal | 34,7 | 7,4 | 8,1 | 10,2 |
| NS/NC | 0,1 | 0,8 | 1,1 | 1,0 |

### Lectura

1. **La comparación entre flujos no se pudo hacer:** con las reglas actuales el flujo de evidencia pública no
   construye una audiencia de población general para esta pregunta.
2. **Quién compone la audiencia casi no cambia el resultado.** Dos audiencias inventadas con grupos poco realistas
   ("jóvenes profesionales") dan el mismo error que 200 personas reales de la encuesta (8,9–9,1 pp) y casi la misma
   distribución. A1 y A2 difieren entre sí en 0,2 pp. Sin identidad política en el perfil, Qwen responde lo mismo
   para cualquier composición: el cuello de botella es el modelo, no la audiencia.
3. Ninguna variante le gana a repartir 20% por opción, y todas subestiman "Muy mal" (7–10% contra 35%).
4. Por lo tanto, en esta pregunta mejorar los perfiles con evidencia no tendría margen para mejorar la precisión
   salvo que la evidencia agregue identidad política o algo que el modelo efectivamente use.

## Segunda vuelta: flujo corregido (14 de octubre de 2026)

Después del resultado anterior se corrigió el flujo de evidencia pública (ver `docs/EVIDENCIA_PUBLICA.md`):

1. Público general: un dato de la región cuenta como dato del público; la región se acredita también por la
   cita principal o por la fuente. Un subgrupo sigue necesitando su propia cita.
2. Encuestas o mediciones de la propia pregunta no bloquean, ni como aspecto del plan ni como vacío de la revisión.
3. El análisis de cada fuente ya no recibe el contexto de los participantes: Qwen copiaba esas frases como si
   fueran citas del documento.
4. El diseño de la audiencia pide cada atributo como frase de una cita, con ids cortos (`h1`, `h2`…), y manda cada
   cita una sola vez. Antes el pedido llenaba el contexto de 8192 tokens, Ollama recortaba la instrucción y el
   modelo escribía perfiles genéricos sin vínculo con la evidencia.

**Cambio de protocolo, declarado:** la fecha del escenario pasó a ser la de hoy (14/10), como en un uso normal.
Con un escenario en el pasado el buscador solo trae lo más reciente y la regla de fechas rechaza casi todo.
Con la fecha de hoy entraron notas con la respuesta: tres con el resultado del ICG de septiembre y dos con otras
encuestas de aprobación del gobierno. Se excluyeron todas antes de crear la audiencia (función "Excluir fuentes"),
para que B no reciba la respuesta. B sí ve datos publicados después del trabajo de campo (por ejemplo la inflación
de septiembre), que A no tiene. Para conseguir respaldo de salarios se hizo una búsqueda enfocada con límites más
altos solo para esta corrida (3 rondas, 30 documentos).

Expediente `1a4b478267ba4814b30675f02e26f205`: **Suficiente para explorar**, 55 hallazgos válidos; inflación,
economía, empleo y salarios respaldados.

Audiencia creada (`universe_public_952af47a513d4479a8f8974db9c08f2a`): 2 grupos con nombre neutral ("Grupo 1" y
"Grupo 2", porque sus nombres no aparecían en las citas) y 4 arquetipos. Cada arquetipo tiene uno o dos atributos
respaldados; el resto queda "No especificado". Ejemplos: "El empleo formal cayó 0,2 puntos porcentuales" como
principal dolor, "El desempleo en Argentina subió al 7,9%" como objeción. Son hechos macro, no rasgos de personas.

| Corrida | Válidas | MAE (pp) | Saldo (pp) |
|---|---:|---:|---:|
| **B1 evidencia pública** `study_cmp_20261014_122956_186550` | 200 | **8,91** | −3,1 |
| A1 flujo anterior | 200 | 9,11 | +6,5 |
| A2 flujo anterior | 200 | 8,88 | +4,8 |
| Personas reales del ICG | 199 | 8,88 | −3,7 |
| 20% por opción sustantiva | — | 6,67 | 0,0 |
| **Real** | — | — | **−13,8** |

| Opción | Real | B1 | A1 | A2 |
|---|---:|---:|---:|---:|
| Muy bien | 9,0 | 11,2 | 10,7 | 11,0 |
| Bien | 22,9 | 20,5 | 23,9 | 23,0 |
| Regular | 22,4 | 32,3 | 36,6 | 35,8 |
| Mal | 10,9 | 24,4 | 20,7 | 21,1 |
| Muy mal | 34,7 | 10,4 | 7,4 | 8,1 |
| NS/NC | 0,1 | 1,4 | 0,8 | 1,1 |

### Lectura

1. **El flujo ya construye una audiencia de población general** a partir de la pregunta, sin recibir la respuesta.
2. **No mejora la precisión:** 8,91 pp contra 8,88–9,11 del flujo anterior, dentro del umbral de 3 pp que no se
   interpreta. Tampoco le gana a repartir 20% por opción.
3. El saldo de B queda más cerca del real (−3,1 contra +5/+6 de A), igual que con personas reales, pero sigue a
   10 pp y el MAE no cambia: es un desplazamiento de "Bien" a "Mal", no la recuperación de "Muy mal".
4. Los perfiles resultantes son hechos macro asignados como dolor u objeción, no personas. Con evidencia pública
   general (estadísticas nacionales) el flujo no tiene de dónde sacar rasgos individuales; sirve más como contexto
   compartido que como composición de la audiencia.
5. Sigue valiendo lo de la primera vuelta: en esta pregunta el resultado depende del modelo, no de la audiencia.
