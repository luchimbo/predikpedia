# Realismo de Predikpedia

Primera etapa implementada localmente el 6 de octubre de 2026: `realism_v1`.

## Referencia y diagnóstico

El [repositorio original de MiroFish](https://github.com/666ghj/MiroFish), consultado el 6 de octubre de 2026, describe datos semilla, grafo de relaciones, perfiles, memoria temporal, interacción con OASIS y reportes. Esto orienta el desarrollo; no prueba precisión predictiva ni implica que Predikpedia ejecute ese motor.

Predikpedia consulta participantes individuales. Sus atributos antes se sorteaban por separado: valores plausibles podían combinarse de forma incoherente. Estudios exigía además una intención comercial aun en preguntas no comerciales o sin información suficiente.

`methodology_v1.md` conserva reglas legacy (pesos 2x, 40%, 80% y vínculos OCEAN) sin calibración documentada. Esta etapa no aplica esas cifras ni umbrales psicométricos antiguos como leyes generales.

## Implementado

- Cada segmento contiene arquetipos con combinaciones completas de atributos y pesos relativos. Datos desconocidos pueden ser `No especificado`; notas distinguen restricciones y supuestos. Son instrucciones de generación, no verificación automática de fuentes.
- Un solo sorteo por persona conserva los atributos juntos. Mayores restos conserva el tamaño de las muestras nuevas sin asignar personas a segmentos de peso cero.
- Crear audiencias mantiene una sola llamada al LLM. Las audiencias sin arquetipos mantienen el algoritmo y secuencia de azar anteriores. Los snapshots guardados permanecen iguales.
- Prompts usan contexto operativo y notas, sin inferir presupuesto desde sensibilidad al precio ni personalidad desde edad o clase social. Permiten aceptar, rechazar, dudar o mostrar desinterés, sin cuotas prefijadas de opinión.
- Intenciones `no_se`, `no_aplica` e `indiferente`, además de las anteriores. Objeción y driver pueden quedar vacíos. Confidence expresa seguridad de una opinión simulada, no probabilidad de compra.
- JSON inválido, respuestas vacías y categorías desconocidas se registran como errores. Las citas ajenas al texto se reemplazan por un fragmento de la respuesta.
- Informes, análisis opcional con IA y KPIs de la pestaña principal excluyen errores y textos vacíos. Descargas y tabla completa mantienen los registros originales.
- Los estudios nuevos guardan `simulation_version="realism_v1"`; anteriores cargan como `legacy`. Ningún campo JSON anterior cambia de nombre.

## Unión con la versión de GitHub (6 de octubre de 2026)

En paralelo se había mergeado en `main` otra implementación de arquetipos (PR #1, ver `ROADMAP_FIABILIDAD.md`). Se unieron así:

- **Arquetipos:** se conserva el formato con nombre, peso y atributos. Dentro de cada segmento las personas se reparten entre arquetipos por mayores restos según el peso y en orden mezclado, así ningún arquetipo con peso queda afuera por azar. Se piden de 4 a 8 por segmento (se aceptan hasta 10). Los arquetipos planos `{campo: valor}` guardados por la otra versión se siguen leyendo.
- **De GitHub:** audiencias desde datos reales (CSV/Excel, una persona por fila; sus columnas llegan al prompt), porcentajes editables en Revisar, segmentos en 0% sin personas, pantallas simplificadas de Audiencias, Estudios y Resultados, y el campo `error` en las respuestas.
- **De esta etapa:** motor de simulación, validación, modalidades (encuesta, entrevista, social), memoria y evidencia de origen. "Chats de soporte" aparece como tercer modo de Audiencias solo si hay una fuente privada importada; modalidad y opciones quedan en "Opciones avanzadas" de Estudios.
- Los errores se marcan de las dos formas (texto `[ERROR: ...]` y campo `error`), y el análisis excluye ambas.

## Límites y evaluación

Los tests verifican conservación de atributos conjuntos, ponderación, determinismo, muestras pequeñas, lectura de JSON anterior, validación e integración con ejecución. No prueban que la salida del LLM coincida con personas reales: falta evaluación conductual con el proveedor y una referencia empírica.

Cada segmento usa hasta cuatro arquetipos. Muchas personas pueden compartir el mismo perfil: aumentar la población no aumenta automáticamente su diversidad ni reduce sesgos del modelo. Pesos sin datos reales son hipótesis. Los prompts y la validación de campos tampoco detectan todas las contradicciones semánticas.

Las repeticiones de una pregunta siguen siendo independientes. No usan respuestas anteriores ni opiniones de otros agentes: hacerlo cambiaría la modalidad de estudio y podría introducir anclaje o contagio artificial.

## Siguientes etapas alineadas con MiroFish

1. **Evidencia de origen:** incorporar entrevistas, encuestas o descripciones aportadas por el usuario. Guardar origen, fecha, fragmento y distinción hecho/supuesto en los perfiles. Evaluar contradicciones frente a esas fuentes antes de expandir.
2. **Individualidad persistente:** ampliar perfiles coherentes dentro de cada arquetipo con restricciones y experiencias sustentadas. Identidad estable por audiencia y persona, sin presentar biografías ficticias como evidencia.
3. **Entrevistas con memoria:** modo explícito de conversación de varias preguntas, con historial por persona y estudio. Aislar usuarios, audiencias y corridas; registrar qué información vio cada participante. Mantener independientes las repeticiones de encuestas.
4. **Simulación social opcional:** definir red, exposición, acciones y rondas antes de integrar OASIS u otro motor. Conservar la respuesta individual inicial para medir cambios tras interacción. Identificar la modalidad en los resultados.
5. **Calibración:** comparar contra una muestra real del mismo segmento y estímulo. Medir preferencias, diversidad, contradicciones, no respuesta y estabilidad entre modelos/semillas; separar evaluación de los datos usados para ajustar. No optimizar solo para parecer convincente.

La calibración requiere una audiencia concreta y material real de referencia. Memoria e interacción deben incorporarse después de definir sus modalidades y criterios de evaluación.
