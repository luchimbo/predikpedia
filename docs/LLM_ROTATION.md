# Rotacion de Ollama y OpenRouter

Render ejecuta Streamlit y las llamadas LLM. Vercel solo hospeda el portal Next.js que redirige a Streamlit; sus variables no controlan este router.

## Configuracion

`LLM_PROVIDER=local` (por defecto) intenta Ollama las 24 horas. Cada respuesta tiene un único intento local de hasta 60 segundos en total (o el timeout del llamador, si es menor), sin reintentos del SDK. Si no termina a tiempo, se cancela la solicitud HTTP local y se usa OpenRouter con los mismos prompts y temperatura. Los errores locales también activan el respaldo inmediatamente. La siguiente respuesta vuelve a intentar Ollama; no se cambia permanentemente de proveedor. Ollama puede seguir calculando en el servidor aunque el cliente cierre la conexión.

OpenRouter conserva el timeout y el número de intentos del llamador: los 60 segundos son el límite de espera de Ollama, no el tiempo total incluyendo el respaldo. `get_request_metadata()` registra el proveedor final, el modelo y `fallback_reason` (`local_timeout` o `local_error`).

`LLM_PROVIDER=openrouter` fuerza OpenRouter. Se mantiene `schedule` como modo opcional compatible: usa Ollama de 09:30 (inclusive) a 17:30 (exclusiva), en `America/Argentina/Buenos_Aires`, y OpenRouter fuera de esa franja. Sus intentos locales tienen el mismo límite y respaldo. Tanto `render.yaml` como el supervisor del túnel configuran `local`. No se admite `LLM_BASE_URL`.

Los procesos locales usan `LLM_LOCAL_BASE_URL=http://192.168.1.104:11434/v1`. Render recibe la URL temporal `https://...trycloudflare.com/v1`, creada por el relay. El mismo secreto de `LLM_RELAY_BEARER_TOKEN` debe ser `LLM_LOCAL_API_KEY` en Render.

## Relay y Quick Tunnel (Windows)

1. Copiar `.env.relay.example` a `.env.relay.local` y cargar `LLM_RELAY_BEARER_TOKEN`, `RENDER_API_KEY`, `RENDER_SERVICE_ID` y `OPENROUTER_MODEL`. No subir ese archivo.
2. Ejecutar `./scripts/start_llm_relay_and_tunnel.ps1` en PowerShell.
3. El relay escucha solo en `127.0.0.1:3100`; cloudflared es el unico proceso expuesto. El supervisor detecta cada URL Quick Tunnel, actualiza Render y redeploya solo si cambia `LLM_LOCAL_BASE_URL`.

Antes del primer redeploy, probar en orden: Ollama LAN directo, relay con bearer valido e invalido, URL Quick Tunnel autenticada y por ultimo el supervisor/Render. El supervisor solo detiene los procesos que inició.

`trycloudflare.com` es temporal y cambia al reiniciar. Para produccion estable, usar Cloudflare Tunnel administrado con hostname propio y reemplazar la URL temporal en Render.
