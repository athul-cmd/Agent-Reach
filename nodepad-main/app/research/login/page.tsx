import { Suspense } from "react"
import { ResearchLoginClient } from "./login-client"

function LoginFallback() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#030303] px-6 text-muted-foreground">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em]">Loading sign-in…</p>
    </main>
  )
}

export default function ResearchLoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <ResearchLoginClient />
    </Suspense>
  )
}
