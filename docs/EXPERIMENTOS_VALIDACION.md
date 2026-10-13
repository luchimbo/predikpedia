# Experimentos de validación (Fase 1)

Benchmark: **Índice de Confianza en el Gobierno (UTDT), ola septiembre 2026, n=1000, ponderado.**
Pregunta: evaluación de la gestión del gobierno nacional (Muy bien / Bien / Regular / Mal / Muy mal / NS-NC).
Audiencia: 200 personas sorteadas (con el peso UTDT) de los microdatos de la misma ola; grupo = zona; la respuesta
real queda fuera del perfil. Todas las corridas usan **las mismas 200 personas**.

Reproducir: `tools/prepare_icg_wave.py` (arma audiencia y benchmark) y `tools/run_benchmark_experiment.py`
(corre una variante). Cada corrida queda en `tools/experiments_log.jsonl` y en Resultados → Validación.

## Resultados (6 de octubre de 2026)

Error = promedio, por opción, de |simulado − real| en puntos porcentuales.
Referencias sin modelo: repartir parejo entre las 6 opciones = 10,0; 20% a cada una de las 5 sustantivas = 6,7.

| Corrida | Modelo | Respuestas válidas | Error (pp) |
|---|---|---|---|
| E0 línea de base (prompt original, sin contexto) | gemini-2.5-flash-lite | 198 | 23,5 |
| B1 prompt "tomá posición" | gemini-2.5-flash-lite | 200 | 22,2 |
| A1 contexto con datos duros + B1 | gemini-2.5-flash-lite | 199 | 22,7 |
| C1 + A1 + B1 | gpt-5.4-mini | 172 | 22,2 |
| C1 + A1 + B1 | deepseek-chat | 153 | 20,5 |
| C1 + A1 + B1 | claude-haiku-4.5 | 115 | 22,2 |
| C1 + A1 + B1 | gemini-3.5-flash | 60 | 17,8 |
| **B2 probabilidades + A1** | gemini-2.5-flash-lite | 197 | **10,9** |
| **B2 probabilidades + A1** | gpt-5.4-mini | 180 | **11,1** |
| **B2 probabilidades + A1** | gemini-3.5-flash | 81 | **8,3** |

Real: Muy bien 9,0 · Bien 22,9 · Regular 22,4 · Mal 10,9 · Muy mal 34,7 · NS/NC 0,1.

## Qué aprendimos

1. **Pedir una sola opción por persona colapsa la distribución.** Con cualquier modelo y cualquier prompt, casi
   todos eligen "Regular" o "Mal" y nadie elige los extremos. El modelo le da a cada perfil la respuesta *modal*
   y borra la dispersión real dentro del grupo (en la realidad, "Muy mal" es la respuesta más común).
2. **Pedirle al modelo la distribución del perfil y sortear (modo `probabilidades`) baja el error a la mitad**
   (de ~22 a 8–11 pp) en los tres modelos probados. Es el cambio que más movió la aguja.
3. **Cambiar el prompt de elección (B1), agregar contexto (A1) o cambiar de modelo, sin B2, casi no mueve nada.**
4. **Sesgo que queda:** "Muy mal" sale en ~10% contra 35% real; la simulación sigue siendo más moderada que la
   gente. El perfil no tiene identidad política, que es lo que más explica esta pregunta.
5. Ninguna variante supera todavía a "20% a cada opción" (6,7 pp). Es la vara a superar.

## Advertencias

- **Errores por saldo:** las corridas con muchas respuestas inválidas (gemini-3.5-flash, haiku) fallaron por falta de
  crédito en OpenRouter (error 402), no por formato. Con n chico el error es menos confiable (gemini-3.5-flash: 81).
- **Una sola ola y una sola pregunta.** Los ajustes se hicieron mirando septiembre 2026. Antes de dar por bueno un
  cambio hay que probarlo en la ola de control **enero 2025** (opinión opuesta: Muy bien + Bien = 50%), ya
  preparada (`universe_icg_2025_01_…`, `bench_icg_2025_01_…`, contexto `tools/contextos/argentina_2025_01.txt`,
  escrito antes de ver resultados). Pendiente por falta de saldo.
- El texto de `response_text` en modo probabilidades es de "una persona del perfil" y puede no coincidir con la
  opción sorteada; sirve para medir distribuciones, no para leer respuestas individuales.

## Ola de control: enero 2025

Mismo método (B2 + contexto con datos duros de ese mes, escrito antes de ver resultados), sin ningún ajuste.
Real: Muy bien 19,6 · Bien 30,3 · Regular 18,1 · Mal 11,9 · Muy mal 19,3 · NS/NC 0,9.

| Corrida | Modelo | Válidas | Error sep-2026 | Error ene-2025 |
|---|---|---|---|---|
| Elección única (B1) + A1 | gemini-2.5-flash-lite | 199 | 22,7 | 25,6 |
| B2 + A1 | gemini-2.5-flash-lite | 197 | 10,9 | 8,5 |
| B2 + A1 | gpt-5.4-mini | 200 | 11,1 | 10,4 |
| B2 + A1 | gemini-3.5-flash | 154 / 160 | 6,8 | 6,6 |
| *Referencia: 20% a cada opción sustantiva* | — | — | *6,7* | *3,7* |

**¿Capta el cambio de opinión?** Saldo neto (Muy bien + Bien − Mal − Muy mal), en puntos:

| | sep-2026 | ene-2025 | Cambio |
|---|---|---|---|
| **Real** | −13,7 | +18,7 | **+32,4** |
| gemini-3.5-flash | +6,4 | +11,2 | +4,8 |
| gemini-2.5-flash-lite | −15,2 | −4,6 | +10,6 |
| gpt-5.4-mini | −23,9 | −23,0 | +0,9 |

**Conclusión honesta:** B2 arregla el colapso y el error se mantiene fuera de la ola usada para ajustar, pero
**la simulación todavía no sirve para predecir**: devuelve casi la misma distribución "repartida" en los dos meses y
no capta el giro real de 32 puntos. Por eso su error es parecido o peor que el de no usar modelo (20% a cada opción).
El contexto con datos duros no alcanza para que el modelo traduzca la coyuntura en opinión. La métrica que importa
de acá en adelante es **el cambio entre olas**, no solo el error de una ola.

## Experimento D: identidad política (Latinobarómetro 2024, Argentina)

Benchmark: aprobación de la gestión del gobierno (Aprueba 38,8 · No aprueba 56,3 · NS/NC 4,9), n=1210, ago-sep 2024,
ponderado. 200 personas con demografía, ideología (0-10) y partido que votaría. Datos con licencia que prohíbe
redistribuir: se preparan con `tools/prepare_latinobarometro.py` y quedan en `data/privado/` (ignorado por git).

**El error total engaña.** Varias corridas dan 4-7 pp de error total y sin embargo no distinguen entre votantes:
aciertan el promedio por compensación. La prueba real es el % que aprueba **dentro de cada grupo político**:

| Partido que votaría (n) | Real | flash-lite elección | flash-lite B2 | gpt-5.4-mini solo demografía B2 | gpt-5.4-mini B2 | gpt-5.4-mini elección |
|---|---|---|---|---|---|---|
| La Libertad Avanza (45) | 93 | 13 | 40 | 33 | 77 | 100 |
| Peronismo (37) | 5 | 0 | 11 | 16 | 44 | 0 |
| Ninguno / no votaría (40) | 28 | 0 | 25 | 28 | 28 | 0 |
| No sabe / no contesta (52) | 29 | 0 | 33 | 33 | 33 | 0 |
| Error medio por persona (pp) | — | 36,2 | 16,6 | 18,2 | **12,7** | 18,7 |

(Todas con el ajuste B3 y contexto de ago-sep 2024, salvo donde se indica.)

1. **gemini-2.5-flash-lite no usa la identidad política**: con el contexto económico, hasta los votantes de LLA
   "no aprueban". Sin contexto los respeta más, pero igual queda lejos. Sirve para corridas baratas, no para esto.
2. **gpt-5.4-mini sí la usa.** En elección única acierta a los partidarios (LLA 100, peronistas 0) pero colapsa a
   los independientes (0% contra 28%). En modo probabilidades acierta a los independientes pero sus probabilidades son
   demasiado tibias para los partidarios (peronistas 44% contra 5%).
3. **B3** (los datos reales van como hechos sobre la persona, con la indicación de que la identidad pesa más que
   la coyuntura): mejora chica con flash-lite (17,3 → 16,6). Queda activo porque corrige un error de diseño (la
   política de realismo trataba los datos reales como hipótesis), pero la evidencia de mejora es débil.
4. Para validar con esta métrica en la app, la columna de identidad (partido) tiene que ser el **grupo** de la
   audiencia: así la pestaña Validación compara grupo por grupo.

Advertencia: entre corridas idénticas el error total varía ~3 pp (D0 dio 8,2 y 5,1). Diferencias menores a eso
no significan nada con n=200.

## Próximos pasos

1. ~~Ola de control enero 2025~~ (hecho: no capta el cambio).
2. A0 + B2 (sin contexto) para aislar cuánto aporta el contexto bajo B2.
3. ~~D: identidad política (Latinobarómetro)~~ (hecho: importa, pero solo si el modelo la usa).
4. Calibrar las probabilidades del modo B2 (son demasiado tibias): estimar un "afilado" en una ola y probarlo en otra.
   Es la Fase 3 del roadmap (corrección aprendida).
5. Repetir con el modelo local (qwen2.5:32b en 192.168.1.104) cuando esté prendido, para no gastar saldo.
6. Decidir si `probabilidades` pasa a ser el modo por defecto de las preguntas cerradas en la UI.

## Fase 3 experimental: afilado de probabilidades (6 de octubre de 2026)

Protocolo fijado antes de evaluar ICG con la corrección:

- Transformación **por persona**: `q_i = p_i^k / sum(p_j^k)`. No se potencia el promedio del grupo.
- Grilla fija: `k = 1, 1.25, 1.5, 2, 3, 4, 6, 8`. Selección por **MAE macro de grupos políticos**
  (cada grupo pesa igual), con desempate a favor del menor exponente. Se conserva `k=1` como candidato.
- Entrenamiento: Latinobarómetro 2024 Argentina, con identidad política y contexto ya escrito.
- Prueba: **ICG sep-2026 y ene-2025**, con sus contextos existentes. Se congela `k` antes de generar/evaluar
  las dos olas. Se informan error por grupo en entrenamiento y cambio de saldo entre olas en prueba.
- Comprobación recíproca, sin nuevas llamadas: estimar otro `k` **solo con ICG septiembre** usando la misma
  grilla y objetivo macro de grupos (zonas). Congelarlo antes de leer las métricas locales de enero y probarlo
  en enero y en Latinobarómetro. Permite informar grupos políticos fuera del entrenamiento de ese parámetro.
  No se elige entre ambos parámetros usando el resultado de prueba: son dos experimentos con fuentes de
  entrenamiento diferentes, reportados completos. Latinobarómetro ya fue observado; es validación retrospectiva.
- Un exponente entrenado con GPT no se transfiere a Qwen. La prueba local vuelve a generar las tres encuestas
  con los mismos pesos del modelo, prompt B2+B3 y temperature=1. No cambia el prompt mirando la prueba.
- Medición principal: **promedio de probabilidades declaradas**, sin ruido del sorteo. Las tablas previas usan
  elecciones sorteadas y no se comparan directamente con estas cifras. Se informan MAE total, MAE macro de
  grupos y MAE de grupos ponderado por el número de personas simuladas (no es error individual).
- En Latinobarómetro se une `persona_id` a la población guardada para recuperar `partido_que_votaria`:
  el `perfil` de las respuestas originales es región. El join incompleto aborta, no descarta personas en silencio.
- Los derivados y el parámetro congelado quedan en `.private/calibration/`, ignorado por git; el log compartido
  solo agrega resúmenes. Los archivos originales no se modifican.
- ICG es una **transferencia entre preguntas y escalas** (3 a 6 opciones), y un control histórico ya consultado,
  no una encuesta prospectiva ciega. Ninguna mejora habilita una corrección general en la UI.

Implementación: `app/services/probability_calibration_service.py` y `tools/calibrate_probabilities.py`,
con comandos separados `fit` / `evaluate`. La prueba rechaza el benchmark usado para estimar `k`
(incluso con otro ID si conserva fuente/fecha/pregunta), y también rechaza otro modelo.

### Entrenamiento exploratorio con GPT guardado (sin nuevas llamadas)

Corrida: `study_exp_20261006_132949_f783b3`, 198 respuestas válidas de 200; un error operativo en LLA y otro
en peronismo. **k elegido = 1.5**. Error macro de grupos: **10.06 → 6.75 pp**; ponderado por n simulado:
**10.16 → 6.57 pp**. Error total: 4.21 → 2.41 pp.

| Grupo (n válido) | Real % aprueba | B2 esperado | B2 esperado con k=1.5 |
|---|---:|---:|---:|
| La Libertad Avanza (44) | 93.34 | 66.95 | 78.17 |
| Peronismo (36) | 5.46 | 25.22 | 19.40 |
| Ninguno / no votaría (40) | 28.42 | 27.23 | 22.43 |
| No sabe / no contesta (52) | 29.07 | 29.94 | 26.49 |
| Juntos por el Cambio (7) | 46.79 | 31.43 | 27.15 |
| Izquierda (8) | 7.70 | 16.12 | 8.97 |
| Otro partido (4) | 24.36 | 31.75 | 27.88 |
| Voto en blanco o nulo (7) | 21.34 | 30.14 | 26.05 |

**No validado fuera de entrenamiento.** El afilado ayuda a los partidarios pero empeora la aprobación de
independientes y Juntos por el Cambio; peronismo sigue lejos. No se buscó otro parámetro mirando ICG.
Las probabilidades individuales GPT de las olas ICG no están en el workspace: sus promedios en el log no
permiten reconstruir `promedio(p^k)`. Por eso no se presenta una falsa prueba externa con esos promedios.

### Entorno de la nueva corrida local

SSH `pcmidi` respondió. Ollama ya estaba activo y ahora es accesible en `192.168.1.101:11434`
(también en `.116`; `.104` no respondió). `qwen2.5:32b` está instalado, cuantización Q4_K_M.
La prueba de 2 personas fue válida. Una tanda con contexto de 32k se interrumpió con 15 respuestas guardadas
porque el modelo quedó parcialmente fuera de GPU; figura como interrumpida en el log.

Se creó el alias `qwen2.5:32b-predikpedia-ctx8192` del mismo modelo, cambiando únicamente `num_ctx=8192`.
Ollama confirmó contexto 8192 y el modelo entero en VRAM. Ese mismo alias se usa para entrenamiento y prueba.
El runner fuerza `--provider local`, sin fallback OpenRouter, y guarda cada respuesta incrementalmente.
Saldo consultado antes de inferencia: US$2.147 de OpenRouter. Costo externo previsto y realizado localmente: US$0.

### Entrenamiento local: Latinobarómetro

Corrida `study_exp_20261006_155600_fd48cc`, 198 válidas de 200; dos fallas en LLA. **k congelado = 3**.
MAE macro: **13.89 → 6.88 pp**; MAE ponderado por n simulado: **15.13 → 5.93 pp**.
MAE total: 6.92 → 4.50 pp. Son errores de entrenamiento, no prueba externa.

| Grupo (n válido) | Real % aprueba | Qwen B2 esperado | Qwen B2 esperado con k=3 |
|---|---:|---:|---:|
| La Libertad Avanza (43) | 93.34 | 56.40 | 77.69 |
| Peronismo (37) | 5.46 | 26.62 | 10.65 |
| Ninguno / no votaría (40) | 28.42 | 32.00 | 23.37 |
| No sabe / no contesta (52) | 29.07 | 32.50 | 26.14 |
| Juntos por el Cambio (7) | 46.79 | 37.14 | 29.75 |
| Izquierda (8) | 7.70 | 19.38 | 4.02 |
| Otro partido (4) | 24.36 | 31.25 | 21.59 |
| Voto en blanco o nulo (7) | 21.34 | 35.00 | 24.12 |

La aprobación se acerca en partidarios, pero se aleja en independientes y Juntos por el Cambio.
Los cuatro grupos con 4–8 personas no permiten conclusiones firmes; se muestran sin ocultarlos.

Las dos tandas ICG se iniciaron después de guardar `qwen25_lb2024_fit.json`. La evaluación externa está
completada; sus resultados y la conclusión figuran al final.

### Interrupción y reanudación local

Durante las dos tandas ICG dejó de responder tanto SSH como la API de `pcmidi` (el ping seguía respondiendo).
El usuario confirmó que la máquina seguía encendida pero se trababa. Se detuvieron los clientes; quedaron
64 respuestas válidas de septiembre y 66 de enero, más dos fallas de conexión en cada ola, registradas aparte.
SSH volvió a responder y el uptime mostró un reinicio de la máquina. La continuación usa una sola ola y
un cliente por vez para reducir carga. No se activó OpenRouter.

El runner incorpora `--resume-study <id> --retry-errors`: conserva las opiniones válidas, reintenta únicamente
las filas con error y las personas pendientes. Usa el mismo ID de estudio y la misma semilla de respuesta.
Rechaza cambios de pregunta, contexto, opciones, temperature, n, prompt, población, benchmark o modelo/proveedor.
Para nuevas corridas guarda antes de generar un manifest en `.private/experiment_manifests/`.
Los manifests de estas dos tandas se reconstruyeron tras la interrupción con archivos que no cambiaron y
comprobando pregunta, contexto y modelo contra las respuestas guardadas; esta reconstrucción está marcada en el log.

La API `show` confirmó que el alias y el modelo original comparten el mismo GGUF y template, y que la única
diferencia de parámetros es `num_ctx=8192`. No hubo truncamientos en los registros de las respuestas procesadas.

Verificación de código: 108 tests `unittest` OK (94 existentes + 9 de calibración + 5 de reanudación),
compilación de los archivos nuevos y del runner OK, y un recálculo independiente NumPy coincide con las métricas GPT.
La CLI rechaza usar el benchmark de entrenamiento como prueba externa y no escribe un artefacto de validación falso.

### Prueba externa: ICG septiembre con k=3 aprendido en Latinobarómetro

Corrida `study_exp_20261006_160706_fdae28`, completada por reanudación: **199 válidas de 200**.
MAE total esperado **8.88 → 14.78 pp**; MAE macro por zona **9.28 → 14.89 pp**.
El afilado empeora las tres zonas: CABA 8.74 → 13.24, Conurbano 11.27 → 17.98 e Interior 7.84 → 13.44 pp.

| Opción | Real (%) | Qwen B2 esperado | Qwen B2 con k=3 |
|---|---:|---:|---:|
| Muy bien | 9.0 | 10.35 | 2.87 |
| Bien | 22.9 | 20.80 | 16.70 |
| Regular | 22.4 | 33.04 | 50.97 |
| Mal | 10.9 | 24.70 | 26.69 |
| Muy mal | 34.7 | 10.15 | 2.72 |
| No sabe / no contesta | 0.1 | 0.96 | 0.05 |

**La mejora de entrenamiento no se transfiere a esta pregunta:** el afilado refuerza el centro y achica el extremo
que ya estaba subestimado. Una potencia positiva conserva el orden de las opciones de cada perfil; no puede convertir
una opción poco probable para el modelo en su favorita.

### Comprobación recíproca: entrenamiento solo en ICG septiembre

Sin leer las métricas locales de enero, se estimó `k` con septiembre y la misma grilla: **elige k=1** (sin afilado).
Todos los exponentes mayores empeoran el MAE macro por zona. El archivo `qwen25_icgsep_fit.json` se guardó antes
de retomar enero. En Latinobarómetro, prueba externa para este parámetro, el MAE macro sigue en **13.89 pp**
y el ponderado por n simulado en **15.13 pp**: los porcentajes por partido son la columna Qwen B2 esperado de la
tabla anterior, sin mejora. Es una prueba retrospectiva entre preguntas; no una validación política prospectiva.

### Resultado completo: cambio entre olas ICG

Enero: `study_exp_20261006_160706_30e783`, **200 válidas de 200** tras reanudar. Septiembre: 199/200.
Métrica: promedio de probabilidades por persona. El saldo es Muy bien + Bien − Mal − Muy mal;
el cambio informado es **enero 2025 menos septiembre 2026**, manteniendo el orden del experimento anterior.

| Método | MAE sep-2026 (pp) | MAE ene-2025 (pp) | Cambio de saldo (pp) | Error del cambio (pp) |
|---|---:|---:|---:|---:|
| **Real, ponderado** | — | — | **+32.51** | — |
| Referencia: 20% por opción sustantiva | 6.67 | 3.75 | 0.00 | 32.51 |
| Qwen B2+B3 bruto | 8.88 | 9.11 | +1.18 | 31.33 |
| **Qwen con k=3 aprendido en LB2024** | **14.78** | **15.76** | **+1.32** | **31.19** |
| Qwen con k=1 aprendido solo en ICG septiembre | 8.88 (entrenamiento) | 9.11 (prueba) | +1.18 | 31.33 |

Saldo real: −13.764 en septiembre y +18.743 en enero. El **+32.51** proviene de los porcentajes completos
guardados en los benchmarks; el +32.4 de la tabla histórica se había calculado con porcentajes redondeados.
Saldo Qwen bruto: −3.688 y −2.510. Con k=3: −9.828 y −8.510.

En enero, el MAE macro por zona también empeora con k=3: **9.21 → 15.50 pp**. La reducción de 0.14 pp
en el error del cambio es ínfima respecto de la brecha de más de 31 pp y no valida la corrección.

**Conclusión: el afilado global no pasó la prueba externa.** En Latinobarómetro, donde se ajustó, baja el error
por grupo político; en las olas ICG empeora la distribución y casi no modifica el cambio de opinión. Qwen separa
LLA del peronismo en estas corridas, pero sus probabilidades brutas tampoco captan el giro entre meses.
No se habilita una corrección por defecto basándose en estos resultados.

Lo que falta para el siguiente experimento: una segunda ola/encuesta con aprobación e identidad política comparable
para comprobar una corrección específica de ese tipo de pregunta. ICG no contiene identidad política en los perfiles
usados, y otra escala requiere otra validación. No alcanza volver a elegir k mirando este mismo control.

Actualización de fuentes: se descargaron y prepararon **Latinobarómetro 2023 Argentina** (misma aprobación
binaria, otro presidente) y **LAPOP 2026 Argentina** (Milei, escala ordinal con opción regular).
El protocolo y las limitaciones están en `docs/CONTROL_POLITICO_INDEPENDIENTE.md`.
Antes de inferencia en el control se congelaron una corrección logarítmica por grupo y una referencia
de frecuencias del entrenamiento LB2024. No se modifica k=3 ni se elige un método mirando el control.

Resultado del control LB2023 (13/10/2026, 200 válidas de 200, Qwen local): k=3 baja el MAE macro por grupo
político de 13,41 a 4,82 pp; la corrección log por grupo queda en 10,75 y no se transfiere al cambiar el gobierno.
El afilado funciona en aprobación binaria con identidad política y sigue sin funcionar en ICG. Tablas y límites
en `docs/CONTROL_POLITICO_INDEPENDIENTE.md`, sección "Resultado".

Resultado del control LAPOP 2026 (13/10/2026, escala de cinco niveles con identidad política, 200 válidas):
k=3 empeora el MAE macro de 12,19 a 16,48 pp y B2 bruto no supera a 20% por opción (11,95). El modelo sigue
evitando "Muy malo" (7,7% contra 31,4% real). El límite del afilado es la escala, no la falta de identidad.

### Reproducir la calibración offline (sin gasto)

Desde la raíz del repo, en PowerShell. Los datos Latinobarómetro y los derivados permanecen en carpetas ignoradas.
Los archivos `--out` deben tener nombres nuevos: la herramienta rechaza sobrescribir parámetros/evaluaciones.

```powershell
# Entrenar en LB2024 local, con partido recuperado por persona_id
& '.\.venv\Scripts\python.exe' -X utf8 tools/calibrate_probabilities.py fit `
  --results data/privado/resultados/study_exp_20261006_155600_fd48cc.json `
  --benchmark data/privado/benchmarks/bench_lb2024_ar_20261006_132018.json `
  --population data/privado/universos/expansiones/universe_lb2024_ar_20261006_132018_2026-10-06T16-20-18+00-00.json `
  --group-column partido_que_votaria --out .private/calibration/repro_lb_fit.json

# Evaluar las dos olas fuera del entrenamiento, con k congelado
& '.\.venv\Scripts\python.exe' -X utf8 tools/calibrate_probabilities.py evaluate `
  --calibration .private/calibration/repro_lb_fit.json `
  --results data/demo_user/resultados/study_exp_20261006_160706_fdae28.json `
  --benchmark data/demo_user/benchmarks/bench_icg_2026_09_20261006_122319.json `
  --second-results data/demo_user/resultados/study_exp_20261006_160706_30e783.json `
  --second-benchmark data/demo_user/benchmarks/bench_icg_2025_01_20261006_123909.json `
  --positive 'Muy bien' Bien --negative Mal 'Muy mal' `
  --out .private/calibration/repro_icg_external.json
```

La comprobación recíproca usa `fit` con los archivos ICG de septiembre; después `evaluate` con enero y,
en otro comando, con LB2024 más `--population` / `--group-column partido_que_votaria`. Artefactos de esta corrida:
`qwen25_icgsep_fit.json`, `qwen25_icgjan_external_from_icgsep.json`, `qwen25_lb2024_external_from_icgsep.json`.
El reporte principal es `.private/calibration/qwen25_icg_waves_external_from_lb2024.json`.

Auditoría: modelos/proveedor, hashes de fuentes y parámetros en artefactos; resúmenes de todas las tandas y
calibraciones en `tools/experiments_log.jsonl`. Todos los resultados locales válidos tienen proveedor local,
sin fallback. **Gasto OpenRouter en estas tandas: US$0.** Los datos privados siguen ignorados y no se hizo commit.

Revisión metodológica: **compartible con caveats** como resultado negativo de un experimento retrospectivo;
no como prueba de precisión predictiva. Falta una prueba política externa comparable para el k ajustado en LB2024,
hay cuatro grupos pequeños (n=4–8), y no se estimaron efectos de diseño de encuesta ni intervalos de incertidumbre
para las probabilidades esperadas. Los errores reportados no son errores de clasificación individual.
