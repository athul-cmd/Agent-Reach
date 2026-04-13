import { ResearchSettings } from "@/components/research-settings"
import { loadResearchDashboardServer } from "@/lib/research-server"

export const dynamic = "force-dynamic"

export default async function ResearchSettingsPage() {
  const data = await loadResearchDashboardServer()
  return <ResearchSettings data={data} />
}
