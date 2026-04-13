import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto"

type EncryptedSecretPayload = {
  v: 1
  alg: "aes-256-gcm"
  iv: string
  ciphertext: string
  tag: string
}

function encryptionSecret(): string {
  const secret = process.env.RESEARCH_SETTINGS_ENCRYPTION_KEY || ""
  if (!secret) {
    throw new Error("Missing RESEARCH_SETTINGS_ENCRYPTION_KEY.")
  }
  return secret
}

function deriveKey(secret: string): Buffer {
  return createHash("sha256").update(secret, "utf8").digest()
}

export function encryptServerSecret(plaintext: string): string {
  const key = deriveKey(encryptionSecret())
  const iv = randomBytes(12)
  const cipher = createCipheriv("aes-256-gcm", key, iv)
  const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()])
  const tag = cipher.getAuthTag()
  const payload: EncryptedSecretPayload = {
    v: 1,
    alg: "aes-256-gcm",
    iv: iv.toString("base64"),
    ciphertext: ciphertext.toString("base64"),
    tag: tag.toString("base64"),
  }
  return JSON.stringify(payload)
}

export function decryptServerSecret(payloadText: string): string {
  const payload = JSON.parse(payloadText) as EncryptedSecretPayload
  if (payload.v !== 1 || payload.alg !== "aes-256-gcm") {
    throw new Error("Unsupported encrypted secret payload.")
  }
  const key = deriveKey(encryptionSecret())
  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(payload.iv, "base64"))
  decipher.setAuthTag(Buffer.from(payload.tag, "base64"))
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(payload.ciphertext, "base64")),
    decipher.final(),
  ])
  return plaintext.toString("utf8")
}

export function maskSecret(secret: string): string {
  if (!secret) return ""
  const last4 = secret.slice(-4)
  return `••••••••${last4}`
}

export function secretLast4(secret: string): string {
  return secret.slice(-4)
}
