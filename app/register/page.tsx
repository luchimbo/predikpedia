'use client'

import { useState } from 'react'
import Link from 'next/link'
import { register } from '@/app/auth/actions'

export default function RegisterPage() {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    const password = (e.currentTarget.elements.namedItem('password') as HTMLInputElement).value
    const confirm = (e.currentTarget.elements.namedItem('confirm') as HTMLInputElement).value
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    const formData = new FormData(e.currentTarget)
    const result = await register(formData)
    if (result?.error) {
      setError(result.error)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#05070a]">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="text-3xl font-black tracking-tighter uppercase italic mb-2">
            PREDIK<span className="text-blue-500">PEDIA</span>
          </div>
          <p className="text-gray-500 text-sm">Create your analyst account</p>
        </div>

        <div className="glass rounded-3xl p-8">
          <h1 className="text-xl font-bold mb-6 text-white">Create Account</h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs uppercase tracking-widest text-gray-400 mb-2 block">Email</label>
              <input
                name="email"
                type="email"
                required
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-gray-400 mb-2 block">Password</label>
              <input
                name="password"
                type="password"
                required
                minLength={6}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
                placeholder="Min. 6 characters"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-gray-400 mb-2 block">Confirm Password</label>
              <input
                name="confirm"
                type="password"
                required
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="text-red-400 text-sm bg-red-900/20 border border-red-500/20 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold transition mt-2"
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-blue-400 hover:text-blue-300 transition">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center mt-6">
          <Link href="/" className="text-gray-600 text-xs hover:text-gray-400 transition">
            ← Back to home
          </Link>
        </p>
      </div>
    </div>
  )
}
