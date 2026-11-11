import { createHmac } from 'node:crypto'
import { createClient } from '@/lib/supabase/server'

export async function POST() {
  const headers = { 'Cache-Control': 'no-store' }
  const supabase = await createClient()
  const { data: { user }, error } = await supabase.auth.getUser()
  if (error || !user) {
    return Response.json({}, { status: 401, headers })
  }
  const secret = process.env.PREDIKPEDIA_HANDOFF_SECRET
  if (!secret || secret.length < 32) {
    return Response.json({}, { status: 503, headers })
  }
  const iat = Math.floor(Date.now() / 1000)
  const claims = { sub: user.id, aud: 'predikpedia-streamlit', iat, exp: iat + 60 }
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64url')
  const signature = createHmac('sha256', secret).update(payload).digest('base64url')
  return Response.json({ token: [payload, signature].join('.') }, { headers })
}
