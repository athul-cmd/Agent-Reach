"use client"

import Link from "next/link"
import { type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { GraphArea } from "@/components/graph-area"
import { KanbanArea } from "@/components/kanban-area"
import { TilingArea } from "@/components/tiling-area"
import type { TextBlock } from "@/components/tile-card"
import {
  addWritingSample,
  discardIdea,
  importLinkedInPosts,
  loadOpenAISettings,
  loadResearchDashboardClient,
  runManualJob,
  runSystemVerification,
  saveIdea,
  sendIdeaFeedback,
  signOutResearchUser,
  type CreatorWatchPayload,
  type OpenAISettingsPayload,
  type ResearchDashboardData,
  type SourceHealthPayload,
  type SourceItemPayload,
  type TopicClusterPayload,
  type VerificationPayload,
} from "@/lib/research-api"
import {
  Activity,
  Database,
  KanbanSquare,
  LayoutGrid,
  KeyRound,
  Orbit,
  RadioTower,
  RefreshCw,
  Sparkles,
  LogOut,
  UserRoundSearch,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react"

type ViewMode = "tiling" | "kanban" | "graph"

const NOOP_ID = (_id: string) => {}
const NOOP_TEXT = (_id: string, _value: string) => {}
const NOOP_TEXT_TYPE = (_id: string, _value: import("@/lib/content-types").ContentType) => {}
const NOOP_REENRICH = (_id: string, _category?: string) => {}
const NOOP_SUBTASK = (_id: string, _subTaskId: string) => {}

function formatScore(score: number): string {
  return score.toFixed(2)
}

function toTimestamp(value: string | null | undefined): number {
  if (!value) return Date.now()
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? Date.now() : timestamp
}

function cleanMarkdownSummary(markdown: string): string {
  return markdown
    .replace(/^#+\s+/gm, "")
    .replace(/\*\*/g, "")
    .trim()
}

function parseLinkedInDraft(value: string): { title?: string; text: string }[] {
  return value
    .split(/\n---+\n/g)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk, index) => {
      const lines = chunk.split("\n")
      const firstLine = lines[0]?.trim() || ""
      if (firstLine.toLowerCase().startsWith("title:")) {
        return {
          title: firstLine.slice("title:".length).trim(),
          text: lines.slice(1).join("\n").trim(),
        }
      }
      return {
        title: `LinkedIn Post ${index + 1}`,
        text: chunk,
      }
    })
    .filter((post) => post.text)
}

function blockSources(itemIds: string[], itemMap: Map<string, SourceItemPayload>) {
  return itemIds
    .map((itemId) => itemMap.get(itemId))
    .filter((item): item is SourceItemPayload => Boolean(item))
    .map((item) => ({
      url: item.canonical_url,
      title: item.title || item.author_name || item.source,
      siteName: item.source,
    }))
    .filter((item) => item.url)
}

function profileBrief(data: ResearchDashboardData): TextBlock | null {
  if (!data.profile) return null
  const profile = data.profile
  const style = data.style_profile
  const lines = [
    `## ${profile.name}`,
    "",
    profile.persona_brief,
    "",
    `- Niche: ${profile.niche_definition}`,
  ]
  if (profile.target_audience) lines.push(`- Audience: ${profile.target_audience}`)
  if (profile.must_track_topics.length) lines.push(`- Must track: ${profile.must_track_topics.join(", ")}`)
  if (profile.desired_formats.length) lines.push(`- Formats: ${profile.desired_formats.join(", ")}`)
  const annotationLines = []
  if (style?.tone_markers.length) annotationLines.push(`Tone markers: ${style.tone_markers.join(", ")}`)
  if (style?.hook_patterns.length) annotationLines.push(`Hook patterns: ${style.hook_patterns.join(", ")}`)
  if (style?.preferred_topics.length) annotationLines.push(`Preferred topics: ${style.preferred_topics.join(", ")}`)
  return {
    id: "research-brief",
    text: lines.join("\n"),
    annotation: annotationLines.join("\n\n"),
    timestamp: toTimestamp(profile.updated_at),
    contentType: "task",
    category: "brief",
    isPinned: true,
  }
}

function clusterBlock(
  cluster: TopicClusterPayload,
  itemMap: Map<string, SourceItemPayload>,
): TextBlock {
  return {
    id: cluster.id,
    text: [
      `## ${cluster.cluster_label}`,
      "",
      cluster.cluster_summary,
      "",
      `- Final score: ${formatScore(cluster.final_score)}`,
      `- Source families: ${cluster.source_family_count}`,
      `- Freshness: ${formatScore(cluster.freshness_score)}`,
    ].join("\n"),
    annotation: [
      `Representative terms: ${cluster.representative_terms.join(", ") || "none"}`,
      `Cluster key: ${cluster.cluster_key}`,
    ].join("\n\n"),
    timestamp: toTimestamp(cluster.rank_snapshot_at),
    contentType: "thesis",
    category: cluster.representative_terms[0] || "cluster",
    isPinned: cluster.final_score >= 0.75,
    influencedBy: [],
    confidence: Math.round(cluster.final_score * 100),
    sources: blockSources(cluster.supporting_item_ids, itemMap),
  }
}

function creatorAnnotation(creators: CreatorWatchPayload[]): string {
  if (!creators.length) return "No creators have been promoted into the watchlist yet."
  return creators
    .slice(0, 8)
    .map(
      (creator) =>
        `- ${creator.creator_name} (${creator.source}, ${formatScore(creator.watch_score)}): ${creator.watch_reason}`,
    )
    .join("\n")
}

function buildBlocks(data: ResearchDashboardData): TextBlock[] {
  const itemMap = new Map(data.source_items.map((item) => [item.id, item]))
  const blocks: TextBlock[] = []
  const brief = profileBrief(data)
  if (brief) blocks.push(brief)

  data.clusters.forEach((cluster) => {
    blocks.push(clusterBlock(cluster, itemMap))
  })

  data.ideas.forEach((idea) => {
    blocks.push({
      id: idea.id,
      text: [`## ${idea.headline}`, "", idea.hook, "", idea.outline_md].join("\n"),
      annotation: [
        `Why now: ${idea.why_now}`,
        `Status: ${idea.status}`,
        `Score: ${formatScore(idea.final_score)}`,
      ].join("\n\n"),
      timestamp: toTimestamp(idea.generated_at),
      contentType: idea.status === "saved" ? "thesis" : "idea",
      category: idea.status,
      influencedBy: [idea.topic_cluster_id],
      confidence: Math.round(idea.final_score * 100),
      isPinned: idea.status === "saved",
      sources: blockSources(idea.evidence_item_ids, itemMap),
    })
  })

  if (data.creators.length) {
    blocks.push({
      id: "creator-watchlist",
      text: [
        "## Creators Worth Watching",
        "",
        ...data.creators.slice(0, 5).map((creator) => `- ${creator.creator_name} (${creator.source})`),
      ].join("\n"),
      annotation: creatorAnnotation(data.creators),
      timestamp: toTimestamp(data.creators[0]?.updated_at),
      contentType: "entity",
      category: "watchlist",
      isPinned: true,
    })
  }

  return blocks
}

function SummarySection({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: LucideIcon
  children: ReactNode
}) {
  return (
    <section className="rounded-sm border border-border/60 bg-card/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/70">
          {title}
        </h2>
      </div>
      {children}
    </section>
  )
}

function statusTone(status: string): string {
  return status === "ok" ? "text-primary" : "text-amber-300"
}

function sourceHealthSummary(source: SourceHealthPayload): string {
  if (!source.available) return "Unavailable on this machine"
  if (source.stale) return "No recent items collected"
  return "Healthy"
}

function sourceNextStep(source: SourceHealthPayload): string {
  if (!source.available) return source.hint || "Install or configure the required source adapter."
  if (source.stale) return "Run verification or trigger a refresh to confirm live collection still works."
  return "No immediate action required."
}

function verificationSummary(result: VerificationPayload | null): string {
  if (!result) return "No verification has been run from the dashboard yet."
  if (result.storage?.database || result.database) {
    const database = result.storage?.database || result.database
    const blob = result.storage?.blob_store || result.blob_store
    const dbStatus = database ? `DB ${database.status}` : ""
    const blobStatus = blob ? `Blob ${blob.status}` : ""
    return [dbStatus, blobStatus].filter(Boolean).join(" • ")
  }
  if (result.sources) {
    const degraded = result.sources.checks.filter((check) => check.status !== "ok").length
    return degraded
      ? `${degraded} source checks need attention`
      : `All ${result.sources.checks.length} source checks passed`
  }
  return result.status
}

function FormInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-sm border border-border/60 bg-black/30 px-3 py-2 text-sm outline-none transition-colors focus:border-primary/60 ${props.className || ""}`}
    />
  )
}

function FormTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-sm border border-border/60 bg-black/30 px-3 py-2 text-sm outline-none transition-colors focus:border-primary/60 ${props.className || ""}`}
    />
  )
}

function ActionButton({
  disabled,
  onClick,
  children,
  primary = false,
}: {
  disabled?: boolean
  onClick: () => void
  children: ReactNode
  primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] disabled:opacity-50 ${
        primary
          ? "border-primary/60 bg-primary/15 text-primary"
          : "border-border/60 bg-card/40 text-foreground"
      }`}
    >
      {children}
    </button>
  )
}

export function ResearchStudio({ data }: { data: ResearchDashboardData }) {
  const [dashboardData, setDashboardData] = useState(data)
  const [openAISettings, setOpenAISettings] = useState<OpenAISettingsPayload | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("tiling")
  const [highlightedBlockId, setHighlightedBlockId] = useState<string | null>(null)
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set())
  const [sampleTitle, setSampleTitle] = useState("")
  const [sampleText, setSampleText] = useState("")
  const [linkedinDraft, setLinkedinDraft] = useState("")
  const [ideaNotes, setIdeaNotes] = useState<Record<string, string>>({})
  const [verificationResult, setVerificationResult] = useState<VerificationPayload | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const blocks = useMemo(() => buildBlocks(dashboardData), [dashboardData])
  const activeProfileId = dashboardData.profile?.id
  const lastRun =
    dashboardData.jobs.find((job) => job.status === "succeeded" || job.status === "failed") ??
    dashboardData.jobs[0] ??
    null
  const reportSummary = dashboardData.report ? cleanMarkdownSummary(dashboardData.report.summary_md) : ""
  const configurationWarnings: string[] = []
  if (!dashboardData.profile) {
    configurationWarnings.push("Research profile is not configured yet.")
  }
  if (openAISettings?.configured === false) {
    configurationWarnings.push("OpenAI key is not configured in Settings.")
  }
  if (settingsError) {
    configurationWarnings.push("Could not load settings metadata from the app.")
  }

  useEffect(() => {
    let cancelled = false

    async function refreshSettings() {
      try {
        const settings = await loadOpenAISettings()
        if (!cancelled) {
          setOpenAISettings(settings)
          setSettingsError(null)
        }
      } catch (error) {
        if (!cancelled) {
          setSettingsError(error instanceof Error ? error.message : "Could not load settings.")
        }
      }
    }

    void refreshSettings()

    return () => {
      cancelled = true
    }
  }, [])

  function toggleCollapse(id: string) {
    setCollapsedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function refreshDashboard(successMessage?: string) {
    try {
      const fresh = await loadResearchDashboardClient()
      setDashboardData(fresh)
      setErrorMessage(null)
      if (successMessage) setStatusMessage(successMessage)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not refresh the dashboard.")
    }
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label)
    setStatusMessage(null)
    setErrorMessage(null)
    try {
      await action()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Action failed.")
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSampleSave() {
    await runAction("writing-sample", async () => {
      await addWritingSample({
        profile_id: activeProfileId,
        title: sampleTitle,
        raw_text: sampleText,
        source_type: "uploaded",
      })
      setSampleTitle("")
      setSampleText("")
      await refreshDashboard("Writing sample added.")
    })
  }

  async function handleLinkedInImport() {
    await runAction("linkedin-import", async () => {
      await importLinkedInPosts({
        profile_id: activeProfileId,
        posts: parseLinkedInDraft(linkedinDraft),
      })
      setLinkedinDraft("")
      await refreshDashboard("LinkedIn posts imported.")
    })
  }

  async function handleRunJob(job: string, _message: string) {
    await runAction(job, async () => {
      const result = await runManualJob({ profile_id: activeProfileId, job }) as {
        queued?: number
        running?: number
        rescheduled?: number
        dispatch?: { dispatched?: number }
      }
      const queued = result.queued ?? 0
      const running = result.running ?? 0
      const rescheduled = result.rescheduled ?? 0
      const dispatched = result.dispatch?.dispatched ?? 0
      const queuedSummary =
        queued > 0
          ? `Queued ${queued} job${queued === 1 ? "" : "s"}${rescheduled > 0 ? ` (${rescheduled} moved to run now)` : ""}.`
          : running > 0
            ? `${running} job${running === 1 ? "" : "s"} already running.`
            : "No new jobs were added."
      const summary =
        dispatched > 0
          ? `${queuedSummary} Dispatched ${dispatched}.`
          : queued > 0 || running > 0
            ? `${queuedSummary} Waiting for background execution.`
            : queuedSummary
      await refreshDashboard(summary)
    })
  }

  async function handleIdeaSave(ideaId: string) {
    await runAction(`save:${ideaId}`, async () => {
      await saveIdea({ profile_id: activeProfileId, idea_id: ideaId })
      await refreshDashboard("Idea saved.")
    })
  }

  async function handleIdeaDiscard(ideaId: string) {
    await runAction(`discard:${ideaId}`, async () => {
      await discardIdea({
        profile_id: activeProfileId,
        idea_id: ideaId,
        note: ideaNotes[ideaId] || "",
      })
      await refreshDashboard("Idea discarded.")
    })
  }

  async function handleIdeaFeedback(ideaId: string) {
    await runAction(`feedback:${ideaId}`, async () => {
      await sendIdeaFeedback({
        profile_id: activeProfileId,
        idea_id: ideaId,
        note: ideaNotes[ideaId] || "",
      })
      await refreshDashboard("Feedback recorded.")
    })
  }

  async function handleVerification(
    mode: "storage" | "sources" | "all",
    runCollect = false,
  ) {
    const label = runCollect ? `verify:${mode}:collect` : `verify:${mode}`
    await runAction(label, async () => {
      const result = await runSystemVerification({
        profile_id: activeProfileId,
        mode,
        run_collect: runCollect,
        limit: 1,
      })
      setVerificationResult(result)
      await refreshDashboard(
        runCollect
          ? "Live verification completed."
          : `${mode === "all" ? "Full" : mode} verification completed.`,
      )
    })
  }

  async function handleLogout() {
    await runAction("logout", async () => {
      await signOutResearchUser()
      window.location.assign("/research/login")
    })
  }

  return (
    <div className="flex min-h-screen bg-[#030303] text-foreground">
      <div className="flex min-h-screen min-w-0 flex-1 flex-col border-r border-border/60">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 bg-card/70 px-6 py-4 backdrop-blur-md">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <RadioTower className="h-4 w-4 text-primary" />
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-primary/80">
                Research Studio
              </p>
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              {dashboardData.profile?.name || "Content Research Dashboard"}
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {dashboardData.profile?.niche_definition ||
                "Create a research profile, add writing memory, and then trigger the pipeline."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setViewMode("tiling")}
              className={`inline-flex items-center gap-2 rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] transition-colors ${
                viewMode === "tiling"
                  ? "border-primary/60 bg-primary/15 text-primary"
                  : "border-border/60 bg-card/40 text-muted-foreground hover:text-foreground"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Canvas
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`inline-flex items-center gap-2 rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] transition-colors ${
                viewMode === "kanban"
                  ? "border-primary/60 bg-primary/15 text-primary"
                  : "border-border/60 bg-card/40 text-muted-foreground hover:text-foreground"
              }`}
            >
              <KanbanSquare className="h-3.5 w-3.5" />
              Board
            </button>
            <button
              onClick={() => setViewMode("graph")}
              className={`inline-flex items-center gap-2 rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] transition-colors ${
                viewMode === "graph"
                  ? "border-primary/60 bg-primary/15 text-primary"
                  : "border-border/60 bg-card/40 text-muted-foreground hover:text-foreground"
              }`}
            >
              <Orbit className="h-3.5 w-3.5" />
              Graph
            </button>
            <button
              onClick={() => {
                void refreshDashboard("Dashboard refreshed.")
              }}
              className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Reload
            </button>
            <Link
              href="/research/settings"
              className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              <RadioTower className="h-3.5 w-3.5" />
              Settings
            </Link>
            <button
              onClick={() => {
                void handleLogout()
              }}
              className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              <LogOut className="h-3.5 w-3.5" />
              Logout
            </button>
          </div>
        </header>

        <div className="grid grid-cols-4 border-b border-border/40 bg-black/20 px-6 py-3">
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/50">Source Items</p>
            <p className="mt-1 text-lg font-semibold">{dashboardData.metrics.source_item_count}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/50">Clusters</p>
            <p className="mt-1 text-lg font-semibold">{dashboardData.metrics.cluster_count}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/50">Ideas</p>
            <p className="mt-1 text-lg font-semibold">{dashboardData.metrics.idea_count}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground/50">Creators</p>
            <p className="mt-1 text-lg font-semibold">{dashboardData.metrics.creator_count}</p>
          </div>
        </div>

        {(busyAction || statusMessage || errorMessage) && (
          <div className="border-b border-border/40 px-6 py-3">
            {busyAction && (
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary/80">
                Working: {busyAction}
              </p>
            )}
            {statusMessage && <p className="mt-1 text-sm text-foreground/80">{statusMessage}</p>}
            {errorMessage && <p className="mt-1 text-sm text-destructive/90">{errorMessage}</p>}
          </div>
        )}

        {configurationWarnings.length > 0 && (
          <div className="border-b border-amber-500/20 bg-amber-500/5 px-6 py-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-amber-300">
                  Settings Attention Needed
                </p>
                <div className="mt-2 space-y-1 text-sm text-amber-100/90">
                  {configurationWarnings.map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </div>
              </div>
              <Link
                href="/research/settings"
                className="inline-flex items-center gap-2 rounded-sm border border-amber-500/30 bg-black/20 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-amber-100 transition-colors hover:border-amber-400/50"
              >
                <RadioTower className="h-3.5 w-3.5" />
                Open Settings
              </Link>
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1">
          {!dashboardData.available ? (
            <div className="flex h-full items-center justify-center px-6">
              <div className="max-w-2xl rounded-sm border border-border/60 bg-card/40 p-6">
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-primary/80">
                  Research API Offline
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  This page expects the Python research API to be reachable at{" "}
                  <code className="rounded bg-black/40 px-1.5 py-0.5 text-foreground">
                    {dashboardData.apiBaseUrl}
                  </code>
                  .
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  Start it with{" "}
                  <code className="rounded bg-black/40 px-1.5 py-0.5 text-foreground">
                    agent-reach research serve
                  </code>{" "}
                  and then reload this page.
                </p>
                {dashboardData.error && (
                  <p className="mt-3 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive/90">
                    {dashboardData.error}
                  </p>
                )}
              </div>
            </div>
          ) : viewMode === "tiling" ? (
            <TilingArea
              blocks={blocks}
              readOnly={true}
              collapsedIds={collapsedIds}
              onDelete={NOOP_ID}
              onEdit={NOOP_TEXT}
              onEditAnnotation={NOOP_TEXT}
              onReEnrich={NOOP_REENRICH}
              onChangeType={NOOP_TEXT_TYPE}
              onToggleCollapse={toggleCollapse}
              onTogglePin={NOOP_ID}
              onToggleSubTask={NOOP_SUBTASK}
              onDeleteSubTask={NOOP_SUBTASK}
              highlightedBlockId={highlightedBlockId}
              onHighlight={setHighlightedBlockId}
            />
          ) : viewMode === "kanban" ? (
            <KanbanArea
              blocks={blocks}
              readOnly={true}
              onDelete={NOOP_ID}
              onEdit={NOOP_TEXT}
              onEditAnnotation={NOOP_TEXT}
              onReEnrich={NOOP_REENRICH}
              onChangeType={NOOP_TEXT_TYPE}
              onToggleCollapse={toggleCollapse}
              onTogglePin={NOOP_ID}
              onToggleSubTask={NOOP_SUBTASK}
              onDeleteSubTask={NOOP_SUBTASK}
              collapsedIds={collapsedIds}
            />
          ) : (
            <GraphArea
              blocks={blocks}
              readOnly={true}
              projectName={dashboardData.profile?.name || "Research Studio"}
              onReEnrich={NOOP_REENRICH}
              onChangeType={NOOP_TEXT_TYPE}
              onTogglePin={NOOP_ID}
              onEdit={NOOP_TEXT}
              onEditAnnotation={NOOP_TEXT}
              highlightedBlockId={highlightedBlockId}
              onHighlight={setHighlightedBlockId}
            />
          )}
        </div>
      </div>

      <aside className="hidden w-[380px] shrink-0 flex-col gap-4 overflow-y-auto bg-[#050505] p-5 xl:flex">
        <SummarySection title="Writing Memory" icon={Workflow}>
          <div className="space-y-3 text-sm">
            <FormInput
              value={sampleTitle}
              onChange={(event) => setSampleTitle(event.target.value)}
              placeholder="Writing sample title"
            />
            <FormTextarea
              value={sampleText}
              onChange={(event) => setSampleText(event.target.value)}
              placeholder="Paste a writing sample"
              className="min-h-[112px]"
            />
            <ActionButton
              onClick={() => void handleSampleSave()}
              disabled={busyAction !== null || !activeProfileId || !sampleTitle.trim() || !sampleText.trim()}
            >
              Add Writing Sample
            </ActionButton>
            <FormTextarea
              value={linkedinDraft}
              onChange={(event) => setLinkedinDraft(event.target.value)}
              placeholder={"Paste LinkedIn posts. Separate posts with\n---\nOptionally start a post with 'Title: ...'."}
              className="min-h-[128px]"
            />
            <ActionButton
              onClick={() => void handleLinkedInImport()}
              disabled={busyAction !== null || !activeProfileId || !linkedinDraft.trim()}
            >
              Import LinkedIn Posts
            </ActionButton>
          </div>
        </SummarySection>

        <SummarySection title="Manual Runs" icon={RefreshCw}>
          <div className="space-y-2">
            <ActionButton
              onClick={() => void handleRunJob("all", "Full refresh completed.")}
              disabled={busyAction !== null || !activeProfileId}
              primary={true}
            >
              Run Full Refresh
            </ActionButton>
            <ActionButton
              onClick={() => void handleRunJob("refresh_style_profile", "Style profile refreshed.")}
              disabled={busyAction !== null || !activeProfileId}
            >
              Refresh Style Profile
            </ActionButton>
            <ActionButton
              onClick={() => void handleRunJob("publish_weekly_digest", "Weekly digest published.")}
              disabled={busyAction !== null || !activeProfileId}
            >
              Publish Weekly Digest
            </ActionButton>
          </div>
        </SummarySection>

        <SummarySection title="Weekly Digest" icon={Sparkles}>
          {dashboardData.report ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/60">
                <span>{new Date(dashboardData.report.report_period_start).toLocaleDateString()}</span>
                <span>{new Date(dashboardData.report.report_period_end).toLocaleDateString()}</span>
              </div>
              <div className="prose prose-invert max-w-none text-sm leading-relaxed prose-p:text-foreground/80 prose-li:text-foreground/80">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{dashboardData.report.summary_md}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              No weekly digest has been published yet. Run the pipeline and then publish the weekly digest job.
            </p>
          )}
        </SummarySection>

        <SummarySection title="Settings Status" icon={KeyRound}>
          <div className="space-y-3 text-sm text-foreground/80">
            <div className="rounded-sm border border-border/50 bg-black/20 p-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                Research Profile
              </p>
              <p className="mt-2">{dashboardData.profile ? "Configured" : "Missing"}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {dashboardData.profile
                  ? dashboardData.profile.niche_definition
                  : "Define your niche, audience, and formats from the settings page."}
              </p>
            </div>
            <div className="rounded-sm border border-border/50 bg-black/20 p-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                OpenAI Key
              </p>
              <p className="mt-2">
                {openAISettings
                  ? openAISettings.configured
                    ? "Configured"
                    : "Missing"
                  : "Checking status..."}
              </p>
              {openAISettings?.configured && openAISettings.masked_value && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Stored server-side as {openAISettings.masked_value}
                </p>
              )}
              {!openAISettings?.configured && !settingsError && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Add the model key from the settings page so background jobs can generate ideas.
                </p>
              )}
              {settingsError && (
                <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive/90">
                  {settingsError}
                </p>
              )}
            </div>
            <Link
              href="/research/settings"
              className="inline-flex w-full items-center justify-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              <RadioTower className="h-3.5 w-3.5" />
              Manage Settings
            </Link>
          </div>
        </SummarySection>

        <SummarySection title="Style Signals" icon={Workflow}>
          {dashboardData.style_profile ? (
            <div className="space-y-3 text-sm text-foreground/80">
              <p>{dashboardData.style_profile.raw_summary}</p>
              <div>
                <p className="mb-1 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">Tone</p>
                <p>{dashboardData.style_profile.tone_markers.join(", ") || "No tone markers yet."}</p>
              </div>
              <div>
                <p className="mb-1 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">Hooks</p>
                <p>{dashboardData.style_profile.hook_patterns.join(", ") || "No hook patterns yet."}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              No style profile exists yet. Add writing samples or LinkedIn posts, then run the style refresh job.
            </p>
          )}
        </SummarySection>

        <SummarySection title="Idea Actions" icon={Sparkles}>
          {dashboardData.ideas.length ? (
            <div className="space-y-3">
              {dashboardData.ideas.slice(0, 6).map((idea) => (
                <div key={idea.id} className="rounded-sm border border-border/50 bg-black/20 p-3">
                  <p className="text-sm font-medium text-foreground">{idea.headline}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{idea.hook}</p>
                  <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.16em] text-primary/80">
                    {idea.status} • {formatScore(idea.final_score)}
                  </p>
                  <FormTextarea
                    value={ideaNotes[idea.id] || ""}
                    onChange={(event) =>
                      setIdeaNotes((prev) => ({ ...prev, [idea.id]: event.target.value }))
                    }
                    placeholder="Optional reason or feedback note"
                    className="mt-3 min-h-[72px]"
                  />
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <ActionButton
                      onClick={() => void handleIdeaSave(idea.id)}
                      disabled={busyAction !== null || !activeProfileId}
                      primary={true}
                    >
                      Save
                    </ActionButton>
                    <ActionButton
                      onClick={() => void handleIdeaDiscard(idea.id)}
                      disabled={busyAction !== null || !activeProfileId}
                    >
                      Discard
                    </ActionButton>
                    <ActionButton
                      onClick={() => void handleIdeaFeedback(idea.id)}
                      disabled={busyAction !== null || !activeProfileId || !(ideaNotes[idea.id] || "").trim()}
                    >
                      Feedback
                    </ActionButton>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              No idea cards are available yet.
            </p>
          )}
        </SummarySection>

        <SummarySection title="Creators" icon={UserRoundSearch}>
          {dashboardData.creators.length ? (
            <div className="space-y-3">
              {dashboardData.creators.slice(0, 8).map((creator) => (
                <div key={creator.id} className="rounded-sm border border-border/50 bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">{creator.creator_name}</p>
                    <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary/80">
                      {creator.source}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{creator.watch_reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              Creator discovery has not produced a watchlist yet.
            </p>
          )}
        </SummarySection>

        <SummarySection title="Run State" icon={RefreshCw}>
          <div className="space-y-3 text-sm text-foreground/80">
            <p>
              API target:{" "}
              <code className="rounded bg-black/40 px-1.5 py-0.5 text-[12px] text-foreground">
                {dashboardData.apiBaseUrl}
              </code>
            </p>
            {lastRun ? (
              <>
                <p>Latest job: <span className="text-foreground">{lastRun.job_type}</span></p>
                <p>Status: <span className="text-foreground">{lastRun.status}</span></p>
                <p>Scheduled: <span className="text-foreground">{new Date(lastRun.scheduled_for).toLocaleString()}</span></p>
                {lastRun.error_summary && (
                  <p className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive/90">
                    {lastRun.error_summary}
                  </p>
                )}
              </>
            ) : (
              <p>No job history is available yet.</p>
            )}
            {reportSummary && (
              <div className="rounded-sm border border-border/50 bg-black/20 p-3">
                <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                  Weekly Summary Snapshot
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">{reportSummary}</p>
              </div>
            )}
          </div>
        </SummarySection>

        <SummarySection title="System Health" icon={Activity}>
          {dashboardData.system_health ? (
            <div className="space-y-4 text-sm text-foreground/80">
              <div className="rounded-sm border border-border/50 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground/60">
                    Overall
                  </p>
                  <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusTone(dashboardData.system_health.status)}`}>
                    {dashboardData.system_health.status}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Scheduler state:{" "}
                  <span className={statusTone(dashboardData.system_health.worker.status)}>
                    {dashboardData.system_health.worker.state}
                  </span>
                  {dashboardData.system_health.worker.note
                    ? ` • ${dashboardData.system_health.worker.note}`
                    : ""}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Failed jobs: {dashboardData.system_health.jobs.failed_job_count} • Pending jobs:{" "}
                  {dashboardData.system_health.jobs.pending_job_count}
                </p>
              </div>

              <div>
                <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                  Source Availability
                </p>
                <div className="space-y-2">
                  {dashboardData.system_health.sources.map((source) => (
                    <div key={source.source} className="rounded-sm border border-border/50 bg-black/20 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground">{source.source}</p>
                        <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusTone(source.status)}`}>
                          {source.status}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        {sourceHealthSummary(source)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground/80">
                        {source.hint}
                      </p>
                      <p className="mt-1 text-xs text-foreground/70">
                        Next step: {sourceNextStep(source)}
                      </p>
                      <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                        Items: {source.item_count}
                        {source.latest_published_at
                          ? ` • Latest: ${new Date(source.latest_published_at).toLocaleDateString()}`
                          : ""}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                  Storage
                </p>
                <div className="rounded-sm border border-border/50 bg-black/20 p-3 text-xs leading-relaxed text-muted-foreground">
                  <p>DB: {dashboardData.system_health.storage.db_backend || dashboardData.system_health.storage.database}</p>
                  <p>Blob: {dashboardData.system_health.storage.blob_backend || dashboardData.system_health.storage.blob_store}</p>
                  {dashboardData.system_health.worker.last_update_at && (
                    <p>
                      Last scheduler update:{" "}
                      {new Date(dashboardData.system_health.worker.last_update_at).toLocaleString()}
                    </p>
                  )}
                  {dashboardData.system_health.worker.last_error && (
                    <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive/90">
                      Last background error: {dashboardData.system_health.worker.last_error}
                    </p>
                  )}
                </div>
              </div>

              <div>
                <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                  Recent Job Status
                </p>
                <div className="space-y-2">
                  {dashboardData.system_health.jobs.latest_jobs.length ? (
                    dashboardData.system_health.jobs.latest_jobs.map((job) => (
                      <div key={job.job_type} className="rounded-sm border border-border/50 bg-black/20 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium text-foreground">{job.job_type}</p>
                          <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusTone(job.status === "failed" ? "degraded" : "ok")}`}>
                            {job.status}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">
                          Scheduled: {new Date(job.scheduled_for).toLocaleString()}
                        </p>
                        {job.error_summary && (
                          <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive/90">
                            {job.error_summary}
                          </p>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      No job-level health entries are available yet.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted-foreground">
              Health telemetry is not available yet.
            </p>
          )}
        </SummarySection>

        <SummarySection title="Operations" icon={Wrench}>
          <div className="space-y-3 text-sm text-foreground/80">
            <div className="grid grid-cols-2 gap-2">
              <ActionButton
                onClick={() => void handleVerification("storage")}
                disabled={busyAction !== null}
              >
                Verify Storage
              </ActionButton>
              <ActionButton
                onClick={() => void handleVerification("sources")}
                disabled={busyAction !== null}
              >
                Verify Sources
              </ActionButton>
              <ActionButton
                onClick={() => void handleVerification("all")}
                disabled={busyAction !== null}
                primary={true}
              >
                Verify All
              </ActionButton>
              <ActionButton
                onClick={() => void handleVerification("sources", true)}
                disabled={busyAction !== null || !activeProfileId}
              >
                Source Smoke
              </ActionButton>
            </div>

            <div className="rounded-sm border border-border/50 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                  Latest Verification
                </p>
                <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusTone(verificationResult?.status || "degraded")}`}>
                  {verificationResult?.status || "not-run"}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {verificationSummary(verificationResult)}
              </p>
              {verificationResult?.generated_at && (
                <p className="mt-2 text-xs text-muted-foreground/80">
                  Verified at {new Date(verificationResult.generated_at).toLocaleString()}
                </p>
              )}
            </div>

            {verificationResult?.storage && (
              <div className="rounded-sm border border-border/50 bg-black/20 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <Database className="h-4 w-4 text-primary" />
                  <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                    Storage Verification
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">
                  DB: {verificationResult.storage.database?.backend} •{" "}
                  {verificationResult.storage.database?.status}
                </p>
                {verificationResult.storage.database?.error && (
                  <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive/90">
                    {verificationResult.storage.database.error}
                  </p>
                )}
                {verificationResult.storage.database?.missing_fields?.length ? (
                  <p className="mt-2 text-xs text-amber-100/80">
                    Missing: {verificationResult.storage.database.missing_fields.join(", ")}
                  </p>
                ) : null}
                {verificationResult.storage.database?.remediation_hint && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {verificationResult.storage.database.remediation_hint}
                  </p>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  Blob: {verificationResult.storage.blob_store?.backend} •{" "}
                  {verificationResult.storage.blob_store?.status}
                </p>
                {verificationResult.storage.blob_store?.error && (
                  <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive/90">
                    {verificationResult.storage.blob_store.error}
                  </p>
                )}
                {verificationResult.storage.blob_store?.missing_fields?.length ? (
                  <p className="mt-2 text-xs text-amber-100/80">
                    Missing: {verificationResult.storage.blob_store.missing_fields.join(", ")}
                  </p>
                ) : null}
                {verificationResult.storage.blob_store?.remediation_hint && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {verificationResult.storage.blob_store.remediation_hint}
                  </p>
                )}
              </div>
            )}

            {verificationResult?.sources && (
              <div className="space-y-2">
                {verificationResult.sources.checks.map((check) => (
                  <div key={check.source} className="rounded-sm border border-border/50 bg-black/20 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-foreground">{check.source}</p>
                      <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${statusTone(check.status)}`}>
                        {check.status}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{check.hint}</p>
                    {typeof check.sample_count === "number" && (
                      <p className="mt-2 text-xs text-foreground/80">
                        Sample items returned: {check.sample_count}
                      </p>
                    )}
                    {check.error && (
                      <p className="mt-2 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive/90">
                        {check.error}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </SummarySection>
      </aside>
    </div>
  )
}
