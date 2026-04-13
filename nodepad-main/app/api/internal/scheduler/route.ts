import { NextRequest, NextResponse } from "next/server"
import { dispatchDueJobsServer } from "@/lib/research-server"
import { parseQstashJwtClaims, verifyQstashSignature } from "@/lib/research-runtime"

function unauthorized(message: string) {
  return NextResponse.json({ error: message }, { status: 401 })
}

export async function POST(request: NextRequest) {
  const signature = request.headers.get("Upstash-Signature")
  if (!verifyQstashSignature(signature)) {
    return unauthorized("Invalid Upstash signature.")
  }

  const claims = parseQstashJwtClaims(signature)
  if (!claims) {
    return unauthorized("Invalid Upstash claims.")
  }

  try {
    const result = await dispatchDueJobsServer({
      leaseOwner: "qstash-scheduler",
      trigger: "qstash",
    })
    return NextResponse.json(
      {
        ok: true,
        claims,
        result,
      },
      { status: 200 },
    )
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Scheduler dispatch failed." },
      { status: 500 },
    )
  }
}
