"use client";

import { createClient } from "@supabase/supabase-js";

// This app is entirely client-rendered (every page is "use client", no
// server components or actions read auth state), so the plain browser
// client is enough -- it persists the session to localStorage itself and
// auto-detects the magic-link redirect's token in the URL on load. No
// @supabase/ssr / cookie-based session plumbing needed unless a server
// component or route handler starts depending on auth state later.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY -- set them in web/.env.local."
  );
}

// Singleton: creating more than one client for the same project duplicates
// the auth-state listener and can produce inconsistent session state across
// components.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
