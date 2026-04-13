import { NextRequest, NextResponse } from "next/server"
import { encryptServerSecret, maskSecret, secretLast4 } from "@/lib/server-secret-crypto"
import { createServerSupabaseClient } from "@/lib/supabase/server"

type SettingsRow = {
  user_id: string
  openai_api_key_ciphertext: string | null
  openai_api_key_last4: string | null
  updated_at: string | null
}

function settingsResponse(row: SettingsRow | null) {
  const last4 = row?.openai_api_key_last4 || ""
  return {
    configured: Boolean(row?.openai_api_key_ciphertext),
    masked_value: last4 ? maskSecret(last4) : "",
    last4,
    updated_at: row?.updated_at || null,
  }
}

async function requireUser() {
  const supabase = await createServerSupabaseClient()
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()
  if (error) {
    throw new Error(error.message)
  }
  if (!user) {
    return { supabase, user: null }
  }
  return { supabase, user }
}

async function readSettingsRow(userId: string) {
  const supabase = await createServerSupabaseClient()
  const { data, error } = await supabase
    .from("research_user_settings")
    .select("user_id, openai_api_key_ciphertext, openai_api_key_last4, updated_at")
    .eq("user_id", userId)
    .maybeSingle()
  if (error) {
    throw new Error(error.message)
  }
  return data as SettingsRow | null
}

export async function GET() {
  try {
    const { user } = await requireUser()
    if (!user) {
      return NextResponse.json({ error: "Unauthorized." }, { status: 401 })
    }
    const row = await readSettingsRow(user.id)
    return NextResponse.json(settingsResponse(row))
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not load settings." },
      { status: 500 },
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await requireUser()
    if (!user) {
      return NextResponse.json({ error: "Unauthorized." }, { status: 401 })
    }

    const body = await request.json().catch(() => ({}))
    const apiKey = typeof body?.apiKey === "string" ? body.apiKey.trim() : ""
    if (!apiKey) {
      return NextResponse.json({ error: "Missing apiKey." }, { status: 400 })
    }

    const ciphertext = encryptServerSecret(apiKey)
    const last4 = secretLast4(apiKey)
    const { error } = await supabase.from("research_user_settings").upsert(
      {
        user_id: user.id,
        openai_api_key_ciphertext: ciphertext,
        openai_api_key_last4: last4,
      },
      {
        onConflict: "user_id",
      },
    )
    if (error) {
      throw new Error(error.message)
    }
    const row = await readSettingsRow(user.id)
    return NextResponse.json(settingsResponse(row))
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not save settings." },
      { status: 500 },
    )
  }
}

export async function DELETE() {
  try {
    const { supabase, user } = await requireUser()
    if (!user) {
      return NextResponse.json({ error: "Unauthorized." }, { status: 401 })
    }

    const { error } = await supabase.from("research_user_settings").upsert(
      {
        user_id: user.id,
        openai_api_key_ciphertext: null,
        openai_api_key_last4: null,
      },
      {
        onConflict: "user_id",
      },
    )
    if (error) {
      throw new Error(error.message)
    }
    const row = await readSettingsRow(user.id)
    return NextResponse.json(settingsResponse(row))
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not delete settings." },
      { status: 500 },
    )
  }
}
