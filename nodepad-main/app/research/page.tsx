import { ResearchStudio } from "@/components/research-studio"
import { requireResearchPageSession } from "@/lib/research-page-auth"
import { loadResearchDashboardServer } from "@/lib/research-server"

export const dynamic = "force-dynamic"

export default async function ResearchPage() {
  await requireResearchPageSession("/research")
  const data = await loadResearchDashboardServer()
  return <ResearchStudio data={data} />
}
