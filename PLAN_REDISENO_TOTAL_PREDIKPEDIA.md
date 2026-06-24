# Plan Maestro de Rediseno Total de Predikpedia

## 1. Proposito

Este documento define el plan completo para transformar Predikpedia en una plataforma de research sintetico con una experiencia mucho mas clara, legible, consistente y vendible.

No es un plan de mejoras cosmeticas.

Es un plan de cambio total en cuatro niveles:

1. Rediseno visual total.
2. Rediseno total de UX y navegacion.
3. Reorganizacion funcional del producto.
4. Refactor tecnico para que la app deje de sentirse como una herramienta interna y pase a verse como un producto serio.

La restriccion principal es mantener `Streamlit` como base.

---

## 2. Vision objetivo

Predikpedia debe convertirse en una app Streamlit que se sienta como:

1. Un producto de research con IA.
2. Un workspace claro para crear audiencias sinteticas.
3. Un sistema guiado para correr estudios y comparar resultados.
4. Un lugar donde los insights sean faciles de leer, compartir y exportar.

La nueva experiencia debe verse mas cerca de:

1. `Deepsona` en claridad de scorecards, comparaciones y lectura ejecutiva.
2. `Synthetic Users` en flujo guiado, entrevistas, continuidad y reportes.

Pero sin copiar visualmente a ninguno de los dos. La app debe tener una identidad propia.

---

## 3. Diagnostico de la app actual

## 3.1 Problemas visuales graves

1. La UI actual mezcla varios lenguajes visuales a la vez.
2. Hay una topbar decorativa y una navegacion real distinta, lo que confunde.
3. El sidebar esta sobrecargado y contiene demasiadas funciones criticas.
4. La lectura es dificil por densidad excesiva, bloques muy largos y jerarquia visual debil.
5. Hay demasiadas cajas, separadores, colores y elementos compitiendo por atencion.
6. La app se siente "cortada" o apretada por problemas de layout y distribucion.
7. Hay componentes que parecen demo interna y no producto terminado.
8. La interfaz usa demasiados textos tecnicos, etiquetas largas y piezas sueltas sin guiar al usuario.

## 3.2 Problemas de UX graves

1. El usuario no entiende rapidamente por donde empezar.
2. La app mezcla configuracion, ejecucion, archivo y analisis en la misma superficie.
3. No existe un journey principal evidente.
4. El flujo no esta pensado desde objetivos del usuario, sino desde modulos tecnicos.
5. El usuario ve demasiadas decisiones al mismo tiempo.
6. No hay una homepage de producto.
7. No hay suficiente separacion entre "audiencia", "estudio", "resultado" y "reporte".
8. La experiencia actual exige entender el sistema antes de poder usarlo.

## 3.3 Problemas funcionales

1. Conviven dos productos en una sola app:
   - research sintetico general
   - simulacion electoral Peru 2026
2. Los universos custom son mucho mas simples que el caso electoral.
3. La expansion actual de personas es demasiado plana para research profundo.
4. Los estudios custom son todavia muy single-turn.
5. Los resultados actuales muestran datos, pero no siempre decisiones.
6. No hay comparacion fuerte entre variantes, conceptos o escenarios.
7. No hay un panel persistente robusto de personas sinteticas.

## 3.4 Problemas tecnicos que afectan UX

1. `predikpedia.py` concentra demasiadas responsabilidades.
2. `ui_universos.py` tambien concentra demasiadas responsabilidades.
3. `st.session_state` esta distribuido sin una capa de estado clara.
4. La persistencia depende de rutas legacy duras.
5. El motor LLM no expone suficiente metadata ni manejo de errores.
6. La estructura actual hace dificil mejorar la UI sin tocar demasiadas cosas a la vez.

---

## 4. Resultado esperado

Al terminar el rediseno, Predikpedia debe cumplir con esto:

1. La app se entiende en menos de 30 segundos.
2. La pantalla inicial muestra claramente que hacer primero.
3. No hay elementos cortados, montados o dificilmente legibles.
4. No hay mezcla de navegaciones falsas y reales.
5. El layout funciona correctamente en desktop mediano, desktop ancho y laptop comun.
6. La lectura mejora claramente por jerarquia, espaciado y contenido mas enfocado.
7. El flujo principal queda separado en pasos logicos.
8. El usuario puede crear una audiencia, correr un estudio, leer resultados y exportar sin confusion.
9. El modo research y el modo electoral dejan de pelear por el mismo espacio mental.
10. La app se ve como un producto nuevo, no como una version maquillada de la actual.

---

## 5. Principios de producto

1. Primero claridad, despues complejidad.
2. Cada pantalla debe tener un objetivo principal.
3. Cada pantalla debe tener una sola accion primaria.
4. El usuario no debe ver configuracion tecnica antes de ver valor.
5. La app debe guiar, no solo exponer herramientas.
6. El contenido debe ser escaneable.
7. Los resultados deben responder preguntas de negocio, no solo mostrar texto.
8. La experiencia debe ser amable para alguien no tecnico.
9. La complejidad avanzada debe estar disponible, pero nunca dominar la interfaz.
10. Todo cambio visual debe mejorar legibilidad, foco o navegacion.

---

## 6. Objetivos del rediseno total visual

## 6.1 Objetivo principal

Hacer un cambio visual total que elimine la sensacion actual de caos, corte, amontonamiento y dificultad de lectura.

## 6.2 Lo que implica "cambio total visual"

1. Rehacer la shell visual completa.
2. Rehacer navegacion, layout, cards, formularios, tablas y graficos.
3. Rehacer el sistema tipografico.
4. Rehacer la paleta y el sistema de superficies.
5. Rehacer los estados vacios, alertas y bloques informativos.
6. Rehacer la densidad visual.
7. Rehacer el orden de lectura.
8. Rehacer la experiencia responsive.
9. Rehacer el lenguaje visual de botones y CTA.
10. Rehacer la presentacion de resultados para que sean mas ejecutivos.

## 6.3 Lo que NO sirve

No alcanza con:

1. Cambiar colores.
2. Retocar CSS aislado.
3. Agregar sombras o bordes nuevos.
4. Cambiar el ancho del container y dejar lo demas igual.
5. Mantener la misma arquitectura de informacion con un look distinto.

---

## 7. Nueva direccion visual

## 7.1 Posicionamiento visual deseado

La app debe verse como una plataforma de research premium, limpia, sobria y contemporanea.

Tono visual:

1. Claro.
2. Profesional.
3. Calmado.
4. Data-first.
5. Sin estetica de demo ni de panel tecnico.

## 7.2 Direccion recomendada

Usar una direccion tipo:

1. Fondo claro y respirable.
2. Superficies blancas o gris muy suave.
3. Acento fuerte y unico para marca/acciones.
4. Tipografia sans moderna para contenido.
5. Monoespaciada solo para numeros, IDs y metadata.
6. Cards suaves, no pesadas.
7. Bordes finos, nada barroco.
8. Graficos limpios y legibles.

## 7.3 Decisiones visuales concretas

1. Eliminar la topbar ornamental actual.
2. Eliminar estilos que simulan navegacion donde no la hay.
3. Reducir uso de decoracion que no aporta lectura.
4. Eliminar exceso de iconos/emoji en labels y botones.
5. Usar un set de iconos consistente.
6. Hacer que las metric cards sean mas simples y menos gritadas.
7. Dejar mas espacio entre bloques y menos separadores duros.
8. Reforzar jerarquia con tamano, peso y espaciado, no solo color.

---

## 8. Sistema de diseno objetivo

## 8.1 Paleta

Definir un sistema de tokens, no colores sueltos.

Tokens minimos:

1. `bg_app`
2. `bg_surface`
3. `bg_surface_alt`
4. `border_subtle`
5. `text_primary`
6. `text_secondary`
7. `text_muted`
8. `accent_primary`
9. `accent_primary_soft`
10. `success`
11. `warning`
12. `danger`
13. `info`

Reglas:

1. Un solo color de acento fuerte.
2. Maximo dos tonos de acento secundarios.
3. No usar combinaciones de color que compitan entre si.
4. Contraste AA como minimo.
5. Graficos y estados deben derivar del sistema, no de hex random.

## 8.2 Tipografia

Sistema tipografico propuesto:

1. UI y contenido: `Inter` o similar.
2. Datos, IDs, numeros y costos: `IBM Plex Mono` o similar.

Escala sugerida:

1. `display`: 32-40px
2. `page_title`: 24-28px
3. `section_title`: 18-20px
4. `card_title`: 15-16px
5. `body`: 14-16px
6. `meta`: 12-13px

Reglas:

1. Nada de bloques largos con mismo peso visual.
2. El texto de ayuda debe verse mas liviano que el texto principal.
3. Los labels no deben competir con los titulos.
4. Evitar mayusculas excesivas salvo en metadata muy puntual.

## 8.3 Espaciado

Usar escala consistente:

1. 4
2. 8
3. 12
4. 16
5. 24
6. 32
7. 40
8. 48

Reglas:

1. Cada seccion debe respirar.
2. El gap vertical entre bloques principales debe ser amplio.
3. Los formularios no deben verse comprimidos.
4. No usar mas de dos densidades distintas en una misma pantalla.

## 8.4 Radios, sombras y bordes

1. Radios suaves y consistentes.
2. Sombras minimas, solo para separar superficie.
3. Bordes finos y claros.
4. Nada de brillo fuerte ni look recargado.

## 8.5 Componentes base

Diseñar y estandarizar:

1. `PageHeader`
2. `SectionHeader`
3. `MetricCard`
4. `InsightCard`
5. `StatStrip`
6. `EmptyState`
7. `FilterBar`
8. `PrimaryCTA`
9. `SecondaryCTA`
10. `StatusChip`
11. `InfoBanner`
12. `TableShell`
13. `ResultQuote`
14. `ComparisonCard`

---

## 9. Reglas obligatorias de layout para corregir lo "cortado"

Este punto es critico. La nueva UI debe resolver explicitamente la sensacion de que todo se corta por los lados o entra mal.

## 9.1 Reglas de ancho

1. Definir un `max-width` consistente para el contenido principal.
2. No mezclar cards full width con bloques internos angostos sin razon.
3. Evitar columnas demasiado finas en formularios largos.
4. Toda tabla ancha debe tener contenedor controlado.
5. Todo texto largo debe wrapear correctamente.

## 9.2 Reglas responsive

La app debe revisarse al menos en:

1. 1440px
2. 1280px
3. 1024px
4. 768px

Validaciones obligatorias:

1. No horizontal scroll inesperado.
2. No cards truncadas.
3. No titulos cortados.
4. No columnas que colapsen mal.
5. No inputs que queden apretados o desalineados.
6. No tablas ilegibles sin solucion visual.

## 9.3 Reglas para Streamlit

1. Reducir uso de `st.columns` cuando genera micro-columnas ilegibles.
2. No construir layouts complejos con demasiadas columnas anidadas.
3. Usar `use_container_width=True` de forma consistente donde corresponda.
4. Revisar `block-container` y paddings globales.
5. Evitar HTML/CSS que rompa el flujo natural de Streamlit.
6. No depender de hacks fragiles para la navegacion principal.

---

## 10. Arquitectura de informacion nueva

La app deja de organizarse por modulos tecnicos y pasa a organizarse por flujo de usuario.

## 10.1 Paginas principales

1. `Inicio`
2. `Audiencias`
3. `Estudios`
4. `Resultados`
5. `Reportes`
6. `Configuracion`

## 10.2 Modos de producto

La app debe contemplar dos workspaces o modos:

1. `Research`
2. `Electoral`

Opciones validas:

1. Dos paginas de entrada separadas.
2. Un selector de modo en `Inicio`.
3. Dos shells internas distintas compartiendo servicios.

Lo importante es que no se mezclen dentro de la misma pantalla principal.

---

## 11. Estructura objetivo de cada pagina

## 11.1 Inicio

Objetivo:

1. Decirle al usuario que puede hacer.
2. Mostrar estado actual del workspace.
3. Dar accesos directos claros.

Bloques:

1. Hero corto con propuesta de valor.
2. CTA principal `Nuevo estudio`.
3. CTA secundaria `Crear audiencia`.
4. Cards de resumen:
   - audiencias guardadas
   - estudios recientes
   - ultimo reporte
   - uso/costo reciente
5. Lista de estudios recientes.
6. Lista de audiencias recientes.
7. Seccion `Elegir modo` si aplica.

No debe incluir:

1. API key visible.
2. Inputs tecnicos.
3. Creditos dominando el espacio.
4. Metodologia larga.

## 11.2 Audiencias

Objetivo:

1. Crear, editar, expandir y reutilizar audiencias.

Subflujo:

1. Biblioteca de audiencias.
2. Crear nueva audiencia.
3. Segmentar.
4. Revisar.
5. Expandir panel.

Bloques:

1. Header con busqueda y filtros.
2. Tabla o grid de audiencias guardadas.
3. Wizard de creacion.
4. Preview de composicion.
5. Preview de personas sinteticas.

Mejoras clave:

1. Permitir mas de 3 segmentos.
2. Mostrar composicion de forma visual.
3. Separar claramente descripcion general vs segmentos.
4. Hacer que la expansion tenga sentido para el usuario.

## 11.3 Estudios

Objetivo:

1. Configurar y ejecutar un estudio con la menor friccion posible.

Subflujo ideal:

1. Elegir audiencia.
2. Elegir tipo de estudio.
3. Agregar estimulo o pregunta.
4. Configurar muestra.
5. Revisar costo y tiempo.
6. Ejecutar.

Tipos de estudio iniciales:

1. Exploratorio.
2. Concept test.
3. Messaging test.
4. Pricing.
5. Feature feedback.
6. Electoral.

Bloques:

1. Selector de audiencia.
2. Selector de template.
3. Formulario principal.
4. Panel lateral o card de resumen.
5. CTA de ejecucion.
6. Progreso claro.

## 11.4 Resultados

Objetivo:

1. Ver hallazgos accionables, no solo respuestas.

Jerarquia recomendada:

1. Resumen ejecutivo.
2. KPIs del estudio.
3. Drivers y barreras.
4. Insights por segmento.
5. Quotes destacadas.
6. Tabla completa.

Bloques:

1. Encabezado con metadata del estudio.
2. Scorecards.
3. Seccion de hallazgos.
4. Comparacion entre segmentos.
5. Explorador de respuestas.

## 11.5 Reportes

Objetivo:

1. Releer historico y exportar.

Bloques:

1. Lista de estudios guardados.
2. Filtros por audiencia, fecha, template, estado.
3. Vista resumida del reporte.
4. Exportes.
5. Comparacion de estudios.

## 11.6 Configuracion

Objetivo:

1. Sacar del flujo principal toda la complejidad tecnica.

Bloques:

1. API keys.
2. Proveedor/modelo.
3. User ID.
4. Storage path/configuracion.
5. Creditos y billing.
6. Parametros avanzados.

---

## 12. Rediseno total de UX

## 12.1 Journey principal nuevo

El usuario debe poder entender este flujo sin capacitacion:

1. Entro a la app.
2. Veo un CTA claro.
3. Creo o elijo una audiencia.
4. Elijo el tipo de estudio.
5. Corro la simulacion.
6. Veo un resumen facil de leer.
7. Profundizo si quiero.
8. Exporto si lo necesito.

## 12.2 Reglas UX obligatorias

1. Una accion primaria por pantalla.
2. Un bloque de contexto por pantalla.
3. Un bloque de ayuda solo cuando haga falta.
4. Menos densidad en formularios.
5. Menos texto todo junto.
6. Mas feedback de estado.
7. Mas explicacion previa a acciones caras.
8. Menos dependencia de saber terminos internos.

## 12.3 Estados vacios y ayudas

Crear estados vacios claros para:

1. No hay audiencias.
2. No hay expansion.
3. No hay estudios.
4. No hay resultados.
5. No hay API key.
6. No hay saldo.

Cada estado vacio debe incluir:

1. Mensaje corto.
2. Explicacion breve.
3. CTA siguiente.

---

## 13. Rediseno funcional del producto

## 13.1 Audiencias y personas sinteticas

Hay que enriquecer el modelo de audiencia/persona.

Campos nuevos recomendados para personas sinteticas:

1. `persona_id`
2. `perfil`
3. `perfil_descripcion`
4. `edad_rango`
5. `rol`
6. `industria`
7. `objetivo`
8. `principal_pain`
9. `motivador`
10. `objecion_base`
11. `sensibilidad_precio`
12. `comportamiento`
13. `canal_preferido`
14. `contexto_operativo`
15. `notas`

Objetivo:

1. Que la expansion no sea solo reparto porcentual.
2. Que las personas sintenticas sirvan para estudios mas ricos.

## 13.2 Tipos de estudio

Definir y soportar como templates:

1. `exploratory_interview`
2. `concept_test`
3. `messaging_test`
4. `pricing_test`
5. `feature_feedback`
6. `electoral_scenario`

Cada template debe definir:

1. Inputs esperados.
2. Prompt base.
3. Estructura de salida.
4. Metricas sugeridas.
5. Vista de resultados sugerida.

## 13.3 Comparacion de variantes

Feature obligatoria en roadmap:

1. Poder comparar dos o mas variantes.
2. Poder comparar por segmento.
3. Poder mostrar cual rinde mejor y por que.

Casos:

1. Dos mensajes.
2. Dos conceptos.
3. Dos ofertas.
4. Dos escenarios electorales.

## 13.4 Reportes e insights

La app debe dejar de depender solo de tablas y keywords.

Agregar capas de lectura:

1. Executive summary.
2. Top insights.
3. Top objections.
4. Top drivers.
5. Quotes destacadas.
6. Diferencias por segmento.
7. Recomendaciones accionables.

---

## 14. Arquitectura tecnica objetivo

## 14.1 Reorganizacion de archivos

Estructura sugerida:

```text
app/
  main.py
  state.py
  theme.py
  navigation.py
  pages/
    home.py
    audiencias.py
    estudios.py
    resultados.py
    reportes.py
    settings.py
    electoral.py
  components/
    page_header.py
    cards.py
    filters.py
    empty_states.py
    tables.py
    charts.py
    forms.py
  services/
    universe_service.py
    study_service.py
    results_service.py
    report_service.py
    llm_service.py
  domain/
    models.py
    prompts.py
    templates.py
  storage/
    repositories.py
    migrations.py
    paths.py
```

No hace falta hacer todo de golpe, pero esta debe ser la direccion.

## 14.2 Separacion de responsabilidades

1. UI renderiza.
2. Services orquestan casos de uso.
3. Domain define entidades y reglas.
4. Storage persiste.
5. Theme define identidad.
6. State centraliza el estado de app.

## 14.3 `session_state`

Crear una capa central de estado con claves fijas:

1. `current_page`
2. `workspace_mode`
3. `active_universe_id`
4. `active_panel_id`
5. `active_study_id`
6. `active_results_id`
7. `run_status`
8. `last_error`
9. `saved_api_key`
10. `settings`

---

## 15. Refactor del motor LLM

## 15.1 Mejoras obligatorias

1. Separar errores de respuestas validas.
2. Guardar provider, modelo y timestamps.
3. Agregar retries.
4. Agregar timeout.
5. Agregar logging de corrida.
6. Preparar salidas estructuradas.
7. Registrar tokens si el provider lo devuelve.

## 15.2 Salida estructurada

Siempre que el template lo permita, pedir JSON con campos como:

1. `response_text`
2. `sentiment`
3. `intent`
4. `main_objection`
5. `main_driver`
6. `confidence`
7. `price_sensitivity`
8. `quote`

Objetivo:

1. Analisis mas consistente.
2. Mejor comparacion entre estudios.
3. Mejor reporte.

---

## 16. Persistencia y operacion

## 16.1 Corto plazo

1. Mantener JSON si hace falta para avanzar rapido.
2. Pero desacoplar rutas fijas.
3. Definir una carpeta de datos configurable.
4. Separar storage legacy de storage nuevo.

## 16.2 Mediano plazo

Migrar a `SQLite` para:

1. audiencias
2. panels
3. estudios
4. respuestas
5. exports
6. logs

Beneficios:

1. Menos fragilidad.
2. Mejor historial.
3. Mejor filtrado.
4. Mejor performance.

---

## 17. Roadmap por fases

## Fase 0 - Definicion y baseline

Duracion estimada:

1. 2 a 3 dias.

Objetivo:

1. Cerrar vision, alcance y criterio visual.

Tareas:

1. Definir el modo research y el modo electoral.
2. Definir paginas finales.
3. Definir sistema visual objetivo.
4. Definir backlog P0, P1 y P2.
5. Congelar nuevas features fuera del plan.

Entregables:

1. Este plan aprobado.
2. Sitemap aprobado.
3. Lista de componentes base.

## Fase 1 - Shell nueva y layout nuevo

Duracion estimada:

1. 4 a 6 dias.

Objetivo:

1. Cambiar totalmente la estructura visible de la app.

Tareas:

1. Crear nueva navegacion real.
2. Sacar topbar falsa.
3. Rehacer sidebar para contexto, no para control total.
4. Rehacer `block-container` y paddings.
5. Corregir anchos y cortes laterales.
6. Crear `PageHeader`, `SectionHeader`, `EmptyState`, `MetricCard`.
7. Crear homepage nueva.

Archivos impactados:

1. `predikpedia.py`
2. nuevos modulos de shell

Definicion de listo:

1. La app ya se ve claramente distinta.
2. Ya no hay confusion de navegacion.
3. Ya no hay sensacion fuerte de amontonamiento.

## Fase 2 - Rediseno total de Audiencias

Duracion estimada:

1. 5 a 7 dias.

Objetivo:

1. Hacer entendible la creacion de universos/audiencias.

Tareas:

1. Separar biblioteca y creacion.
2. Convertir la creacion en wizard.
3. Permitir mas segmentos.
4. Mejorar validacion visual.
5. Mejorar preview de composicion.
6. Mejorar expansion y preview de personas.
7. Crear cards/tabla de audiencias guardadas.

Archivos impactados:

1. `ui_universos.py`
2. `models_universos.py`
3. `services_universo_expansion.py`
4. `storage_universos.py`

Definicion de listo:

1. Un usuario nuevo entiende como crear una audiencia.
2. La pantalla deja de parecer un formulario improvisado.

## Fase 3 - Rediseno total de Estudios

Duracion estimada:

1. 5 a 7 dias.

Objetivo:

1. Convertir la ejecucion en un flujo guiado y predecible.

Tareas:

1. Crear `Study Wizard`.
2. Agregar templates.
3. Separar configuracion de estudio de resultados.
4. Mostrar resumen previo de ejecucion.
5. Mejorar feedback de progreso.
6. Agregar resume/checkpoint.
7. Unificar semantica entre estudio custom y OASIS.

Archivos impactados:

1. `ui_universos.py`
2. `predikpedia.py`
3. `engine_llm.py`
4. nuevos servicios de estudio

Definicion de listo:

1. El usuario sabe que estudio corre, sobre quien y con que objetivo.
2. No ve ruido innecesario mientras configura.

## Fase 4 - Rediseno total de Resultados

Duracion estimada:

1. 5 a 7 dias.

Objetivo:

1. Hacer que resultados e insights sean faciles de leer y compartir.

Tareas:

1. Rehacer jerarquia de resultados.
2. Agregar resumen ejecutivo.
3. Agregar drivers, barriers y quotes.
4. Mejorar tablas y filtros.
5. Mejorar charts.
6. Diferenciar claramente resultado activo, historico y checkpoint.

Archivos impactados:

1. `predikpedia.py`
2. `ui_universos.py`
3. nuevos servicios de analisis

Definicion de listo:

1. El resultado puede leerse rapido sin bajar primero a la tabla cruda.

## Fase 5 - Reportes y comparacion

Duracion estimada:

1. 4 a 6 dias.

Objetivo:

1. Dar una capa de lectura ejecutiva y reutilizable.

Tareas:

1. Pantalla de reportes.
2. Comparacion entre estudios.
3. Comparacion entre variantes.
4. Exportes mas limpios.
5. Cards de findings reutilizables.

Definicion de listo:

1. La app ya entrega outputs presentables a terceros.

## Fase 6 - Robustez, storage y operacion

Duracion estimada:

1. 4 a 6 dias.

Objetivo:

1. Reducir deuda tecnica que impacta producto.

Tareas:

1. Desacoplar rutas legacy.
2. Mejorar storage.
3. Mejorar manejo de errores.
4. Guardar metadata de corridas.
5. Preparar migracion a SQLite.

Definicion de listo:

1. La app es mas estable y portable.

---

## 18. Backlog detallado por area

## 18.1 Area visual

P0:

1. Eliminar topbar falsa.
2. Rehacer shell.
3. Rehacer spacing.
4. Rehacer tipografia.
5. Rehacer cards.
6. Corregir layout cortado.
7. Rehacer sidebar.

P1:

1. Rehacer graficos.
2. Rehacer tablas.
3. Rehacer chips y alertas.
4. Rehacer empty states.

P2:

1. Motion sutil.
2. Tema oscuro opcional.

## 18.2 Area UX

P0:

1. Sitemap nuevo.
2. Journey principal nuevo.
3. Wizard para audiencias.
4. Wizard para estudios.
5. Separar research y electoral.

P1:

1. Comparacion entre variantes.
2. Mejor explorador de respuestas.

## 18.3 Area funcional

P0:

1. Enriquecer personas sinteticas.
2. Mejorar templates.
3. Mejorar metadata.
4. Mejorar resultados.

P1:

1. Panel persistente.
2. Quotes estructuradas.
3. Mejor clustering.

## 18.4 Area tecnica

P0:

1. Separar UI, services y storage.
2. Centralizar state.
3. Mejorar motor LLM.

P1:

1. SQLite.
2. Jobs asincronicos si hace falta.

---

## 19. Checklist especifico de rediseno visual total

Este checklist no es opcional.

## 19.1 Shell

1. Nueva navegacion principal.
2. Nuevo header por pagina.
3. Nuevo sidebar contextual.
4. Nuevo ancho maximo.
5. Nuevo padding global.

## 19.2 Legibilidad

1. Reescribir jerarquia tipografica.
2. Reducir densidad de contenido.
3. Mejorar contraste.
4. Mejorar largos de linea.
5. Cortar bloques de texto muy largos.

## 19.3 Formularios

1. Labels claros.
2. Agrupacion logica.
3. Menos campos visibles a la vez.
4. Mejor feedback de validacion.
5. Mejor CTA principal.

## 19.4 Resultados

1. Resumen primero.
2. Insights despues.
3. Tabla cruda al final.
4. Exportes visibles pero no invasivos.

## 19.5 Responsive

1. Revisar desktop ancho.
2. Revisar laptop.
3. Revisar tablet.
4. Corregir overflow.
5. Corregir wrapping.

---

## 20. QA obligatoria

## 20.1 QA visual

1. Revisar que no haya elementos cortados.
2. Revisar que no haya texto montado.
3. Revisar que no haya horizontal scroll raro.
4. Revisar que la lectura sea clara.
5. Revisar que cada pantalla tenga foco claro.

## 20.2 QA funcional

1. Crear audiencia.
2. Guardar audiencia.
3. Expandir audiencia.
4. Ejecutar estudio.
5. Ver resultado.
6. Exportar.
7. Reabrir historico.

## 20.3 QA de percepcion

Preguntas que la nueva UI debe responder con un "si":

1. Se entiende donde empezar.
2. Se entiende que hace cada pantalla.
3. Se entiende que resultado estoy mirando.
4. Se siente mas producto y menos herramienta interna.
5. Se puede mostrar a alguien externo sin pedir contexto previo.

---

## 21. Riesgos del proyecto

1. Querer cambiar la UI sin cambiar la arquitectura de informacion.
2. Querer conservar demasiadas piezas viejas por miedo a romper.
3. Mezclar el rediseno visual con nuevas features sin prioridad.
4. Rehacer CSS pero no el flujo.
5. No separar research y electoral.
6. No validar responsive en tamanos reales.

Mitigaciones:

1. Fases claras.
2. Definicion de listo por etapa.
3. Feature freeze temporal.
4. Testing de layouts en cada fase.

---

## 22. Metricas de exito

## 22.1 Producto

1. Tiempo hasta primer estudio ejecutado.
2. Tiempo hasta primer insight visible.
3. Porcentaje de usuarios que completan el flujo principal.
4. Reutilizacion de audiencias.

## 22.2 UX

1. Menos pasos percibidos.
2. Menos dudas sobre donde empezar.
3. Menos dependencia del sidebar.
4. Menos scroll inutil.

## 22.3 Visual

1. Cero elementos cortados en tamanos objetivo.
2. Mejor legibilidad percibida.
3. Menor densidad visual innecesaria.
4. Consistencia visual entre paginas.

---

## 23. Orden recomendado de implementacion

Orden obligatorio sugerido:

1. Definir vision y sitemap.
2. Rehacer shell y layout.
3. Rehacer homepage.
4. Rehacer Audiencias.
5. Rehacer Estudios.
6. Rehacer Resultados.
7. Agregar Reportes.
8. Mejorar storage y motor.

No hacer primero:

1. nuevos modelos visuales aislados
2. animaciones
3. dark mode
4. features secundarias

---

## 24. Definicion final de "done"

El rediseno total solo se considera terminado si se cumplen todas estas condiciones:

1. La app se ve claramente distinta a la actual.
2. La navegacion ya no confunde.
3. El contenido ya no se ve cortado ni comprimido.
4. El journey principal se entiende sin explicacion externa.
5. La lectura de resultados es rapida y clara.
6. Research y electoral ya no pelean por la misma interfaz.
7. La UI se siente producto y no prototipo.
8. La arquitectura deja espacio real para crecer.

---

## 25. Recomendacion ejecutiva

La app necesita un cambio total visual y de UX, no una iteracion chica.

La mejor estrategia es:

1. Redibujar la shell completa.
2. Separar el producto por paginas y modos.
3. Simplificar el journey.
4. Rehacer la legibilidad de punta a punta.
5. Reordenar el sistema tecnico para sostener esa nueva interfaz.

Si se hace bien, Predikpedia puede pasar de una app dificil de entender a una plataforma que realmente pueda mostrarse, venderse y operarse con confianza.
