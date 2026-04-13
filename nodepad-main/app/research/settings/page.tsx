import { ResearchSettings } from "@/components/research-settings"
import { requireResearchPageSession } from "@/lib/research-page-auth"
import { loadResearchDashboardServer } from "@/lib/research-server"

export const dynamic = "force-dynamic"

export default async function ResearchSettingsPage() {
  await requireResearchPageSession("/research/settings")
  const data = await loadResearchDashboardServer()
  return <ResearchSettings data={data} />
}
