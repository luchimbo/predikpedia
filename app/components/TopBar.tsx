'use client'

import { logout } from '@/app/auth/actions'

export default function TopBar({ email }: { email: string }) {
  return (
    <header className="h-14 flex-shrink-0 border-b border-white/5 bg-[#07090d]/80 backdrop-blur flex items-center justify-end px-8 gap-4">
      <span className="text-xs text-gray-600">{email}</span>
      <form action={logout}>
        <button
          type="submit"
          className="text-xs text-gray-500 hover:text-white transition px-3 py-1.5 rounded-lg hover:bg-white/5"
        >
          Sign out
        </button>
      </form>
    </header>
  )
}
