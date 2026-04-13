"use client"

export function MobileWall() {
  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background px-8 text-center md:hidden" style={{ paddingBottom: "15vh" }}>
      {/* Logo */}
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex items-center gap-1">
          <span className="h-3.5 w-3.5 rounded-sm bg-[#3ecf6e]" />
          <span className="h-3.5 w-3.5 rounded-sm bg-[#3ecf6e] opacity-60" />
          <span className="h-3.5 w-3.5 rounded-sm bg-[#3ecf6e] opacity-30" />
        </div>
        <span className="font-mono text-sm font-semibold tracking-tight text-foreground">
          research studio
        </span>
      </div>

      {/* Message */}
      <p className="mb-3 max-w-xs text-base font-medium text-foreground">
        Spatial thinking needs space.
      </p>
      <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
        Research Studio is built for large screens. Open it on a desktop or laptop browser to get the full experience.
      </p>
    </div>
  )
}
