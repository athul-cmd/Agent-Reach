import assert from "node:assert/strict"
import test from "node:test"

import { dispatchResearchRoute, normalizeResearchRoutePath } from "./research-route-handler.ts"

function createHandlers() {
  const calls: Array<{ name: string; args: unknown[] }> = []
  return {
    calls,
    handlers: {
      loadResearchDashboardServer: async () => {
        calls.push({ name: "dashboard", args: [] })
        return { available: true }
      },
      upsertResearchProfileServer: async (input: unknown) => {
        calls.push({ name: "profile", args: [input] })
        return { profile: input }
      },
      addWritingSamplesServer: async (payload: unknown) => {
        calls.push({ name: "writing-samples", args: [payload] })
        return { added: 1 }
      },
      importLinkedInPostsServer: async (payload: unknown) => {
        calls.push({ name: "linkedin-import", args: [payload] })
        return { imported: 2 }
      },
      queueManualRunServer: async (payload: unknown) => {
        calls.push({ name: "manual-run", args: [payload] })
        return { ok: true, queued: 1 }
      },
      handleIdeaActionServer: async (ideaId: string, action: string, payload: unknown) => {
        calls.push({ name: "idea-action", args: [ideaId, action, payload] })
        return { idea_id: ideaId, event: action }
      },
      dispatchDueJobsServer: async (options: unknown) => {
        calls.push({ name: "dispatch", args: [options] })
        return { claimed: 1, dispatched: 1 }
      },
      runSystemVerificationServer: async (payload: unknown) => {
        calls.push({ name: "verify", args: [payload] })
        return { status: "ok" }
      },
    },
  }
}

test("normalizeResearchRoutePath strips the api prefix when present", () => {
  assert.deepEqual(normalizeResearchRoutePath(["api", "dashboard"]), ["dashboard"])
  assert.deepEqual(normalizeResearchRoutePath(["system", "verify"]), ["system", "verify"])
})

test("dispatchResearchRoute handles dashboard and profile routes directly", async () => {
  const { handlers, calls } = createHandlers()

  const dashboard = await dispatchResearchRoute("GET", ["api", "dashboard"], {}, handlers)
  const profile = await dispatchResearchRoute(
    "POST",
    ["api", "profile"],
    {
      name: "Founder Voice",
      persona_brief: "Direct",
      niche_definition: "AI systems",
    },
    handlers,
  )

  assert.equal(dashboard.kind, "direct")
  assert.equal(dashboard.status, 200)
  assert.deepEqual(dashboard.body, { available: true })
  assert.equal(profile.kind, "direct")
  assert.deepEqual(profile.body, {
    profile: {
      name: "Founder Voice",
      persona_brief: "Direct",
      niche_definition: "AI systems",
    },
  })
  assert.deepEqual(calls.map((call) => call.name), ["dashboard", "profile"])
})

test("dispatchResearchRoute handles samples, LinkedIn import, and manual runs", async () => {
  const { handlers, calls } = createHandlers()

  const samplePayload = {
    profile_id: "profile_1",
    samples: [{ title: "A", raw_text: "B" }],
  }
  const importPayload = {
    profile_id: "profile_1",
    posts: [{ title: "Post", text: "Body" }],
  }
  const manualPayload = {
    profile_id: "profile_1",
    job: "collect_sources",
  }

  const samples = await dispatchResearchRoute("POST", ["profile", "writing-samples"], samplePayload, handlers)
  const linkedIn = await dispatchResearchRoute("POST", ["profile", "linkedin-import"], importPayload, handlers)
  const manualRun = await dispatchResearchRoute("POST", ["runs", "manual"], manualPayload, handlers)

  assert.equal(samples.kind, "direct")
  assert.deepEqual(samples.body, { added: 1 })
  assert.equal(linkedIn.kind, "direct")
  assert.deepEqual(linkedIn.body, { imported: 2 })
  assert.equal(manualRun.kind, "direct")
  assert.deepEqual(manualRun.body, { ok: true, queued: 1 })
  assert.deepEqual(calls.map((call) => call.name), ["writing-samples", "linkedin-import", "manual-run"])
})

test("dispatchResearchRoute handles idea actions, dispatch, and verification", async () => {
  const { handlers, calls } = createHandlers()

  const saved = await dispatchResearchRoute("POST", ["ideas", "idea_1", "save"], { profile_id: "profile_1" }, handlers)
  const feedback = await dispatchResearchRoute(
    "POST",
    ["ideas", "idea_1", "feedback"],
    { profile_id: "profile_1", note: "Tighter hook" },
    handlers,
  )
  const dispatch = await dispatchResearchRoute("POST", ["system", "dispatch"], {}, handlers)
  const verification = await dispatchResearchRoute(
    "POST",
    ["system", "verify"],
    { mode: "all", profile_id: "profile_1" },
    handlers,
  )

  assert.equal(saved.kind, "direct")
  assert.deepEqual(saved.body, { idea_id: "idea_1", event: "save" })
  assert.equal(feedback.kind, "direct")
  assert.deepEqual(feedback.body, { idea_id: "idea_1", event: "feedback" })
  assert.equal(dispatch.kind, "direct")
  assert.deepEqual(dispatch.body, { claimed: 1, dispatched: 1 })
  assert.equal(verification.kind, "direct")
  assert.deepEqual(verification.body, { verification: { status: "ok" } })
  assert.deepEqual(calls.map((call) => call.name), ["idea-action", "idea-action", "dispatch", "verify"])
  assert.deepEqual(calls[2]?.args[0], { trigger: "manual-dispatch" })
})

test("dispatchResearchRoute returns proxy for unmatched routes", async () => {
  const { handlers } = createHandlers()

  const result = await dispatchResearchRoute("GET", ["system", "health"], {}, handlers)

  assert.deepEqual(result, { kind: "proxy" })
})

test("dispatchResearchRoute maps Unauthorized errors to 401 responses", async () => {
  const { handlers } = createHandlers()
  handlers.queueManualRunServer = async () => {
    throw new Error("Unauthorized.")
  }

  const result = await dispatchResearchRoute("POST", ["runs", "manual"], { job: "collect_sources" }, handlers)

  assert.equal(result.kind, "direct")
  assert.equal(result.status, 401)
  assert.deepEqual(result.body, { error: "Unauthorized." })
})
