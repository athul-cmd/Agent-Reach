import type { ResearchProfileInput } from "./research-api.ts"

export type ResearchRoutePayload = Record<string, unknown>

export type ResearchRouteHandlers = {
  loadResearchDashboardServer: () => Promise<unknown>
  upsertResearchProfileServer: (input: ResearchProfileInput) => Promise<unknown>
  addWritingSamplesServer: (payload: ResearchRoutePayload) => Promise<unknown>
  importLinkedInPostsServer: (payload: ResearchRoutePayload) => Promise<unknown>
  queueManualRunServer: (payload: { profile_id?: string; job: string }) => Promise<unknown>
  handleIdeaActionServer: (
    ideaId: string,
    action: "save" | "discard" | "feedback",
    payload: { profile_id?: string; note?: string },
  ) => Promise<unknown>
  dispatchDueJobsServer: (options?: { trigger?: string }) => Promise<unknown>
  runSystemVerificationServer: (payload: { mode?: string; profile_id?: string | null }) => Promise<unknown>
}

export type RoutedResearchResponse =
  | {
      kind: "direct"
      status: number
      body: unknown
    }
  | {
      kind: "proxy"
    }

export function normalizeResearchRoutePath(pathSegments: string[]): string[] {
  if (pathSegments[0] === "api") return pathSegments.slice(1)
  return pathSegments
}

export function researchRouteError(error: unknown) {
  const message = error instanceof Error ? error.message : "Request failed."
  return {
    status: message === "Unauthorized." ? 401 : 500,
    body: { error: message },
  }
}

export async function dispatchResearchRoute(
  method: "GET" | "POST",
  pathSegments: string[],
  payload: ResearchRoutePayload,
  handlers: ResearchRouteHandlers,
): Promise<RoutedResearchResponse> {
  const directPath = normalizeResearchRoutePath(pathSegments)

  try {
    if (method === "GET") {
      if (directPath.length === 1 && directPath[0] === "dashboard") {
        return {
          kind: "direct",
          status: 200,
          body: await handlers.loadResearchDashboardServer(),
        }
      }
      return { kind: "proxy" }
    }

    if (directPath.length === 1 && directPath[0] === "profile") {
      return {
        kind: "direct",
        status: 200,
        body: await handlers.upsertResearchProfileServer(payload as unknown as ResearchProfileInput),
      }
    }

    if (directPath.length === 2 && directPath[0] === "profile" && directPath[1] === "writing-samples") {
      return {
        kind: "direct",
        status: 200,
        body: await handlers.addWritingSamplesServer(payload),
      }
    }

    if (directPath.length === 2 && directPath[0] === "profile" && directPath[1] === "linkedin-import") {
      return {
        kind: "direct",
        status: 200,
        body: await handlers.importLinkedInPostsServer(payload),
      }
    }

    if (directPath.length === 2 && directPath[0] === "runs" && directPath[1] === "manual") {
      return {
        kind: "direct",
        status: 200,
        body: await handlers.queueManualRunServer(payload as { profile_id?: string; job: string }),
      }
    }

    if (directPath.length === 3 && directPath[0] === "ideas") {
      const action = directPath[2]
      if (action === "save" || action === "discard" || action === "feedback") {
        return {
          kind: "direct",
          status: 200,
          body: await handlers.handleIdeaActionServer(
            directPath[1],
            action,
            payload as { profile_id?: string; note?: string },
          ),
        }
      }
    }

    if (directPath.length === 2 && directPath[0] === "system" && directPath[1] === "dispatch") {
      return {
        kind: "direct",
        status: 200,
        body: await handlers.dispatchDueJobsServer({ trigger: "manual-dispatch" }),
      }
    }

    if (directPath.length === 2 && directPath[0] === "system" && directPath[1] === "verify") {
      return {
        kind: "direct",
        status: 200,
        body: {
          verification: await handlers.runSystemVerificationServer(
            payload as { mode?: string; profile_id?: string | null },
          ),
        },
      }
    }
  } catch (error) {
    const routeError = researchRouteError(error)
    return {
      kind: "direct",
      status: routeError.status,
      body: routeError.body,
    }
  }

  return { kind: "proxy" }
}
