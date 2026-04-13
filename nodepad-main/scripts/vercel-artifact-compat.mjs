import { copyFile, mkdir, stat } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const appDir = resolve(__dirname, "..")
const repoRoot = resolve(appDir, "..")

async function exists(path) {
  try {
    await stat(path)
    return true
  } catch {
    return false
  }
}

async function mirrorBuildArtifact(sourceRelativePath, targetRelativePath = sourceRelativePath) {
  const source = resolve(appDir, ".next", sourceRelativePath)
  const target = resolve(repoRoot, ".next", targetRelativePath)

  if (!(await exists(source))) {
    return
  }

  await mkdir(dirname(target), { recursive: true })
  await copyFile(source, target)
}

async function main() {
  if (process.env.VERCEL !== "1") {
    return
  }

  // Vercel monorepo builds may look for this manifest from repo root.
  // Next.js webpack builds generate routes-manifest.json, so we map it.
  const deterministic = "routes-manifest-deterministic.json"
  const deterministicSource = resolve(appDir, ".next", deterministic)

  if (await exists(deterministicSource)) {
    await mirrorBuildArtifact(deterministic)
    return
  }

  await mirrorBuildArtifact("routes-manifest.json", deterministic)
}

await main()
