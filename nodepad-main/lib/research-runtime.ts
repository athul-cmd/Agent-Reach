import { createHmac, timingSafeEqual } from "node:crypto"

export const DIRECT_RESEARCH_API_BASE_URL = "managed://supabase"
type EnvLike = Record<string, string | undefined>

export type DispatchJobInput = {
  id: string
  job_type: string
  research_profile_id: string
}

export type GitHubDispatchConfig = {
  token: string
  owner: string
  repo: string
  workflow: string
  ref: string
}

function requiredValue(env: EnvLike, key: string): string {
  return String(env[key] || "").trim()
}

export function githubDispatchConfigFromEnv(env: EnvLike = process.env): GitHubDispatchConfig {
  return {
    token: requiredValue(env, "GITHUB_ACTIONS_DISPATCH_TOKEN") || requiredValue(env, "GH_WORKFLOW_DISPATCH_TOKEN"),
    owner: requiredValue(env, "GITHUB_ACTIONS_REPO_OWNER"),
    repo: requiredValue(env, "GITHUB_ACTIONS_REPO_NAME"),
    workflow: requiredValue(env, "GITHUB_ACTIONS_WORKFLOW_FILE") || "research-job-runner.yml",
    ref:
      requiredValue(env, "GITHUB_ACTIONS_WORKFLOW_REF") ||
      requiredValue(env, "VERCEL_GIT_COMMIT_REF") ||
      "main",
  }
}

export function missingGitHubDispatchFields(
  config: GitHubDispatchConfig,
  env: EnvLike = process.env,
): string[] {
  const missing: string[] = []
  if (!config.token) {
    missing.push(env.GITHUB_ACTIONS_DISPATCH_TOKEN ? "GH_WORKFLOW_DISPATCH_TOKEN" : "GITHUB_ACTIONS_DISPATCH_TOKEN")
  }
  if (!config.owner) missing.push("GITHUB_ACTIONS_REPO_OWNER")
  if (!config.repo) missing.push("GITHUB_ACTIONS_REPO_NAME")
  if (!config.workflow) missing.push("GITHUB_ACTIONS_WORKFLOW_FILE")
  if (!config.ref) missing.push("GITHUB_ACTIONS_WORKFLOW_REF")
  return missing
}

export function githubDispatchConfigured(env: EnvLike = process.env): boolean {
  return missingGitHubDispatchFields(githubDispatchConfigFromEnv(env), env).length === 0
}

export function gitHubDispatchErrorMessage(env: EnvLike = process.env): string {
  const missing = missingGitHubDispatchFields(githubDispatchConfigFromEnv(env), env)
  if (!missing.length) return ""
  return `GitHub Actions dispatch environment is incomplete. Missing: ${missing.join(", ")}.`
}

export function buildGitHubDispatchRequest(
  job: DispatchJobInput,
  trigger: string,
  env: EnvLike = process.env,
) {
  const config = githubDispatchConfigFromEnv(env)
  const missing = missingGitHubDispatchFields(config, env)
  if (missing.length) {
    throw new Error(gitHubDispatchErrorMessage(env))
  }
  return {
    url: `https://api.github.com/repos/${config.owner}/${config.repo}/actions/workflows/${config.workflow}/dispatches`,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${config.token}`,
      "Content-Type": "application/json",
      "User-Agent": "research-studio-scheduler",
    },
    body: {
      ref: config.ref,
      inputs: {
        job_run_id: job.id,
        job_type: job.job_type,
        profile_id: job.research_profile_id,
        trigger,
      },
    },
  }
}

function base64UrlDecode(input: string): Buffer {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/")
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4))
  return Buffer.from(`${normalized}${padding}`, "base64")
}

function base64UrlEncode(input: Buffer): string {
  return input.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "")
}

function secureEqual(leftValue: string, rightValue: string): boolean {
  const left = Buffer.from(leftValue)
  const right = Buffer.from(rightValue)
  if (left.length !== right.length) return false
  return timingSafeEqual(left, right)
}

export function qstashSigningKeysFromEnv(env: EnvLike = process.env): string[] {
  return [requiredValue(env, "QSTASH_CURRENT_SIGNING_KEY"), requiredValue(env, "QSTASH_NEXT_SIGNING_KEY")].filter(
    Boolean,
  )
}

export function qstashConfigured(env: EnvLike = process.env): boolean {
  return qstashSigningKeysFromEnv(env).length > 0
}

export function verifyQstashSignature(
  signature: string | null,
  env: EnvLike = process.env,
): boolean {
  if (!signature) return false
  const keys = qstashSigningKeysFromEnv(env)
  if (!keys.length) return false
  const [encodedHeader, encodedPayload, encodedSignature] = signature.split(".")
  if (!encodedHeader || !encodedPayload || !encodedSignature) return false
  return keys.some((key) => {
    const digest = createHmac("sha256", key).update(`${encodedHeader}.${encodedPayload}`).digest()
    return secureEqual(base64UrlEncode(digest), encodedSignature)
  })
}

export function parseQstashJwtClaims(signature: string | null): Record<string, unknown> | null {
  if (!signature) return null
  const parts = signature.split(".")
  if (parts.length < 2) return null
  try {
    return JSON.parse(base64UrlDecode(parts[1]).toString("utf8")) as Record<string, unknown>
  } catch {
    return null
  }
}
