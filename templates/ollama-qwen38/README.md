# Qwen 3.8 local (Ollama)

Template mínimo para usar el modelo ya disponible en el servidor compartido:

- Endpoint: `http://192.168.1.104:11434/v1`
- Modelo: `qwen3.8:latest` (Qwen 3.5, 27.3B, Q4_K_M)

## Uso

1. Copiar `.env.example` a `.env`.
2. Crear y activar un entorno virtual.
3. Instalar dependencias: `pip install -r requirements.txt`.
4. Ejecutar: `python qwen_local.py`.

El cliente usa la API compatible con OpenAI expuesta por Ollama. Si el proyecto corre fuera de la red local, usá la URL del relay/túnel y el token bearer correspondiente en `LLM_LOCAL_API_KEY`.
