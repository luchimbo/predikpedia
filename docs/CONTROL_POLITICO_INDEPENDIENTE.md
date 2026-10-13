# Control político independiente — 6 de octubre de 2026

Se consiguieron y prepararon dos bases nuevas con microdatos, identidad política y pesos.
**La prueba principal es Latinobarómetro 2023 Argentina**, misma familia de pregunta y escala
que el entrenamiento LB2024, con otro gobierno. **LAPOP 2026 Argentina** queda preparado
para una prueba ordinal separada con el mismo presidente de 2024. No reemplaza aprobación binaria.

## Fuentes y comparabilidad

| Base | Casos argentinos | Respuesta | Identidad y peso | Uso |
|---|---:|---|---|---|
| [Latinobarómetro 2023](https://www.latinobarometro.org/latinobarometro-2023) | 1.200 | P15STGBS: aprueba / no aprueba / NS-NC, Alberto Fernández | P43STGBS_A: partido que votaría; P16ST: ideología 0–10; wt | Control externo de LB2024, histórico, con cambio de gobierno |
| [LAPOP 2026](https://www.vanderbilt.edu/center-for-global-democracy/data/directory/) | 1.031 | m1: cinco niveles + NS-NC, Javier Milei | vb10/vb11: simpatía partidaria; l1n: ideología 1–10; wt | Otra escala: control separado, todavía sin inferencias |

Latinobarómetro observado: 22/02/2023–01/04/2023. LAPOP observado: 20/03/2026–20/05/2026;
coincide con su [documentación técnica](https://www.vanderbilt.edu/center-for-global-democracy/data/?lp_download=2718).
En LAPOP Argentina, `wt=1` en todos los casos: es una muestra autoponderada según la documentación.
Se conserva wt, sin volver a usar weight1500 como si fuera un segundo peso. Estrato y UPM siguen en el original
para calcular incertidumbre con diseño muestral cuando corresponda; no se mandan al LLM.

Se descargaron los Stata originales, cuestionarios y documentación; SHA-256 y URL de cada descarga
en `.private/source_search/downloads.json`. También se recuperó LB2024 por si hace falta reproducir
su preparación; la calibración usa los resultados, audiencia y benchmark ya guardados, sin alterarlos.

Ambas fuentes restringen uso comercial y redistribución. Los originales y derivados se guardan en
`.private/` y `data/privado/`, ignorados por git. No habilitan una base redistribuible para la app comercial.
Las condiciones de [Latinobarómetro](https://www.latinobarometro.org/agregados) y
[LAPOP](https://www.vanderbilt.edu/center-for-global-democracy/data/directory/) quedan registradas en los manifiestos.

## Calidad y preparación

`tools/prepare_political_holdout.py` prepara audiencias, benchmarks y manifiestos privados. Verifica:

- IDs originales únicos y no ausentes; pesos positivos y finitos; fechas dentro de la ventana documentada.
- Columnas y códigos de la versión descargada. Códigos desconocidos abortan.
- Faltantes extendidos de Stata: NS/NR es una respuesta; inaplicable/no preguntado no se convierte en opinión.
- En LAPOP, VB11 es inaplicable cuando VB10 indica que no simpatiza con un partido o no responde.
  El filtro se comprueba antes de distinguir **sin simpatía** de **identidad no respondida**.
- La respuesta real, peso, identificadores, fecha exacta, UPM y estrato quedan fuera del perfil.
  Solo los atributos enumerados en cada manifiesto llegan a la simulación.
- No se equipara “Avanza Libertad” de LB2023 con “La Libertad Avanza” de LB2024.
  Se conserva una categoría propia; cualquier método aprendido usa su fallback global.
- 200 personas por fuente, muestreo con reposición según wt y semilla determinista derivada del ID.
  Todas las alternativas usan exactamente las mismas personas y probabilidades guardadas.

Audiencias / benchmarks (usuario **privado**):

- `universe_lb2023_ar_holdout_v1_20261006` / `bench_lb2023_ar_holdout_v1_20261006`.
- `universe_lapop2026_ar_holdout_v1_20261006` / `bench_lapop2026_ar_holdout_v1_20261006`.

No falta ningún grupo real en las muestras. En LB2023 hay 8–44 simulados por grupo; en LAPOP, 3–132.
Los grupos pequeños deben informarse completos, pero no sostienen por sí solos una afirmación de mejora.
Los manifiestos privados incluyen n reales y simulados por grupo y faltantes de ideología.

## Protocolo congelado antes de inferencia en LB2023

Entrenamiento exclusivo: `study_exp_20261006_155600_fd48cc`, LB2024, 198 respuestas válidas,
Qwen `qwen2.5:32b-predikpedia-ctx8192`, B2+B3. No se reestima contra los nuevos controles.

Se comparan **las cuatro alternativas completas**, sin seleccionar ni reajustar un ganador con el control:

1. B2 bruto: promedio de probabilidades individuales, sin ruido del sorteo.
2. Afilado global ya congelado: k=3, artefacto `.private/calibration/qwen25_lb2024_fit.json`.
3. Corrección por grupo y opción: multiplicar cada p por exp(delta) y renormalizar por persona.
   `delta = n_sim/(n_sim+30) * clip(log((real_grupo+0.5)/(esperado_grupo+0.5)), -log(3), log(3))`.
   Los porcentajes se expresan en pp. El pseudoconteo 30, suavizado 0.5 pp, cota de ratio 3 y umbral
   n_sim=20 son **fijos**, sin búsqueda en el control. Grupos pequeños o nuevos usan offsets globales,
   calculados solo en entrenamiento. Ceros declarados permanecen ceros.
4. Referencia sin LLM: frecuencias reales por grupo de LB2024 si n_real>=50; total LB2024 en el resto.
   No usa los porcentajes de la encuesta de prueba. Es una referencia de transferencia histórica;
   LB2024 es posterior a LB2023 y por eso **no representa una predicción temporal prospectiva**.

Artefacto de las alternativas 3–4: `.private/calibration/qwen25_lb2024_group_log_fit_v1.json`,
SHA-256 `743e32c071cb0f6bb8fc7bfb198e5cb3b4949f819dc387940a5a03b5dc0c3b5f`.
Se guardó antes de crear/evaluar los benchmarks nuevos y antes de consultar el LLM para LB2023.
Su MAE macro de entrenamiento baja de 13.89 a 8.46 pp: **no es validación externa**.
`tools/fit_group_probability_correction.py` reproduce el ajuste; el artefacto conserva parámetros y baseline.

La corrección específica por partido puede fallar al cambiar quién gobierna. Se registra como prueba
de estrés de esa transferencia; no se invierten offsets ni se reemplazan porcentajes mirando LB2023.
Una corrección por rol gobierno/oposición sería otro experimento con otro protocolo y otro control.

Métricas: distribución esperada y % aprueba por grupo, MAE/TVD por grupo, MAE macro,
MAE ponderado por n simulado, MAE total, errores operativos por grupo, grupos sin ajuste específico.
No es error individual ni intervalo de confianza con diseño muestral. El cambio ICG sigue informado
en `docs/EXPERIMENTOS_VALIDACION.md`; esta nueva prueba no reemplaza ese resultado negativo.

Prompt B2+B3 y temperature=1. Contextos nuevos con hechos públicos al inicio de cada trabajo de campo,
sin porcentajes de aprobación ni resultados de prueba:

- `tools/contextos/argentina_lb2023_control.txt`: presidente del período e IPC enero 2023, publicado antes del campo.
- `tools/contextos/argentina_lapop2026_control.txt`: presidente del período e IPC febrero 2026, publicado antes del campo.

## Ejecución

Ollama verificado por SSH `pcmidi` y HTTP en `192.168.1.101:11434`; alias cargado en GPU, contexto 8192.
Saldo OpenRouter consultado: US$2.122369. Proveedor local explícito, sin fallback, **US$0 externo previsto**.
Una sola tanda y un worker para evitar el bloqueo observado con dos olas simultáneas.
Para 200 personas, estimación inicial 10–15 minutos según las corridas anteriores; no es una garantía.

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 tools/run_benchmark_experiment.py `
  --universe-id universe_lb2023_ar_holdout_v1_20261006 `
  --benchmark-id bench_lb2023_ar_holdout_v1_20261006 --user privado --n 200 --workers 1 `
  --provider local --local-base-url http://192.168.1.101:11434/v1 `
  --local-model qwen2.5:32b-predikpedia-ctx8192 --modo-cerrada probabilidades --temperature 1 `
  --contexto-file tools/contextos/argentina_lb2023_control.txt `
  --label 'LOCAL control LB2023 B2+B3 cuatro alternativas congeladas antes de prueba'

# Después de completar la corrida, sustituir ID por el study_id guardado:
& '.\.venv\Scripts\python.exe' -X utf8 tools/evaluate_political_holdout.py `
  --results data/privado/resultados/ID.json `
  --benchmark data/privado/benchmarks/bench_lb2023_ar_holdout_v1_20261006.json `
  --power-calibration .private/calibration/qwen25_lb2024_fit.json `
  --group-calibration .private/calibration/qwen25_lb2024_group_log_fit_v1.json `
  --out .private/calibration/lb2023_four_methods_external_v1.json
```

La evaluación rechaza entrenamiento, otro modelo y otra escala. Preserva las cuatro comparaciones
por grupo en el JSON privado y registra solo resúmenes en `tools/experiments_log.jsonl`.
LAPOP queda disponible para un siguiente protocolo ordinal; no se colapsa “regular” como desaprobación.

Corrida principal: `study_exp_20261006_170849_1f7bc3`. Se observó otro reinicio remoto durante la tanda.
Al detener el cliente había 122 respuestas válidas guardadas; se reanudó el mismo ID con 78 pendientes,
conservando modelo, personas, prompt, contexto y manifiesto. El reinicio no se atribuye a una causa concreta
porque el registro del kernel consultado no la identifica. El incidente se registró como interrumpido en el log.
El digest del alias siguió siendo `0c1aa3fb987e7dd2a9742ca7f5b70fe44f700c134c0325916961cf91cb2a8add`.

QA independiente: NumPy reproduce porcentajes ponderados totales y de cada grupo en ambas fuentes,
y los offsets/transformación individual de entrenamiento, con tolerancia 1e-10. Se verificó que los dos
artefactos usan exactamente los mismos archivos y firmas de entrenamiento.

## Resultado: LB2023, cuatro métodos congelados (13 de octubre de 2026)

La corrida se completó el 13/10 reanudando el mismo ID: 194 respuestas preservadas y 6 nuevas (5 pendientes más
el error de `P_000184`). **200 válidas de 200**, todas de Qwen local, sin fallback; digest del alias sin cambios.
Antes de reanudar se corrigió el runner: con `--provider local` usa `LLMService(local_only=True)`, porque desde el
9/10 el modo `local` del router puede pasar a OpenRouter. Artefacto: `.private/calibration/lb2023_four_methods_external_v1.json`
(SHA-256 `50586669…`). Ningún parámetro se ajustó con este control.

Real ponderado: Aprueba 20,2 · No aprueba 74,6 · NS/NC 5,2. Métrica: promedio de probabilidades por persona.

| Método | MAE macro grupos (pp) | MAE ponderado n sim. (pp) | MAE total (pp) | Aprueba / No aprueba / NS-NC |
|---|---:|---:|---:|---|
| B2 bruto | 13,41 | 14,34 | 11,35 | 27,7 / 57,6 / 14,8 |
| **Afilado global k=3** | **4,82** | **4,28** | **3,02** | 16,7 / 79,1 / 4,1 |
| Corrección log por grupo | 10,75 | 12,23 | 5,02 | 24,5 / 67,1 / 8,4 |
| Referencia sin LLM (frecuencias LB2024) | 18,45 | 19,70 | 5,28 | 27,4 / 66,7 / 5,9 |

% que aprueba por grupo:

| Grupo (n simulado) | Real | B2 bruto | k=3 | Log por grupo | Referencia LB2024 |
|---|---:|---:|---:|---:|---:|
| No sabe / no contesta (44) | 11,8 | 28,9 | 18,5 | 27,4 | 29,1 |
| Ninguno / no votaría (38) | 8,9 | 21,1 | 6,8 | 19,5 | 28,4 |
| Peronismo (36) | 54,2 | 44,9 | 49,2 | 29,5 | 5,5 |
| Juntos por el Cambio (31) | 6,7 | 23,7 | 5,7 | 24,1 | 38,8 |
| Avanza Libertad, categoría LB2023 (20) | 5,2 | 19,8 | 3,4 | 20,1 | 38,8 |
| Otro partido (12) | 19,1 | 28,8 | 16,0 | 30,8 | 38,8 |
| Voto en blanco o nulo (11) | 14,0 | 16,4 | 2,7 | 17,3 | 38,8 |
| Izquierda (8) | 16,2 | 23,8 | 5,0 | 23,8 | 7,7 |

Sin ajuste específico por grupo (usan offsets globales): Avanza Libertad, Izquierda, Juntos por el Cambio,
Otro partido y Voto en blanco o nulo. Con baseline global: los mismos salvo Izquierda.

Lectura:

1. **El afilado k=3 pasó este control**: baja el error macro de 13,4 a 4,8 pp y mejora el MAE de siete de ocho
   grupos. Empeora Izquierda (7,1 → 10,7 pp) y, aunque su MAE baja, hunde la aprobación de Voto en blanco
   (2,7 contra 14,0 real); son los grupos más chicos (8 y 11 personas).
2. **La corrección por grupo y opción no se transfiere** cuando cambia quién gobierna: baja la aprobación de los
   peronistas de 44,9 a 29,5 contra 54,2 real, que es el riesgo anotado en el protocolo. Su mejora en el total
   viene de los offsets globales.
3. **Qwen usa la identidad política con el gobierno cambiado**: sin corrección ya pone a los peronistas como los
   que más aprueban a Fernández. La referencia sin LLM, que copia las frecuencias por partido de 2024, falla
   justamente ahí (5,5 contra 54,2).
4. Este resultado **no anula el negativo de ICG**: allí k=3 empeoró las dos olas (8,9 → 14,8 pp). Las dos
   pruebas juntas dicen que el afilado sirve en aprobación binaria con identidad política en el perfil, y no en la
   escala de seis opciones sin identidad. Es una corrección por tipo de pregunta, no general.
5. Límites: un solo control, histórico y de respuesta muy desbalanceada (75% no aprueba), donde afilar hacia la
   opción dominante de cada perfil ayuda casi por construcción. Falta una encuesta binaria más pareja o bajo otro
   gobierno, y no hay intervalos de incertidumbre con diseño muestral. No se habilita en la UI con esto solo.

## Protocolo LAPOP 2026 (congelado el 13 de octubre de 2026, antes de consultar al modelo)

Pregunta que responde: en ICG el afilado falló y en LB2023 funcionó, pero entre ambos cambian dos cosas a la vez
(escala e identidad política en el perfil). LAPOP tiene **escala ordinal de cinco niveles con identidad política**,
así que separa las dos explicaciones.

- Audiencia y benchmark ya preparados el 6/10 (`universe_lapop2026_ar_holdout_v1_20261006`,
  `bench_lapop2026_ar_holdout_v1_20261006`), 200 personas, grupo = partido con el que simpatiza.
  Contexto `tools/contextos/argentina_lapop2026_control.txt`, escrito el 6/10. Nada de esto se modifica.
- Mismo modelo y alias (Qwen, digest `0c1aa3fb…`), prompt B2+B3, temperature 1, un worker, solo local.
- Se comparan tres alternativas, sin parámetros libres ni ajuste sobre LAPOP:
  1. B2 bruto.
  2. Afilado k=3 congelado (`qwen25_lb2024_fit.json`), el mismo de ICG y LB2023.
  3. Referencia sin modelo: 20% a cada una de las cinco opciones sustantivas y 0% a NS/NC.
- La corrección log por grupo **queda fuera**: sus offsets son por opción de la escala binaria y no existen para
  esta escala. No se inventa un mapeo.
- Métricas: promedio de probabilidades por persona; MAE total, MAE macro por grupo y ponderado por n simulado;
  saldo (Muy bueno + Bueno − Malo − Muy malo) total y por grupo. No se colapsa "regular" en ningún lado.
- Lectura fijada de antemano: si k=3 empeora el MAE macro, lo que limita al afilado es la escala; si lo mejora,
  lo que faltaba en ICG era la identidad. Una diferencia menor a 3 pp no se interpreta (ruido entre corridas idénticas).
- Limitaciones conocidas antes de correr: 132 de las 200 personas no simpatizan con ningún partido, así que el
  total depende sobre todo de ese grupo; cuatro grupos tienen 3–8 personas y no sostienen conclusiones.
  El benchmark real ya fue visto al prepararlo; no importa para el resultado porque no hay nada que ajustar.

## Resultado LAPOP 2026 (13 de octubre de 2026)

Corrida `study_exp_20261013_164554_7113bf`: 196 válidas en la primera pasada (1001 s) y 4 respuestas con formato
inválido reintentadas con `--resume-study --retry-errors`. **200 válidas de 200**, todas Qwen local, sin fallback.
Artefacto: `.private/calibration/qwen25_lapop2026_external_from_lb2024_v1.json`. Sin ajustes sobre LAPOP.

| Método | MAE macro grupos (pp) | MAE ponderado n sim. (pp) | MAE total (pp) | Saldo total (pp) |
|---|---:|---:|---:|---:|
| **Real** | — | — | — | **−23,9** |
| B2 bruto | 12,19 | 8,88 | 7,96 | +9,8 |
| Afilado global k=3 | 16,48 | 15,11 | 12,35 | +10,9 |
| Referencia: 20% por opción sustantiva | 11,95 | 9,15 | 5,97 | 0,0 |

| Opción | Real | B2 bruto | k=3 |
|---|---:|---:|---:|
| Muy bueno | 6,7 | 12,5 | 4,7 |
| Bueno | 18,1 | 23,5 | 20,1 |
| Ni bueno, ni malo (regular) | 26,2 | 37,7 | 61,3 |
| Malo | 17,3 | 18,5 | 12,3 |
| Muy malo (pésimo) | 31,4 | 7,7 | 1,6 |
| No sabe / no contesta | 0,3 | 0,2 | 0,0 |

Por grupo, MAE (pp) y saldo (pp):

| Grupo (n simulado) | MAE bruto | MAE k=3 | MAE 20% | Saldo real | Saldo bruto | Saldo k=3 |
|---|---:|---:|---:|---:|---:|---:|
| No simpatiza con ningún partido (132) | 7,33 | 15,53 | 6,33 | −25,2 | +7,2 | +5,8 |
| La Libertad Avanza (26) | 4,81 | 4,82 | 15,19 | +84,6 | +60,4 | +91,6 |
| Peronismo (19) | 20,31 | 23,44 | 18,21 | −92,3 | −26,1 | −49,8 |
| Juntos por el Cambio (8) | 8,45 | 14,96 | 5,71 | −4,8 | +35,6 | +63,9 |
| Izquierda (7) | 16,90 | 18,17 | 18,33 | −87,5 | −46,4 | −73,4 |
| No sabe / no contesta (5) | 14,19 | 19,63 | 9,86 | −30,4 | −4,0 | +2,8 |
| Otro partido (3) | 13,33 | 18,80 | 10,00 | −40,0 | −3,3 | −8,6 |

Lectura, según lo fijado antes de correr:

1. **k=3 empeora el MAE macro en 4,3 pp (12,19 → 16,48)**, por encima del umbral de 3 pp, y no mejora ningún
   grupo. Con identidad política en el perfil el afilado igual falla en escala ordinal: **lo que lo limita es la
   escala**, no la falta de identidad. Concentra la masa en "regular" (61% contra 26% real) y borra "Muy malo".
2. **B2 bruto no le gana a repartir 20% por opción** (macro 12,19 contra 11,95; total 7,96 contra 5,97).
   Solo supera con claridad a la referencia en La Libertad Avanza.
3. El defecto es el mismo que en ICG: el modelo evita el extremo negativo. "Muy malo" sale 7,7% contra 31,4% real,
   y el saldo total queda con el signo cambiado (+9,8 contra −23,9). En peronistas, 13,7% contra 74,6%.
4. El modelo ordena bien los partidos (LLA arriba, peronismo e izquierda abajo) pero comprime las distancias.
   En el grupo sin partido, que es dos tercios de la muestra, da saldo positivo cuando el real es −25.
5. Los cuatro grupos con 3–8 personas se informan completos y no sostienen conclusiones por sí solos.

**Conclusión de los tres controles (ICG, LB2023, LAPOP):** el afilado k=3 solo sirve en aprobación binaria.
En escalas de cinco o seis niveles hace falta otra corrección, porque potenciar las probabilidades conserva el
orden de cada perfil y el problema es que el modelo casi nunca pone primero la opción extrema. No se habilita
ninguna corrección en la UI.

## Búsqueda que todavía deja una limitación

[ESPOP/UdeSA](https://www.udesa.edu.ar/departamento-de-ciencias-sociales/espop) ofrece informes de 2026
con aprobación de Milei y cruces políticos, pero no se encontró una descarga pública de microdatos
en la página consultada. No se reconstruyen personas inventadas a partir de cruces marginales.
El catálogo descargable de Latinobarómetro consultado ofrece hasta 2024, aunque anuncia un informe 2026.
Por lo tanto todavía falta otra encuesta **binaria bajo Milei**, con perfiles individuales y pesos,
para aislar transferencia de ola sin el cambio de presidente ni de escala.

Texto listo para solicitar esos datos (no se envió ningún mensaje):

> Estamos realizando una validación metodológica de simulaciones de opinión pública. Buscamos una
> ola ESPOP 2024–2026 de Argentina con microdatos anonimizados, pregunta y codificación de aprobación
> presidencial, partido/ideología, variables demográficas, ponderador, fecha de campo y documentación
> de diseño muestral. Necesitamos conocer también la licencia y condiciones de uso para investigación
> no comercial, sin redistribuir originales ni derivados. ¿Existe una descarga o procedimiento de acceso?
