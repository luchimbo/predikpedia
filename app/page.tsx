import Link from 'next/link'
import { createClient } from '@/lib/supabase/server'

export default async function Home() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      <div className="hero-glow"></div>

      <div className="text-center z-10 max-w-2xl">
        <div className="text-5xl md:text-7xl font-black tracking-tighter uppercase italic mb-6">
          PREDIK<span className="text-blue-500">PEDIA</span>
        </div>

        <p className="text-gray-400 text-lg md:text-xl mb-12 font-light leading-relaxed">
          AI-powered psychographic simulation platform.<br />
          Predict behavior. Audit honesty. Simulate decisions.
        </p>

        {user ? (
          <Link
            href="/dashboard"
            className="bg-blue-600 hover:bg-blue-700 text-white px-10 py-4 rounded-xl font-bold transition-all transform hover:scale-105 shadow-lg shadow-blue-600/20 text-lg"
          >
            Enter Platform →
          </Link>
        ) : (
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/login"
              className="bg-blue-600 hover:bg-blue-700 text-white px-10 py-4 rounded-xl font-bold transition-all transform hover:scale-105 shadow-lg shadow-blue-600/20 text-lg"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="glass hover:bg-white/5 text-white px-10 py-4 rounded-xl font-bold transition-all text-lg"
            >
              Create Account
            </Link>
          </div>
        )}
      </div>

      <div className="absolute bottom-8 text-[10px] text-gray-700 uppercase tracking-[0.4em]">
        © 2026 PREDIKPEDIA AI LABORATORY
      </div>
    </main>
  )
}
