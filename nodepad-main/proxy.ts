import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"
import { createServerClient } from "@supabase/ssr"

/**
 * Matcher must stay string patterns only: object matchers with `missing` / `has`
 * break `next build` on Next.js 16.2+ ("Invalid segment configuration export").
 */

/** Preserve Set-Cookie from session refresh (Supabase SSR) when the handler returns a non-next() response. */
function copyResponseCookies(source: NextResponse, target: NextResponse): NextResponse {
  for (const cookie of source.cookies.getAll()) {
    const { name, value, ...options } = cookie
    target.cookies.set(name, value, options)
  }
  return target
}

function redirectWithSessionCookies(base: NextResponse, location: URL): NextResponse {
  return copyResponseCookies(base, NextResponse.redirect(location))
}

function supabaseEnv() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
  return { url, anonKey }
}

function isLoginPath(pathname: string): boolean {
  return pathname === "/research/login"
}

function isProtectedApiPath(pathname: string): boolean {
  return pathname.startsWith("/api/research") || pathname.startsWith("/api/settings")
}

function isProtectedPagePath(pathname: string): boolean {
  // Must exclude login; it lives under /research/ and would otherwise redirect to itself forever.
  if (pathname === "/research/login") {
    return false
  }
  return pathname === "/research" || pathname.startsWith("/research/")
}

export async function proxy(req: NextRequest): Promise<NextResponse> {
  const { pathname, search } = req.nextUrl
  const { url, anonKey } = supabaseEnv()

  if (!url || !anonKey) {
    if (isProtectedApiPath(pathname)) {
      return NextResponse.json(
        { error: "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY." },
        { status: 500 },
      )
    }
    if (isProtectedPagePath(pathname)) {
      const loginUrl = new URL("/research/login", req.url)
      loginUrl.searchParams.set("next", `${pathname}${search}`)
      loginUrl.searchParams.set("error", "supabase-env-missing")
      return NextResponse.redirect(loginUrl)
    }
    return NextResponse.next()
  }

  const sessionResponse = NextResponse.next({
    request: {
      headers: req.headers,
    },
  })

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return req.cookies.getAll()
      },
      setAll(
        cookiesToSet: Array<{
          name: string
          value: string
          options?: Parameters<typeof sessionResponse.cookies.set>[2]
        }>,
      ) {
        cookiesToSet.forEach(({ name, value, options }) => {
          req.cookies.set(name, value)
          sessionResponse.cookies.set(name, value, options)
        })
      },
    },
  })

  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (user && isLoginPath(pathname)) {
    return redirectWithSessionCookies(sessionResponse, new URL("/research", req.url))
  }

  if (!user && (isProtectedApiPath(pathname) || isProtectedPagePath(pathname))) {
    if (isProtectedApiPath(pathname)) {
      const unauthorized = NextResponse.json({ error: "Unauthorized." }, { status: 401 })
      return copyResponseCookies(sessionResponse, unauthorized)
    }
    const loginUrl = new URL("/research/login", req.url)
    loginUrl.searchParams.set("next", `${pathname}${search}`)
    return redirectWithSessionCookies(sessionResponse, loginUrl)
  }

  return sessionResponse
}

export const config = {
  matcher: ["/research", "/research/:path*", "/api/research/:path*", "/api/settings/:path*"],
}
