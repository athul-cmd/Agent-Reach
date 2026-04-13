import { Suspense } from "react"
import { redirectAuthenticatedResearchUser } from "@/lib/research-page-auth"
import { ResearchLoginClient } from "./login-client"

function LoginFallback() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#030303] px-6 text-muted-foreground">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em]">Loading sign-in…</p>
    </main>
  )
}

export default async function ResearchLoginPage() {
  await redirectAuthenticatedResearchUser("/research")
  return (
    <Suspense fallback={<LoginFallback />}>
      <ResearchLoginClient />
    </Suspense>
  )
}
