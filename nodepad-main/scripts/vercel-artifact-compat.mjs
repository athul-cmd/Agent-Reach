import { cp, mkdir, stat } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const appDir = resolve(__dirname, "..")
const repoRoot = resolve(appDir, "..")
const vercelRoot = "/vercel"

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

async function mirrorBuildOutputDirectory() {
  const sourceDir = resolve(appDir, ".next")
  const targetDir = resolve(repoRoot, ".next")

  if (!(await exists(sourceDir))) {
    return
  }

  await cp(sourceDir, targetDir, {
    recursive: true,
    force: true,
    // Keep deploy payload smaller; cache is not needed for Vercel post-processing.
    filter: (src) => !src.includes("/.next/cache"),
  })
}

async function mirrorNodeModuleDirectory(sourceRelativeDir, absoluteTargetDir) {
  const candidates = [
    resolve(appDir, "node_modules", sourceRelativeDir),
    resolve(repoRoot, "node_modules", sourceRelativeDir),
  ]
  const sourceDir = await firstExistingPath(candidates)

  if (!sourceDir) {
    return
  }

  await mkdir(dirname(absoluteTargetDir), { recursive: true })
  await cp(sourceDir, absoluteTargetDir, {
    recursive: true,
    force: true,
  })
}

async function firstExistingPath(paths) {
  for (const path of paths) {
    if (await exists(path)) {
      return path
    }
  }
  return null
}

async function main() {
  if (process.env.VERCEL !== "1") {
    return
  }

  // Vercel monorepo post-processing may look for .next artifacts from repo root.
  // Mirror app build output to root to satisfy those lookups.
  await mirrorBuildOutputDirectory()

  // Some adapters specifically read routes-manifest-deterministic.json.
  // Next.js webpack builds generate routes-manifest.json, so we map it.
  const deterministic = "routes-manifest-deterministic.json"
  const deterministicSource = resolve(appDir, ".next", deterministic)

  if (await exists(deterministicSource)) {
    await mirrorBuildArtifact(deterministic)
  } else {
    await mirrorBuildArtifact("routes-manifest.json", deterministic)
  }

  // Vercel post-processing in monorepo builds can look for this Next adapter file
  // under /vercel/node_modules even when the app is installed in a subdirectory.
  await mirrorNodeModuleDirectory(
    "next/dist/build/adapter",
    resolve(vercelRoot, "node_modules/next/dist/build/adapter"),
  )
}

await main()
