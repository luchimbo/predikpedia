import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Predikpedia | Honesty Audit for Global Strategy',
  description: 'The world\'s first AI platform powered by Psychographic Agents to audit voting honesty and predict behavior during real-time crises.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet" />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  )
}
