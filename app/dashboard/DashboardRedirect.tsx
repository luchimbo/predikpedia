'use client'

import { useEffect, useState, useRef } from 'react'

interface DashboardRedirectProps {
  streamlitUrl: string
  userId: string
}

export default function DashboardRedirect({ streamlitUrl, userId }: DashboardRedirectProps) {
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState('Iniciando handshake del sistema...')
  const [isOnline, setIsOnline] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)
  const redirectingRef = useRef(false)

  // Polling to check if Streamlit is online
  useEffect(() => {
    let active = true
    const checkStatus = async () => {
      try {
        const res = await fetch('/api/ping')
        if (!res.ok) return
        const data = await res.json()
        if (data.online && active) {
          setIsOnline(true)
        }
      } catch (err) {
        console.error('Failed to check Streamlit status:', err)
      }
    }

    // Run immediately
    checkStatus()

    // Poll every 3 seconds
    const interval = setInterval(checkStatus, 3000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  // Elapsed time tracker for showing the Render Free Tier tip
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedTime((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Simulated progress bar behavior
  useEffect(() => {
    if (isOnline) {
      // If server is online, jump to 100% and redirect
      setProgress(100)
      setStatusText('Conexión establecida. Redirigiendo al dashboard...')
      
      if (!redirectingRef.current) {
        redirectingRef.current = true
        const timer = setTimeout(() => {
          window.location.href = `${streamlitUrl}?uid=${userId}`
        }, 800)
        return () => clearTimeout(timer)
      }
      return
    }

    // Otherwise, simulate progress up to 90%
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          return 90 // Hold at 90% until isOnline becomes true
        }
        // Increment by a random value between 1 and 3
        const increment = Math.floor(Math.random() * 3) + 1
        const next = prev + increment
        return next > 90 ? 90 : next
      })
    }, 800)

    return () => clearInterval(progressInterval)
  }, [isOnline, streamlitUrl, userId])

  // Update terminology text based on progress
  useEffect(() => {
    if (isOnline) return

    if (progress < 15) {
      setStatusText('Estableciendo conexión segura con el clúster de simulación...')
    } else if (progress < 40) {
      setStatusText('Activando contenedores del servidor (Render free tier spin-up)...')
    } else if (progress < 65) {
      setStatusText('Asignando memoria cognitiva e inicializando agentes psicográficos...')
    } else if (progress < 85) {
      setStatusText('Cargando el entorno de trabajo del usuario y sesión de Supabase...')
    } else {
      setStatusText('Esperando respuesta final del motor Predikpedia...')
    }
  }, [progress, isOnline])

  return (
    <div className="fixed inset-0 z-[9999] bg-[#05070a] flex flex-col items-center justify-center p-6 text-white overflow-hidden select-none">
      {/* Self-contained CSS animations */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes subtlePulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.05); }
        }
        .animate-subtle-pulse {
          animation: subtlePulse 3s ease-in-out infinite;
        }
      `}} />

      {/* Background glow effects */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[350px] h-[350px] bg-purple-600/5 rounded-full blur-[90px] pointer-events-none" />

      {/* Cyber grid lines decoration */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.012)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.012)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />

      <div className="w-full max-w-md text-center z-10 flex flex-col items-center">
        {/* Logo */}
        <div className="text-4xl font-black tracking-tighter uppercase italic mb-10 text-white select-none">
          PREDIK<span className="text-blue-500">PEDIA</span>
        </div>

        {/* Pulsing Visual Indicator */}
        <div className="relative w-28 h-28 mb-8 flex items-center justify-center">
          {/* Rotating outer ring */}
          <div className="absolute inset-0 rounded-full border border-dashed border-blue-500/20 animate-[spin_25s_linear_infinite]" />
          
          {/* Pulsing glow ring */}
          <div className="absolute inset-2 rounded-full border border-blue-500/25 animate-ping duration-1000" />
          
          {/* Glass sphere container */}
          <div className="absolute inset-3 bg-white/[0.02] border border-white/10 rounded-full backdrop-blur-md flex items-center justify-center shadow-inner">
            {isOnline ? (
              <i className="fa-solid fa-circle-check text-green-400 text-3xl animate-bounce" />
            ) : (
              <i className="fa-solid fa-server text-blue-400 text-3xl animate-pulse" />
            )}
          </div>
        </div>

        {/* Progress percent */}
        <div className="text-2xl font-black tracking-tight text-blue-400 mb-2 select-none font-mono">
          {progress}%
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mb-4 border border-white/5 relative">
          <div
            className="bg-blue-500 h-full rounded-full transition-all duration-500 ease-out shadow-[0_0_12px_rgba(59,130,246,0.8)]"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Status Message */}
        <div className="min-h-[24px] px-4">
          <p className="text-sm font-mono text-gray-400 animate-subtle-pulse">
            <span className="text-blue-500 font-bold">&gt;&gt;</span> {statusText}
          </p>
        </div>

        {/* Render Free Tier alert message */}
        <div className="mt-12 h-16 transition-all duration-500 w-full flex justify-center">
          {elapsedTime > 7 && !isOnline && (
            <div className="glass rounded-2xl p-4 border border-blue-500/10 max-w-sm animate-fade-in shadow-lg">
              <p className="text-xs text-blue-300/80 font-mono leading-relaxed text-left flex items-start">
                <i className="fa-solid fa-circle-info mt-0.5 mr-2 text-blue-400 flex-shrink-0" />
                <span>
                  <strong>Nota de Entorno:</strong> El motor se encuentra inactivo (Free Tier de Render). Se está iniciando el contenedor. Esto puede tomar entre 30 y 60 segundos.
                </span>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
