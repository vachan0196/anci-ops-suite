"use client";

import { Loader2 } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError, beginTotpEnrolment, confirmTotpEnrolment, getTwoFactorStatus,
  type TwoFactorStatusResponse,
} from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth-token";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function TwoFactorEnrolment() {
  const [status, setStatus] = useState<TwoFactorStatusResponse | null>(null);
  const [setup, setSetup] = useState<{ manualSecret: string; expiresAt: string } | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [saved, setSaved] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const active = useRef(true);

  async function loadStatus() {
    setIsSubmitting(true);
    setFormError(null);
    try {
      const token = getAccessToken();
      if (!token) throw new Error();
      const response = await getTwoFactorStatus(token);
      if (active.current) setStatus(response);
    } catch {
      if (active.current) setFormError("Something went wrong. Please try again.");
    } finally {
      if (active.current) setIsSubmitting(false);
    }
  }

  useEffect(() => {
    active.current = true;
    void loadStatus();
    const clearSecrets = () => {
      active.current = false;
      setRecoveryCodes(null);
      setSetup(null);
      setCode("");
    };
    window.addEventListener("pagehide", clearSecrets);
    return () => {
      window.removeEventListener("pagehide", clearSecrets);
      clearSecrets();
    };
  }, []);

  async function handleError(error: unknown) {
    if (error instanceof ApiError && error.code === "AUTH_2FA_ENROLMENT_INVALID") {
      setSetup(null);
      setCode("");
      setFormError("That setup expired. Start again.");
    } else if (error instanceof ApiError && error.code === "AUTH_2FA_INVALID_CODE") {
      setFormError("That code wasn't accepted. Check your authenticator and try again.");
    } else if (error instanceof ApiError && error.code === "AUTH_2FA_ALREADY_ENABLED") {
      setSetup(null);
      setCode("");
      await loadStatus();
    } else {
      setFormError("Something went wrong. Please try again.");
    }
  }

  async function handleBegin() {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      const token = getAccessToken();
      if (!token) throw new Error();
      const response = await beginTotpEnrolment(token);
      if (active.current) {
        setSetup({ manualSecret: response.manual_secret, expiresAt: response.expires_at });
        setCode("");
      }
    } catch (error) {
      if (active.current) await handleError(error);
    } finally {
      if (active.current) setIsSubmitting(false);
    }
  }

  async function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting || !code.trim()) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      const token = getAccessToken();
      if (!token) throw new Error();
      const response = await confirmTotpEnrolment(token, { code: code.trim() });
      if (active.current) {
        setSetup(null);
        setCode("");
        setRecoveryCodes(response.recovery_codes);
        setSaved(false);
      }
    } catch (error) {
      if (active.current) await handleError(error);
    } finally {
      if (active.current) setIsSubmitting(false);
    }
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      if (active.current) setFormError("Something went wrong. Please try again.");
    }
  }

  function downloadRecoveryCodes(codes: string[]) {
    let url: string | null = null;
    let link: HTMLAnchorElement | null = null;
    try {
      const blob = new Blob([codes.join("\r\n") + "\r\n"], { type: "text/plain;charset=utf-8" });
      url = URL.createObjectURL(blob);
      link = document.createElement("a");
      link.href = url;
      link.download = "admin-portal-recovery-codes.txt";
      document.body.appendChild(link);
      link.click();
    } catch {
      if (active.current) setFormError("Something went wrong. Please try again.");
    } finally {
      link?.remove();
      if (url !== null) {
        const createdUrl = url;
        window.setTimeout(() => URL.revokeObjectURL(createdUrl), 1000);
      }
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-12 sm:px-6">
      <Card className="mx-auto max-w-lg">
        <CardHeader><CardTitle>Two-factor authentication</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          {formError ? <p role="alert" className="text-sm text-red-700">{formError}</p> : null}
          {recoveryCodes !== null ? (
            <div className="space-y-4">
              <h1 className="text-xl font-semibold">Save your recovery codes</h1>
              <p>These are shown once. Each code works once.</p>
              <p>When you sign in, enter one code at a time, exactly as shown.</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-100 p-3 font-mono">{recoveryCodes.join("\n")}</pre>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => copy(recoveryCodes.join("\n"))}>Copy all codes</Button>
                <Button type="button" variant="outline" onClick={() => downloadRecoveryCodes(recoveryCodes)}>Download codes (.txt)</Button>
              </div>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} />
                I have saved these codes
              </label>
              <Button type="button" disabled={!saved || isSubmitting} onClick={() => {
                setRecoveryCodes(null);
                setSaved(false);
                void loadStatus();
              }}>Done</Button>
            </div>
          ) : status?.totp_enrolled ? (
            <div className="space-y-3">
              <h1 className="text-xl font-semibold">Two-factor authentication is on</h1>
              <p>Recovery codes remaining: {status.recovery_codes_remaining}</p>
            </div>
          ) : setup ? (
            <form onSubmit={handleConfirm} className="space-y-4">
              <p>Enter this key manually in your authenticator app:</p>
              <code className="block break-all rounded-lg bg-slate-100 p-3 font-mono">{setup.manualSecret}</code>
              <Button type="button" variant="outline" onClick={() => copy(setup.manualSecret)}>Copy key</Button>
              <p>This setup key expires at {setup.expiresAt}.</p>
              <label htmlFor="enrolment-code" className="block text-sm font-medium">6-digit code</label>
              <Input id="enrolment-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}"
                maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} disabled={isSubmitting} />
              <Button type="submit" disabled={isSubmitting || !/^[0-9]{6}$/.test(code.trim())}>
                {isSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}Confirm
              </Button>
            </form>
          ) : status ? (
            <Button type="button" onClick={handleBegin} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}Set up two-factor authentication
            </Button>
          ) : isSubmitting ? (
            <p role="status">Loading security settings...</p>
          ) : (
            <Button type="button" variant="outline" onClick={loadStatus}>Try again</Button>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
