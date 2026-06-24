'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV = [
  { href: '/dashboard', label: 'Home', icon: '⌂' },
  { href: '/dashboard/audiencias', label: 'Audiences', icon: '◉' },
  { href: '/dashboard/estudios', label: 'Studies', icon: '▶' },
  { href: '/dashboard/resultados', label: 'Results', icon: '◈' },
  { href: '/dashboard/reportes', label: 'Reports', icon: '☰' },
  { href: '/dashboard/configuracion', label: 'Settings', icon: '⚙' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-56 flex-shrink-0 bg-[#07090d] border-r border-white/5 flex flex-col">
      <div className="px-6 py-6 border-b border-white/5">
        <div className="text-lg font-black tracking-tighter uppercase italic">
          PREDIK<span className="text-blue-500">PEDIA</span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                  : 'text-gray-500 hover:text-gray-200 hover:bg-white/5'
              }`}
            >
              <span className="text-base w-5 text-center">{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="px-6 py-4 border-t border-white/5">
        <div className="text-[10px] text-gray-700 uppercase tracking-widest">v2.0 · Research Platform</div>
      </div>
    </aside>
  )
}
