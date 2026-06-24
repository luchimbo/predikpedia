import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

const STREAMLIT_URL = process.env.NEXT_PUBLIC_STREAMLIT_URL || '#'

export default async function DashboardPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  // Once Streamlit URL is set, redirect directly
  if (STREAMLIT_URL !== '#') {
    redirect(STREAMLIT_URL)
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#05070a] px-4">
      <div className="text-center max-w-md">
        <div className="text-3xl font-black tracking-tighter uppercase italic mb-6">
          PREDIK<span className="text-blue-500">PEDIA</span>
        </div>
        <div className="glass rounded-2xl p-8">
          <div className="text-yellow-400 text-2xl mb-4">⚙</div>
          <h2 className="text-white font-bold text-lg mb-2">App launching soon</h2>
          <p className="text-gray-500 text-sm">
            The simulation platform is being deployed. Once it&apos;s live, you&apos;ll be redirected automatically.
          </p>
        </div>
        <p className="text-gray-700 text-xs mt-6">Logged in as {user.email}</p>
      </div>
    </main>
  )
}
