import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Accounts Payable Platform',
  description: 'PO-backed invoice processing platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

