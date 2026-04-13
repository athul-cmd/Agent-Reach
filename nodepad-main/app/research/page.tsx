import { ResearchStudio } from "@/components/research-studio"
import { loadResearchDashboardServer } from "@/lib/research-server"

export const dynamic = "force-dynamic"

export default async function ResearchPage() {
  const data = await loadResearchDashboardServer()
  return <ResearchStudio data={data} />
}
