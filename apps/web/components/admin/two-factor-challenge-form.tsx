"use client";

import { Loader2 } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, verifyTwoFactor } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Must match the length of _generate_recovery_code() in apps/api/routers/auth.py.
// secrets.token_urlsafe(24) always returns 32 characters. See H174.
const RECOVERY_CODE_LENGTH = 32;
const TOTP_CODE_LENGTH = 6;

const COPY = {
  recoveryHint: "Enter one recovery code, exactly as shown. Each code is 32 characters, and capital letters matter.",
  totpHint: "Enter the 6-digit code from your authenticator app.",
  recoveryTooLong: "This is longer than one recovery code. Enter only one code (32 characters).",
  recoveryTooShort: "This is shorter than a recovery code. Each code is 32 characters. Check you copied all of it.",
  totpInvalid: "Authenticator codes are 6 digits. To use a recovery code, choose Use a recovery code.",
  recoveryRejected: "That recovery code wasn't accepted. Check it was copied exactly, including capital letters. It may already have been used. Try another code, or go back to sign in and start again.",
  totpRejected: "That code wasn't accepted. Check your authenticator app and try again. If it keeps failing, go back to sign in and start again.",
};

export function TwoFactorChallengeForm({ challengeToken, onVerified, onAbandon }: {
  challengeToken: string;
  onVerified: (accessToken: string) => void;
  onAbandon: (reason: "locked" | "expired" | "user") => void;
}) {
  const [mode, setMode] = useState<"totp" | "recovery">("totp");
  const [value, setValue] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const active = useRef(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    active.current = true;
    const abandon = () => { active.current = false; };
    window.addEventListener("pagehide", abandon);
    return () => {
      active.current = false;
      window.removeEventListener("pagehide", abandon);
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedMode = mode;
    const normalised = value.replace(/\s/g, "");
    if (!normalised || isSubmitting) return;
    if (submittedMode === "recovery") {
      if (normalised.length > RECOVERY_CODE_LENGTH) {
        setFormError(COPY.recoveryTooLong);
        inputRef.current?.focus();
        return;
      }
      if (normalised.length < RECOVERY_CODE_LENGTH) {
        setFormError(COPY.recoveryTooShort);
        inputRef.current?.focus();
        return;
      }
    } else if (normalised.length !== TOTP_CODE_LENGTH || !/^[0-9]+$/.test(normalised)) {
      setFormError(COPY.totpInvalid);
      inputRef.current?.focus();
      return;
    }
    setFormError(null);
    setIsSubmitting(true);
    try {
      const response = await verifyTwoFactor({
        two_factor_challenge_token: challengeToken,
        ...(submittedMode === "totp" ? { code: normalised } : { recovery_code: normalised }),
      });
      if (!active.current) return;
      if (typeof response.access_token === "string" && response.access_token.length > 0) {
        onVerified(response.access_token);
      } else {
        setFormError("Unable to sign in. Please try again.");
      }
    } catch (error) {
      if (!active.current) return;
      if (error instanceof ApiError && error.status === 400 && error.code === "AUTH_2FA_CHALLENGE_EXPIRED") {
        onAbandon("expired");
      } else if (error instanceof ApiError && error.status === 400 && error.code === "AUTH_2FA_INVALID") {
        setFormError(submittedMode === "recovery" ? COPY.recoveryRejected : COPY.totpRejected);
      } else if (error instanceof ApiError && error.status === 429 && error.code === "AUTH_2FA_INVALID") {
        onAbandon("locked");
      } else if (error instanceof ApiError && error.status === 429 && error.code === "RATE_LIMIT_EXCEEDED") {
        setFormError("Too many attempts. Please wait a minute and try again.");
      } else {
        setFormError("Unable to verify. Please try again.");
      }
    } finally {
      if (active.current) setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2">
        <label htmlFor="two-factor-code" className="text-sm font-medium text-slate-700">
          {mode === "totp" ? "Authenticator code" : "Recovery code"}
        </label>
        <Input id="two-factor-code" value={value} onChange={(event) => {
          setValue(event.target.value);
          if (formError) setFormError(null);
        }}
          ref={inputRef}
          aria-invalid={Boolean(formError)}
          aria-describedby={formError ? "two-factor-code-hint two-factor-code-error" : "two-factor-code-hint"}
          inputMode={mode === "totp" ? "numeric" : "text"} autoComplete="one-time-code" disabled={isSubmitting} />
        <p id="two-factor-code-hint" className="text-sm text-slate-500">
          {mode === "recovery" ? COPY.recoveryHint : COPY.totpHint}
        </p>
      </div>
      {formError ? <p id="two-factor-code-error" role="alert" className="text-sm text-red-700">{formError}</p> : null}
      <Button type="submit" className="w-full" disabled={!value.trim() || isSubmitting}>
        {isSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}Verify
      </Button>
      <Button type="button" variant="outline" className="w-full" disabled={isSubmitting} onClick={() => {
        setMode(mode === "totp" ? "recovery" : "totp");
        setValue("");
        setFormError(null);
      }}>
        {mode === "totp" ? "Use a recovery code" : "Use an authenticator code"}
      </Button>
      <Button type="button" variant="outline" className="w-full" onClick={() => {
        active.current = false;
        onAbandon("user");
      }}>Back to sign in</Button>
    </form>
  );
}
