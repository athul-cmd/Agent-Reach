import assert from "node:assert/strict"
import { createHmac } from "node:crypto"
import test from "node:test"

import {
  buildGitHubDispatchRequest,
  gitHubDispatchErrorMessage,
  githubDispatchConfigured,
  parseQstashJwtClaims,
  verifyQstashSignature,
} from "./research-runtime.ts"

function base64UrlEncode(value: string): string {
  return Buffer.from(value, "utf8").toString("base64url")
}

function signJwt(payload: Record<string, unknown>, key: string): string {
  const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const encodedPayload = base64UrlEncode(JSON.stringify(payload))
  const encoded = `${header}.${encodedPayload}`
  const signature = createHmac("sha256", key).update(encoded).digest("base64url")
  return `${encoded}.${signature}`
}

test("verifyQstashSignature accepts current or next signing keys", () => {
  const payload = { sub: "schedule", iss: "Upstash", topic: "research" }
  const env = {
    QSTASH_CURRENT_SIGNING_KEY: "current-key",
    QSTASH_NEXT_SIGNING_KEY: "next-key",
  }
  const signedWithCurrent = signJwt(payload, env.QSTASH_CURRENT_SIGNING_KEY)
  const signedWithNext = signJwt(payload, env.QSTASH_NEXT_SIGNING_KEY)

  assert.equal(verifyQstashSignature(signedWithCurrent, env), true)
  assert.equal(verifyQstashSignature(signedWithNext, env), true)
  assert.equal(verifyQstashSignature(signJwt(payload, "wrong-key"), env), false)
})

test("parseQstashJwtClaims decodes payloads", () => {
  const token = signJwt({ sub: "schedule", endpoint: "/api/internal/scheduler" }, "current-key")

  assert.deepEqual(parseQstashJwtClaims(token), {
    sub: "schedule",
    endpoint: "/api/internal/scheduler",
  })
  assert.equal(parseQstashJwtClaims("invalid"), null)
})

test("buildGitHubDispatchRequest returns the expected workflow payload", () => {
  const request = buildGitHubDispatchRequest(
    {
      id: "job_123",
      job_type: "collect_sources",
      research_profile_id: "profile_456",
    },
    "scheduler",
    {
      GITHUB_ACTIONS_DISPATCH_TOKEN: "ghs_123",
      GITHUB_ACTIONS_REPO_OWNER: "acme",
      GITHUB_ACTIONS_REPO_NAME: "Agent-Reach",
      GITHUB_ACTIONS_WORKFLOW_FILE: "research-job-runner.yml",
      GITHUB_ACTIONS_WORKFLOW_REF: "main",
    },
  )

  assert.equal(
    request.url,
    "https://api.github.com/repos/acme/Agent-Reach/actions/workflows/research-job-runner.yml/dispatches",
  )
  assert.equal(request.headers.Authorization, "Bearer ghs_123")
  assert.deepEqual(request.body, {
    ref: "main",
    inputs: {
      job_run_id: "job_123",
      job_type: "collect_sources",
      profile_id: "profile_456",
      trigger: "scheduler",
    },
  })
})

test("GitHub dispatch config reports deterministic missing fields", () => {
  const env = {
    GITHUB_ACTIONS_REPO_OWNER: "acme",
    GITHUB_ACTIONS_REPO_NAME: "Agent-Reach",
  }

  assert.equal(githubDispatchConfigured(env), false)
  assert.equal(
    gitHubDispatchErrorMessage(env),
    "GitHub Actions dispatch environment is incomplete. Missing: GITHUB_ACTIONS_DISPATCH_TOKEN.",
  )
  assert.throws(
    () =>
      buildGitHubDispatchRequest(
        {
          id: "job_123",
          job_type: "collect_sources",
          research_profile_id: "profile_456",
        },
        "manual",
        env,
      ),
    /GITHUB_ACTIONS_DISPATCH_TOKEN/,
  )
})
