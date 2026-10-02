# Rotacion de Ollama y OpenRouter

Render ejecuta Streamlit y las llamadas LLM. Vercel solo hospeda el portal Next.js que redirige a Streamlit; sus variables no controlan este router.

## Configuracion

`LLM_PROVIDER=schedule` usa Ollama desde las 09:30 (inclusive) hasta las 17:30 (exclusiva) de `America/Argentina/Buenos_Aires`; luego usa OpenRouter. Los valores `local` y `openrouter` fuerzan el proveedor. No se admite `LLM_BASE_URL`.

Los procesos locales usan `LLM_LOCAL_BASE_URL=http://192.168.1.104:11434/v1`. Render recibe la URL temporal `https://...trycloudflare.com/v1`, creada por el relay. El mismo secreto de `LLM_RELAY_BEARER_TOKEN` debe ser `LLM_LOCAL_API_KEY` en Render.

## Relay y Quick Tunnel (Windows)

1. Copiar `.env.relay.example` a `.env.relay.local` y cargar `LLM_RELAY_BEARER_TOKEN`, `RENDER_API_KEY`, `RENDER_SERVICE_ID` y `OPENROUTER_MODEL`. No subir ese archivo.
2. Ejecutar `./scripts/start_llm_relay_and_tunnel.ps1` en PowerShell.
3. El relay escucha solo en `127.0.0.1:3100`; cloudflared es el unico proceso expuesto. El supervisor detecta cada URL Quick Tunnel, actualiza Render y redeploya solo si cambia `LLM_LOCAL_BASE_URL`.

Antes del primer redeploy, probar en orden: Ollama LAN directo, relay con bearer valido e invalido, URL Quick Tunnel autenticada y por ultimo el supervisor/Render. El supervisor solo detiene los procesos que inició.

`trycloudflare.com` es temporal y cambia al reiniciar. Para produccion estable, usar Cloudflare Tunnel administrado con hostname propio y reemplazar la URL temporal en Render.
