"use client"

import Link from "next/link"

export default function NotFound() {
  return (
    <div className="relative flex h-screen w-screen flex-col items-center justify-center overflow-hidden bg-background">

      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute left-[7%] top-[14%] h-24 w-44 rounded-sm border border-border/30 bg-card/40 backdrop-blur-sm" />
        <div className="absolute left-[13%] top-[28%] h-16 w-32 rounded-sm border border-border/20 bg-card/25" />
        <div className="absolute right-[9%] top-[10%] h-20 w-52 rounded-sm border border-border/30 bg-card/40 backdrop-blur-sm" />
        <div className="absolute right-[18%] top-[26%] h-12 w-36 rounded-sm border border-border/15 bg-card/20" />
        <div className="absolute bottom-[18%] left-[6%] h-16 w-40 rounded-sm border border-border/25 bg-card/30" />
        <div className="absolute bottom-[32%] left-[16%] h-10 w-28 rounded-sm border border-border/15 bg-card/20" />
        <div className="absolute bottom-[14%] right-[8%] h-20 w-48 rounded-sm border border-border/30 bg-card/35 backdrop-blur-sm" />
        <div className="absolute bottom-[30%] right-[19%] h-14 w-32 rounded-sm border border-border/15 bg-card/20" />
        <div className="absolute left-[2%] top-[48%] h-8 w-20 rounded-sm border border-border/10 bg-card/15" />
        <div className="absolute right-[3%] top-[44%] h-8 w-24 rounded-sm border border-border/10 bg-card/15" />
        <div
          className="absolute left-[7%] top-[14%] h-1 w-14 rounded-full opacity-60"
          style={{ background: "var(--type-question)" }}
        />
        <div
          className="absolute right-[9%] top-[10%] h-1 w-20 rounded-full opacity-50"
          style={{ background: "var(--type-claim)" }}
        />
        <div
          className="absolute bottom-[18%] left-[6%] h-1 w-12 rounded-full opacity-40"
          style={{ background: "var(--type-idea)" }}
        />
        <div
          className="absolute bottom-[14%] right-[8%] h-1 w-16 rounded-full opacity-50"
          style={{ background: "var(--type-reference)" }}
        />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-6 text-center">
        <div className="mb-2 flex items-center gap-2">
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--type-quote)]" />
            <span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--type-quote)] opacity-60" />
            <span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--type-quote)] opacity-30" />
          </div>
          <span className="font-mono text-xs font-semibold tracking-tight text-foreground/60">
            content research studio
          </span>
        </div>
        <div
          className="font-mono text-[clamp(6rem,18vw,14rem)] font-black leading-none tracking-tighter"
          style={{ color: "var(--type-question)", opacity: 0.18 }}
          aria-hidden
        >
          404
        </div>
        <div className="-mt-10 flex flex-col items-center gap-3">
          <p className="font-mono text-sm font-medium tracking-tight text-foreground">
            This page doesn't exist.
          </p>
          <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
            The page you requested is not part of this research workspace, or the route has moved.
          </p>
        </div>
        <Link
          href="/research"
          className="mt-2 inline-flex items-center gap-2 rounded-sm border border-border/60 bg-card/80 px-5 py-2.5 font-mono text-xs font-medium text-foreground/80 transition-colors hover:border-border hover:bg-card hover:text-foreground"
        >
          ← Back to research
        </Link>
      </div>
    </div>
  )
}
