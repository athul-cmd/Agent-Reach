import type { Metadata } from 'next'
import { Geist, Geist_Mono, Vazirmatn } from 'next/font/google'
import { MobileWall } from '@/components/mobile-wall'
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });
const vazirmatn = Vazirmatn({
  subsets: ["arabic"],
  variable: "--font-vazirmatn",
  display: "swap",
});

function metadataBaseUrl(): URL {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim()
  if (explicit) {
    return new URL(explicit)
  }

  const vercelProduction = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim()
  if (vercelProduction) {
    return new URL(`https://${vercelProduction}`)
  }

  const vercelPreview = process.env.VERCEL_URL?.trim()
  if (vercelPreview) {
    return new URL(`https://${vercelPreview}`)
  }

  return new URL("http://localhost:3000")
}

export const metadata: Metadata = {
  metadataBase: metadataBaseUrl(),
  title: 'Content Research Studio',
  description: 'A private research workspace for continuous content discovery, clustering, and idea generation.',
  icons: {
    icon: [{ url: '/icon.svg', type: 'image/svg+xml' }],
    apple: '/apple-icon.png',
  },
  openGraph: {
    title: 'Content Research Studio',
    description: 'A private research workspace for continuous content discovery, clustering, and idea generation.',
    url: 'https://example.com',
    siteName: 'Content Research Studio',
    images: [{ url: '/nodepad.jpg', width: 1200, height: 630, alt: 'Content Research Studio' }],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Content Research Studio',
    description: 'A private research workspace for continuous content discovery, clustering, and idea generation.',
    images: ['/nodepad.jpg'],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`font-sans antialiased ${vazirmatn.variable}`} suppressHydrationWarning>
        <MobileWall />
        {children}
      </body>
    </html>
  )
}
