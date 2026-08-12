"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { LogIn, LogOut, Loader2, Mail, User } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface AuthControlProps {
  /** Hide the "Account" link -- pass this on the account page itself, no
   * reason to link to the page you're already on. */
  hideAccountLink?: boolean;
}

export function AuthControl({ hideAccountLink }: AuthControlProps = {}) {
  const { signedIn, email, loading, sendMagicLink, signOut } = useAuth();
  const [formOpen, setFormOpen] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await sendMagicLink(emailInput);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }

  function closeForm() {
    setFormOpen(false);
    setSent(false);
    setError(null);
    setEmailInput("");
  }

  // Avoids a flash of "Sign in" before the initial session check resolves.
  if (loading) {
    return <div className="h-7 w-20" />;
  }

  if (signedIn) {
    return (
      <div className="flex items-center gap-2">
        <span className="hidden text-xs text-slate-500 sm:inline">{email}</span>
        {!hideAccountLink && (
          <Link href="/account">
            <Button type="button" size="sm" variant="outline">
              <User className="h-3.5 w-3.5" />
              Account
            </Button>
          </Link>
        )}
        <Button type="button" onClick={() => void signOut()} size="sm" variant="outline">
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </Button>
      </div>
    );
  }

  if (!formOpen) {
    return (
      <Button type="button" onClick={() => setFormOpen(true)} size="sm" variant="outline">
        <LogIn className="h-3.5 w-3.5" />
        Sign in
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-900 p-3 shadow-lg shadow-black/30">
      {sent ? (
        <div className="flex flex-col gap-2 text-xs">
          <p className="flex items-center gap-1.5 text-slate-300">
            <Mail className="h-3.5 w-3.5 text-emerald-400" />
            Check <span className="font-medium text-slate-100">{emailInput}</span> for a sign-in link.
          </p>
          <button type="button" onClick={closeForm} className="self-start text-slate-500 hover:text-slate-300">
            Close
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <Input
            type="email"
            required
            autoFocus
            placeholder="you@example.com"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            className="h-8 w-52 text-xs"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex items-center gap-2">
            <Button type="submit" disabled={sending} size="sm">
              {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Mail className="h-3.5 w-3.5" />}
              {sending ? "Sending…" : "Send magic link"}
            </Button>
            <button type="button" onClick={closeForm} className="text-xs text-slate-500 hover:text-slate-300">
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
