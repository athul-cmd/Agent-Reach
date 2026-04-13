"use client"

import Link from "next/link"
import { type InputHTMLAttributes, type TextareaHTMLAttributes, useEffect, useState } from "react"
import {
  deleteOpenAISettings,
  loadOpenAISettings,
  saveOpenAISettings,
  saveResearchProfile,
  type OpenAISettingsPayload,
  type ResearchDashboardData,
  type ResearchProfileInput,
} from "@/lib/research-api"
import { ArrowLeft, KeyRound, RadioTower } from "lucide-react"

function splitCommaSeparated(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function FormInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-sm border border-border/60 bg-black/30 px-3 py-2 text-sm outline-none transition-colors focus:border-primary/60 ${props.className || ""}`}
    />
  )
}

function FormTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-sm border border-border/60 bg-black/30 px-3 py-2 text-sm outline-none transition-colors focus:border-primary/60 ${props.className || ""}`}
    />
  )
}

function ActionButton({
  disabled,
  onClick,
  children,
  primary = false,
}: {
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
  primary?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full rounded-sm border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] disabled:opacity-50 ${
        primary
          ? "border-primary/60 bg-primary/15 text-primary"
          : "border-border/60 bg-card/40 text-foreground"
      }`}
    >
      {children}
    </button>
  )
}

export function ResearchSettings({ data }: { data: ResearchDashboardData }) {
  const [profileForm, setProfileForm] = useState<ResearchProfileInput>({
    name: data.profile?.name || "",
    persona_brief: data.profile?.persona_brief || "",
    niche_definition: data.profile?.niche_definition || "",
    target_audience: data.profile?.target_audience || "",
    must_track_topics: data.profile?.must_track_topics || [],
    excluded_topics: data.profile?.excluded_topics || [],
    desired_formats: data.profile?.desired_formats || [],
  })
  const [topicsInput, setTopicsInput] = useState((data.profile?.must_track_topics || []).join(", "))
  const [excludedInput, setExcludedInput] = useState((data.profile?.excluded_topics || []).join(", "))
  const [formatsInput, setFormatsInput] = useState((data.profile?.desired_formats || []).join(", "))
  const [openAISettings, setOpenAISettings] = useState<OpenAISettingsPayload | null>(null)
  const [openAIKeyInput, setOpenAIKeyInput] = useState("")
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const settings = await loadOpenAISettings()
        setOpenAISettings(settings)
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Could not load settings.")
      }
    })()
  }, [])

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label)
    setStatusMessage(null)
    setErrorMessage(null)
    try {
      await action()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Action failed.")
    } finally {
      setBusyAction(null)
    }
  }

  async function handleProfileSave() {
    await runAction("profile", async () => {
      await saveResearchProfile({
        ...profileForm,
        must_track_topics: splitCommaSeparated(topicsInput),
        excluded_topics: splitCommaSeparated(excludedInput),
        desired_formats: splitCommaSeparated(formatsInput),
      })
      setStatusMessage("Research profile saved.")
    })
  }

  async function handleOpenAIKeySave() {
    await runAction("openai-settings", async () => {
      const settings = await saveOpenAISettings(openAIKeyInput)
      setOpenAISettings(settings)
      setOpenAIKeyInput("")
      setStatusMessage("OpenAI key saved to encrypted server-side settings.")
    })
  }

  async function handleOpenAIKeyDelete() {
    await runAction("openai-settings-delete", async () => {
      const settings = await deleteOpenAISettings()
      setOpenAISettings(settings)
      setOpenAIKeyInput("")
      setStatusMessage("OpenAI key removed from server-side settings.")
    })
  }

  return (
    <main className="min-h-screen bg-[#030303] px-6 py-8 text-foreground">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-sm border border-border/60 bg-card/60 px-6 py-5 backdrop-blur-md">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <RadioTower className="h-4 w-4 text-primary" />
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-primary/80">
                Research Studio
              </p>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Manage the research profile and server-side OpenAI configuration from one place.
            </p>
          </div>
          <Link
            href="/research"
            className="inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/40 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back To Dashboard
          </Link>
        </header>

        {(busyAction || statusMessage || errorMessage) && (
          <div className="rounded-sm border border-border/60 bg-card/40 px-4 py-3">
            {busyAction && (
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary/80">
                Working: {busyAction}
              </p>
            )}
            {statusMessage && <p className="mt-1 text-sm text-foreground/80">{statusMessage}</p>}
            {errorMessage && <p className="mt-1 text-sm text-destructive/90">{errorMessage}</p>}
          </div>
        )}

        <section className="rounded-sm border border-border/60 bg-card/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <RadioTower className="h-4 w-4 text-primary" />
            <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/70">
              Profile Setup
            </h2>
          </div>
          <div className="space-y-3 text-sm">
            <FormInput
              value={profileForm.name}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Profile name"
            />
            <FormTextarea
              value={profileForm.persona_brief}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, persona_brief: event.target.value }))}
              placeholder="Persona brief"
              className="min-h-[88px]"
            />
            <FormTextarea
              value={profileForm.niche_definition}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, niche_definition: event.target.value }))}
              placeholder="Niche definition"
              className="min-h-[88px]"
            />
            <FormInput
              value={profileForm.target_audience || ""}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, target_audience: event.target.value }))}
              placeholder="Audience"
            />
            <FormInput
              value={topicsInput}
              onChange={(event) => setTopicsInput(event.target.value)}
              placeholder="Must-track topics, comma separated"
            />
            <FormInput
              value={excludedInput}
              onChange={(event) => setExcludedInput(event.target.value)}
              placeholder="Excluded topics, comma separated"
            />
            <FormInput
              value={formatsInput}
              onChange={(event) => setFormatsInput(event.target.value)}
              placeholder="Formats, comma separated"
            />
            <ActionButton onClick={() => void handleProfileSave()} disabled={busyAction !== null} primary={true}>
              Save Profile
            </ActionButton>
          </div>
        </section>

        <section className="rounded-sm border border-border/60 bg-card/40 p-5">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-primary" />
            <h2 className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/70">
              OpenAI Settings
            </h2>
          </div>
          <div className="space-y-3 text-sm">
            <div className="rounded-sm border border-border/50 bg-black/20 p-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/50">
                OpenAI Key
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                The key is saved through an authenticated server route and stored encrypted in Supabase. It is never used as browser-local runtime state.
              </p>
              <p className="mt-2 text-xs text-foreground/80">
                Status: {openAISettings?.configured ? `Configured ${openAISettings.masked_value}` : "Not configured"}
              </p>
              {openAISettings?.updated_at && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Updated: {new Date(openAISettings.updated_at).toLocaleString()}
                </p>
              )}
            </div>
            <FormInput
              type="password"
              value={openAIKeyInput}
              onChange={(event) => setOpenAIKeyInput(event.target.value)}
              placeholder="Paste a new OpenAI API key"
            />
            <div className="grid grid-cols-2 gap-2">
              <ActionButton
                onClick={() => void handleOpenAIKeySave()}
                disabled={busyAction !== null || !openAIKeyInput.trim()}
                primary={true}
              >
                Save Key
              </ActionButton>
              <ActionButton
                onClick={() => void handleOpenAIKeyDelete()}
                disabled={busyAction !== null || !openAISettings?.configured}
              >
                Clear Key
              </ActionButton>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
