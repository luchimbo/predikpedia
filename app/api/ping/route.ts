import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  const streamlitUrl = process.env.NEXT_PUBLIC_STREAMLIT_URL
  if (!streamlitUrl || streamlitUrl === '#') {
    return NextResponse.json(
      { online: false, error: 'Streamlit URL not configured' },
      { status: 400 }
    )
  }

  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 3500)

    // Streamlit health check endpoint returns "ok" as raw text when awake.
    // If Render is sleeping, it returns Render's "Service Waking Up" HTML page.
    const healthUrl = `${streamlitUrl.replace(/\/$/, '')}/_stcore/health`
    
    const response = await fetch(healthUrl, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'text/plain, */*'
      },
      cache: 'no-store'
    })

    clearTimeout(timeoutId)

    if (response.ok) {
      const text = await response.text()
      const isOk = text.trim() === 'ok'
      return NextResponse.json({ online: isOk })
    }

    return NextResponse.json({ online: false })
  } catch (error) {
    const isTimeout = error instanceof Error && error.name === 'AbortError'
    return NextResponse.json({ 
      online: false, 
      error: isTimeout ? 'Timeout' : (error instanceof Error ? error.message : String(error)) 
    })
  }
}
