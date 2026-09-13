"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, confirmEmailVerification } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function VerifyEmailForm({ initialToken }: { initialToken: string | null }) {
  const [token, setToken] = useState(initialToken);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccessful, setIsSuccessful] = useState(false);

  useEffect(() => {
    // Restore state during Strict Mode's setup/cleanup/setup cycle as well.
    setToken(initialToken);
    window.history.replaceState(window.history.state, "", window.location.pathname);
    const clearToken = () => setToken(null);
    window.addEventListener("pagehide", clearToken);
    return () => {
      window.removeEventListener("pagehide", clearToken);
      setToken(null);
    };
  }, [initialToken]);

  async function handleVerify() {
    if (!token || isSubmitting) return;
    setFormError(null);
    setIsSubmitting(true);
    try {
      await confirmEmailVerification({ token });
      setToken(null);
      setIsSuccessful(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "AUTH_EMAIL_VERIFICATION_INVALID") {
        setToken(null);
      } else if (error instanceof ApiError && error.status === 429) {
        setFormError("Please wait and try verifying your email again shortly.");
      } else {
        setFormError("Unable to verify your email. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="border-slate-200 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
      <CardHeader className="px-8 pb-0 pt-8 text-center">
        <CardTitle className="text-2xl font-semibold tracking-tight">Verify email</CardTitle>
        <CardDescription>Confirm the email address for your admin account.</CardDescription>
      </CardHeader>
      <CardContent className="px-8 pb-8 pt-8">
        {isSuccessful ? (
          <div className="space-y-5 text-sm text-slate-600" role="status">
            <p>Your email address has been verified.</p>
            <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/login" prefetch={false}>
              Sign in
            </Link>
          </div>
        ) : !token ? (
          <div className="space-y-5 text-sm text-slate-600" role="alert">
            <p>This verification link is invalid, expired, or already used. Please sign in to request a new link.</p>
            <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/login" prefetch={false}>
              Sign in
            </Link>
          </div>
        ) : (
          <div className="space-y-5">
            <p className="text-sm text-slate-600">Click below to verify your email address.</p>
            {formError ? (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            ) : null}
            <Button type="button" className="w-full" disabled={isSubmitting} onClick={handleVerify}>
              {isSubmitting ? <><Loader2 className="mr-2 size-4 animate-spin" />Verifying email...</> : "Verify my email"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
