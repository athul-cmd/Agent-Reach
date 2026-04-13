import { NextRequest, NextResponse } from "next/server"
import {
  addWritingSamplesServer,
  dispatchDueJobsServer,
  handleIdeaActionServer,
  importLinkedInPostsServer,
  loadResearchDashboardServer,
  queueManualRunServer,
  runSystemVerificationServer,
  upsertResearchProfileServer,
} from "@/lib/research-server"
import { dispatchResearchRoute } from "@/lib/research-route-handler"

const DEFAULT_RESEARCH_API_BASE_URL = "http://127.0.0.1:8877"

function researchApiBaseUrl(): string {
  return (process.env.RESEARCH_API_BASE_URL || DEFAULT_RESEARCH_API_BASE_URL).replace(/\/$/, "")
}

function researchApiConfigured(): boolean {
  return Boolean(process.env.RESEARCH_API_BASE_URL)
}

function researchApiHeaders(request: NextRequest): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": request.headers.get("content-type") || "application/json",
  }
  const token = process.env.RESEARCH_API_ACCESS_TOKEN || ""
  if (token) {
    headers["X-Research-Api-Token"] = token
  }
  return headers
}

function buildTargetUrl(pathSegments: string[], search: string): string {
  const pathname = pathSegments.join("/")
  return `${researchApiBaseUrl()}/${pathname}${search}`
}

async function proxy(request: NextRequest, pathSegments: string[]) {
  if (!researchApiConfigured()) {
    return NextResponse.json(
      { error: "Direct app routes handled this request, but the Python API is not configured for fallback proxying." },
      { status: 501 },
    )
  }
  const targetUrl = buildTargetUrl(pathSegments, request.nextUrl.search)
  const body = request.method === "POST" ? await request.text() : undefined

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: researchApiHeaders(request),
      body,
      cache: "no-store",
    })

    const text = await response.text()
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") || "application/json; charset=utf-8",
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not reach the research API."
    return NextResponse.json({ error: message }, { status: 502 })
  }
}

async function requestPayload(request: NextRequest): Promise<Record<string, unknown>> {
  return request.json().catch(() => ({} as Record<string, unknown>))
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const params = await context.params
  const routed = await dispatchResearchRoute("GET", params.path, {}, {
    loadResearchDashboardServer,
    upsertResearchProfileServer,
    addWritingSamplesServer,
    importLinkedInPostsServer,
    queueManualRunServer,
    handleIdeaActionServer,
    dispatchDueJobsServer,
    runSystemVerificationServer,
  })
  if (routed.kind === "direct") {
    return NextResponse.json(routed.body, { status: routed.status })
  }
  return proxy(request, params.path)
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const params = await context.params
  const routed = await dispatchResearchRoute("POST", params.path, await requestPayload(request), {
    loadResearchDashboardServer,
    upsertResearchProfileServer,
    addWritingSamplesServer,
    importLinkedInPostsServer,
    queueManualRunServer,
    handleIdeaActionServer,
    dispatchDueJobsServer,
    runSystemVerificationServer,
  })
  if (routed.kind === "direct") {
    return NextResponse.json(routed.body, { status: routed.status })
  }
  return proxy(request, params.path)
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      Allow: "GET, POST, OPTIONS",
    },
  })
}
