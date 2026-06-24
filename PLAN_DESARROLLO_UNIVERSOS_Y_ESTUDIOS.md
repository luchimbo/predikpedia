# Plan de Desarrollo: Universos y Estudios con Perfiles de Cliente

## 1. Objetivo

Transformar la app actual en una experiencia simple y clara para:

1. Crear un universo a partir de perfiles de cliente.
2. Definir el porcentaje de cada perfil dentro del universo.
3. Guardar ese universo en una biblioteca reutilizable.
4. Ejecutar un estudio sobre un universo guardado.
5. Escribir una pregunta y un contexto opcional.
6. Elegir cuantas veces responde la misma pregunta cada persona.
7. Ver resultados dentro de la app.
8. Descargar los resultados en Excel.

## 2. Alcance de esta primera version

### Incluye

1. Motor unico.
2. Solo perfiles de cliente.
3. Sin geografia.
4. Biblioteca de universos.
5. Pantalla de estudio.
6. Repeticion opcional de la misma pregunta por persona.
7. Resultados en tabla y analisis simple.
8. Exportacion a Excel.

### No incluye por ahora

1. Segmentacion geografica.
2. Edicion avanzada de universos existentes.
3. Multiples preguntas distintas dentro del mismo estudio.
4. Flujos politicos o regionales dedicados.
5. Configuraciones psicometricas complejas visibles en la interfaz.

## 3. Principios de producto

1. Todo en espanol.
2. La interfaz debe ser entendible sin capacitacion.
3. Crear universo y ejecutar estudio son pasos separados.
4. Lo opcional no debe entorpecer lo basico.
5. El usuario siempre debe saber:
   - que universo esta usando
   - cuantas personas tiene
   - como se compone
   - que pregunta se esta haciendo
   - cuantas respuestas se van a generar
   - donde quedan guardados los resultados

## 4. Problemas de la app actual que este plan resuelve

1. El generador de universos hoy esta atado a casos fijos.
2. La biblioteca existe, pero no esta pensada para perfiles de cliente simples.
3. La pregunta y el analisis ya existen, pero no estan organizados alrededor de un flujo de estudio claro.
4. Los resultados se descargan en CSV, no en Excel.
5. La experiencia actual esta muy cargada visualmente para el objetivo nuevo.

## 5. Resultado esperado

Al terminar esta version, el usuario deberia poder hacer esto de punta a punta:

1. Entrar a `Universos`.
2. Crear un universo con nombre, descripcion, cantidad de personas y perfiles con porcentajes.
3. Guardarlo.
4. Ir a `Estudio`.
5. Elegir ese universo.
6. Escribir una pregunta.
7. Agregar un contexto opcional.
8. Elegir si cada persona responde 1 vez o varias veces la misma pregunta.
9. Ejecutar el estudio.
10. Ir a `Resultados`.
11. Ver resumen, tabla y analisis.
12. Descargar un Excel claro.

## 6. Arquitectura funcional

La app se reorganiza en 3 areas principales:

1. `Universos`
2. `Estudio`
3. `Resultados`

### 6.1 Universos

Responsabilidades:

1. Crear universos nuevos.
2. Mostrar la biblioteca de universos guardados.
3. Permitir seleccionar un universo para usarlo en un estudio.

### 6.2 Estudio

Responsabilidades:

1. Tomar un universo guardado.
2. Configurar la pregunta.
3. Configurar el contexto adicional.
4. Configurar cuantas veces responde cada persona.
5. Ejecutar el estudio.

### 6.3 Resultados

Responsabilidades:

1. Mostrar resumen ejecutivo.
2. Mostrar tabla detallada.
3. Permitir filtros basicos.
4. Permitir descarga en Excel.
5. Permitir volver a leer estudios guardados.

## 7. Reglas de negocio

### 7.1 Universo

Un universo debe tener:

1. Nombre.
2. Descripcion general.
3. Cantidad total de personas.
4. Al menos 1 perfil de cliente.
5. Porcentaje por perfil.

### 7.2 Perfiles

Cada perfil debe tener:

1. Nombre.
2. Descripcion.
3. Porcentaje.

### 7.3 Validaciones de porcentajes

1. La suma de porcentajes debe ser 100.
2. No se puede guardar el universo si la suma no es 100.
3. No se permiten porcentajes negativos.
4. No se permiten perfiles vacios.

### 7.4 Estudio

Cada estudio debe tener:

1. Universo seleccionado.
2. Pregunta obligatoria.
3. Contexto adicional opcional.
4. Cantidad de respuestas por persona.

### 7.5 Respuestas por persona

1. Valor por defecto: 1.
2. Minimo: 1.
3. Si el valor es mayor a 1, la persona responde varias veces la misma pregunta.
4. Cada respuesta debe quedar registrada con su numero de repeticion.

## 8. Diseño UX/UI

## 8.1 Objetivo UX

La experiencia debe sentirse como un flujo de trabajo simple:

1. Primero creo el universo.
2. Despues hago el estudio.
3. Despues analizo y descargo.

## 8.2 Estructura de navegacion

Usar 3 pestañas principales en lugar de concentrar todo en el panel lateral:

1. `Universos`
2. `Estudio`
3. `Resultados`

El panel lateral debe quedar para cosas secundarias, no para el flujo principal.

## 8.3 Pantalla `Universos`

### Bloque 1: Biblioteca de universos

Mostrar por cada universo:

1. Nombre.
2. Descripcion corta.
3. Cantidad de personas.
4. Cantidad de perfiles.
5. Fecha de creacion.
6. Boton `Usar en estudio`.

### Bloque 2: Crear universo

Campos:

1. `Nombre del universo`
2. `Descripcion del universo`
3. `Cantidad de personas`

### Bloque 3: Perfiles de cliente

Cada fila de perfil debe tener:

1. `Nombre del perfil`
2. `Descripcion`
3. `Porcentaje`
4. `Eliminar`

### Bloque 4: Resumen y validacion

Mostrar:

1. Porcentaje acumulado.
2. Cantidad de perfiles cargados.
3. Cantidad total de personas.
4. Estado de validacion.

Mensajes UX:

1. Si suma menos de 100: `Falta completar el porcentaje total del universo.`
2. Si suma mas de 100: `El porcentaje total supera 100. Revisalo antes de guardar.`
3. Si suma 100: `El universo esta listo para guardarse.`

### Decisiones de interfaz

1. Boton visible `Agregar perfil`.
2. Boton principal `Guardar universo`.
3. No esconder la validacion al final.
4. Mostrar el porcentaje total siempre.

## 8.4 Pantalla `Estudio`

### Bloque 1: Universo seleccionado

Mostrar:

1. Nombre.
2. Descripcion.
3. Cantidad de personas.
4. Resumen de perfiles y porcentajes.

### Bloque 2: Pregunta

Campo grande:

1. `Pregunta`

Ayuda:

1. `Escribi la pregunta que queres que responda este universo.`

### Bloque 3: Contexto adicional

Campo opcional:

1. `Contexto adicional`

Ayuda:

1. `Agrega informacion extra que las personas deben tener en cuenta al responder.`

### Bloque 4: Configuracion del estudio

Campos:

1. `Respuestas por persona`

Ayuda:

1. `Por defecto es 1. Si elegis un numero mayor, cada persona respondera varias veces la misma pregunta.`

### Bloque 5: Resumen previo a ejecutar

Mostrar:

1. Universo elegido.
2. Cantidad de personas.
3. Respuestas por persona.
4. Total de respuestas esperadas.

Formula:

`total_respuestas = cantidad_personas * respuestas_por_persona`

### Bloque 6: Accion principal

Boton:

1. `Iniciar estudio`

### Decisiones de interfaz

1. La pregunta debe tener mas protagonismo visual que el contexto.
2. La configuracion avanzada no debe ocupar mas espacio que la pregunta.
3. El usuario tiene que ver el volumen total antes de ejecutar.

## 8.5 Pantalla `Resultados`

### Bloque 1: Resumen general

Mostrar:

1. Nombre del estudio.
2. Universo usado.
3. Pregunta.
4. Contexto.
5. Cantidad de personas.
6. Respuestas por persona.
7. Total de respuestas.

### Bloque 2: Analisis resumido

Mostrar:

1. Principales temas mencionados.
2. Gustos o intereses repetidos.
3. Objeciones repetidas.
4. Diferencias entre perfiles.
5. Sintesis general.

### Bloque 3: Filtros

Filtros minimos:

1. Perfil.
2. Persona.
3. Numero de repeticion.

### Bloque 4: Tabla detallada

Columnas recomendadas:

1. Persona
2. Perfil
3. Repeticion
4. Pregunta
5. Contexto
6. Respuesta
7. Sintesis

### Bloque 5: Descarga

Boton:

1. `Descargar Excel`

### Decisiones de interfaz

1. Primero insight, despues tabla.
2. La tabla debe ser util para auditoria.
3. La descarga debe estar visible sin necesidad de scrollear demasiado.

## 9. Modelo de datos

## 9.1 Universo

```json
{
  "id": "universe_20260420_001",
  "nombre": "Panaderos de Gonzalez Catan",
  "descripcion": "Universo de panaderos y responsables de compra de panaderias barriales.",
  "cantidad_personas": 100,
  "perfiles": [
    {
      "nombre": "Panadero tradicional",
      "descripcion": "Dueño o responsable operativo de panaderia barrial.",
      "porcentaje": 60
    },
    {
      "nombre": "Panaderia de especialidad",
      "descripcion": "Perfil mas enfocado en calidad, marca e innovacion.",
      "porcentaje": 40
    }
  ],
  "created_at": "2026-04-20T10:00:00"
}
```

## 9.2 Estudio

```json
{
  "id": "study_20260420_001",
  "universo_id": "universe_20260420_001",
  "universo_nombre": "Panaderos de Gonzalez Catan",
  "pregunta": "Comprarias este servicio para tu negocio?",
  "contexto": "El servicio promete reducir tiempos de atencion y ordenar pedidos.",
  "respuestas_por_persona": 2,
  "created_at": "2026-04-20T10:30:00"
}
```

## 9.3 Resultado por respuesta

```json
{
  "estudio_id": "study_20260420_001",
  "persona_id": "AG_001",
  "perfil": "Panadero tradicional",
  "repeticion": 1,
  "pregunta": "Comprarias este servicio para tu negocio?",
  "contexto": "El servicio promete reducir tiempos de atencion y ordenar pedidos.",
  "respuesta": "...",
  "sintesis": "..."
}
```

## 10. Estructura de archivos sugerida

No hace falta reescribir toda la app de golpe. Conviene extraer piezas del archivo principal actual.

### Archivos nuevos recomendados

1. `models_universos.py`
   - estructuras de universo, perfil y estudio

2. `storage_universos.py`
   - guardar y leer universos
   - guardar y leer estudios
   - guardar y leer resultados

3. `engine_universos.py`
   - generacion de personas a partir de perfiles
   - expansion del universo segun porcentajes

4. `analysis_results.py`
   - resumenes
   - agregados
   - analisis por perfil

5. `export_excel.py`
   - exportacion a xlsx

6. `ui_universos.py`
   - pantalla de universos

7. `ui_estudio.py`
   - pantalla de estudio

8. `ui_resultados.py`
   - pantalla de resultados

### Archivo principal

`predikpedia.py` o un nuevo `app.py` deberia quedar como orquestador de pantallas, no como contenedor de toda la logica.

## 11. Plan de implementacion por fases

## Fase 0: Reordenamiento sin cambios funcionales

### Objetivo

Ordenar la base actual antes de introducir el flujo nuevo, sin romper ni reemplazar las funcionalidades que ya existen.

### Tareas

1. Extraer rutas, helpers de guardado y lectura, y funciones repetidas a modulos separados.
2. Reducir logica acoplada dentro de `predikpedia.py` y `app_miromodi.py` sin cambiar el resultado visible.
3. Centralizar carpetas de trabajo, archivos de salida y utilidades de lectura y escritura.
4. Separar mejor la logica de interfaz de la logica de datos.
5. Dejar preparada la app para que las nuevas pantallas convivan con los flujos actuales mientras se implementa la migracion.

### Criterio de listo

1. La app mantiene el comportamiento actual.
2. Las rutas y helpers base ya no estan duplicados en varios archivos.
3. La base queda lista para sumar `Universos`, `Estudio` y `Resultados` sin tener que reordenar todo otra vez.

## Fase 1: Base estructural

### Objetivo

Preparar la app para dejar de depender de universos fijos.

### Tareas

1. Definir estructuras de datos para universo, perfil, estudio y resultado.
2. Crear funciones de guardado y lectura en disco.
3. Definir carpeta estable para biblioteca de universos.
4. Definir carpeta estable para estudios y resultados.

### Criterio de listo

1. Se puede guardar y volver a leer un universo simple.
2. Se puede guardar y volver a leer un estudio.

## Fase 2: Constructor de universos

### Objetivo

Permitir crear universos desde interfaz.

### Tareas

1. Crear formulario de universo.
2. Crear lista dinamica de perfiles.
3. Validar porcentaje total.
4. Mostrar resumen del universo.
5. Guardar universo.
6. Listar universos guardados.

### Criterio de listo

1. El usuario puede crear un universo sin tocar codigo.
2. No se puede guardar si los porcentajes no suman 100.
3. El universo aparece en la biblioteca.

## Fase 3: Motor de expansion del universo

### Objetivo

Convertir un universo abstracto en personas sinteticas utilizables por el motor.

### Tareas

1. Repartir la cantidad total de personas segun los porcentajes.
2. Generar personas con el perfil correspondiente.
3. Construir backstory base desde:
   - descripcion general del universo
   - nombre del perfil
   - descripcion del perfil
4. Mantener un identificador unico por persona.

### Criterio de listo

1. Un universo de 100 personas con perfiles 60/40 genera 100 personas con esa composicion.
2. Cada persona tiene perfil y contexto base.

## Fase 4: Pantalla de estudio

### Objetivo

Permitir ejecutar una pregunta sobre un universo guardado.

### Tareas

1. Mostrar universo seleccionado.
2. Campo de pregunta.
3. Campo de contexto adicional.
4. Campo `respuestas por persona` con default 1.
5. Mostrar resumen previo a ejecutar.
6. Guardar metadata del estudio.

### Criterio de listo

1. El usuario puede lanzar un estudio con 1 o mas respuestas por persona.
2. El resumen previo informa el total de respuestas esperadas.

## Fase 5: Ejecucion del estudio

### Objetivo

Producir respuestas y guardarlas de forma ordenada.

### Tareas

1. Iterar por persona del universo expandido.
2. Repetir la misma pregunta la cantidad indicada.
3. Guardar una fila por respuesta.
4. Registrar numero de repeticion.
5. Generar una sintesis breve por respuesta o por persona.
6. Guardar resultados finales en disco.

### Criterio de listo

1. Si `respuestas_por_persona = 1`, cada persona responde una vez.
2. Si `respuestas_por_persona = 3`, cada persona responde tres veces.
3. Los resultados quedan asociados al estudio correcto.

## Fase 6: Pantalla de resultados

### Objetivo

Hacer entendibles los datos sin depender del Excel.

### Tareas

1. Mostrar resumen general.
2. Mostrar cantidad de respuestas totales.
3. Mostrar filtros por perfil, persona y repeticion.
4. Mostrar tabla detallada.
5. Mostrar un analisis basico agregado.

### Criterio de listo

1. El usuario puede revisar el estudio completo dentro de la app.
2. El usuario puede auditar respuestas individuales.

## Fase 7: Exportacion a Excel

### Objetivo

Entregar un archivo util fuera de la app.

### Tareas

1. Exportar hoja `Resumen`.
2. Exportar hoja `Respuestas`.
3. Exportar hoja `Perfiles`.
4. Exportar hoja `Analisis`.
5. Exponer boton de descarga.

### Criterio de listo

1. El Excel se abre correctamente.
2. Las hojas tienen nombres claros.
3. El archivo se entiende sin entrar a la app.

## Fase 8: Pulido visual y de mensajes

### Objetivo

Reducir friccion y mejorar claridad.

### Tareas

1. Revisar espaciados.
2. Revisar orden visual de bloques.
3. Simplificar textos demasiado tecnicos.
4. Mejorar estados vacios.
5. Mejorar mensajes de error y exito.

### Criterio de listo

1. La app se puede usar sin explicacion tecnica previa.
2. Los errores son claros y accionables.

## 12. Flujo principal esperado

## Flujo 1: Crear universo

1. El usuario entra a `Universos`.
2. Completa nombre, descripcion y cantidad.
3. Agrega perfiles.
4. Ajusta porcentajes.
5. Ve el porcentaje total.
6. Guarda el universo.

## Flujo 2: Ejecutar estudio

1. El usuario entra a `Estudio`.
2. Selecciona un universo.
3. Escribe la pregunta.
4. Agrega contexto si quiere.
5. Define `Respuestas por persona`.
6. Ve el total esperado.
7. Inicia el estudio.

## Flujo 3: Revisar y descargar

1. El usuario entra a `Resultados`.
2. Ve resumen e insights.
3. Filtra si hace falta.
4. Revisa la tabla.
5. Descarga el Excel.

## 13. Casos de error a cubrir

1. No hay universos guardados.
2. El porcentaje total no suma 100.
3. El nombre del universo esta vacio.
4. No hay pregunta cargada.
5. El usuario intenta ejecutar sin universo seleccionado.
6. La generacion falla a mitad del estudio.
7. El Excel no puede generarse.

### Mensajes sugeridos

1. `Todavia no hay universos guardados.`
2. `El porcentaje total debe sumar 100 antes de guardar.`
3. `Escribi una pregunta para iniciar el estudio.`
4. `Selecciona un universo para continuar.`
5. `No se pudo completar el estudio. Revisa el ultimo avance guardado.`

## 14. Criterios de aceptacion del producto

La version se considera lista si cumple todo esto:

1. Puedo crear un universo con varios perfiles.
2. Los porcentajes se validan correctamente.
3. El universo se guarda y aparece en la biblioteca.
4. Puedo seleccionar un universo guardado para un estudio.
5. Puedo escribir pregunta y contexto.
6. Puedo dejar `Respuestas por persona` en 1 o subirlo.
7. Cada respuesta queda registrada con su repeticion.
8. Puedo ver resumen y tabla dentro de la app.
9. Puedo descargar un Excel entendible.

## 15. Orden recomendado para ejecutar este plan con Codex

1. Ejecutar Fase 0 de reordenamiento sin cambios funcionales.
2. Crear estructuras de datos y almacenamiento.
3. Implementar pantalla `Universos`.
4. Implementar generacion de personas desde perfiles.
5. Implementar pantalla `Estudio`.
6. Implementar ejecucion con repeticion opcional.
7. Implementar pantalla `Resultados`.
8. Implementar exportacion a Excel.
9. Hacer pulido UX/UI final.

## 16. Prompt sugerido para Codex

Usar este prompt como base para la implementacion:

```text
Quiero implementar la primera version de una app de estudios con perfiles de cliente sobre la base del proyecto actual.

Objetivo funcional:
- Crear universos con nombre, descripcion, cantidad de personas y perfiles de cliente.
- Cada perfil debe tener nombre, descripcion y porcentaje.
- La suma de porcentajes debe ser 100.
- Los universos deben guardarse en una biblioteca reutilizable.
- Debe existir una pantalla de estudio donde se seleccione un universo, se escriba una pregunta, un contexto opcional y la cantidad de respuestas por persona.
- El valor por defecto de respuestas por persona debe ser 1.
- Si el valor es mayor a 1, cada persona debe responder varias veces la misma pregunta.
- Los resultados deben verse dentro de la app y poder descargarse en Excel.

Restricciones:
- Todo en espanol.
- Sin geografia.
- Motor unico.
- Interfaz simple.
- Separar claramente Universos, Estudio y Resultados.

Entregables:
- Estructuras de datos.
- Persistencia de universos y estudios.
- Constructor de universos.
- Pantalla de estudio.
- Guardado de resultados.
- Analisis basico en app.
- Exportacion a Excel.

Segui el archivo PLAN_DESARROLLO_UNIVERSOS_Y_ESTUDIOS.md como fuente principal de verdad.
```

## 17. Nota final

Este plan esta pensado para que la implementacion sea incremental. No obliga a rehacer toda la app en un solo paso. La prioridad es construir primero un flujo correcto, claro y usable, y despues refinar el motor interno si hace falta.
