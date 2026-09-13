"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { ApiError, requestPasswordReset } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);

  function validateForm() {
    if (!email.trim()) {
      setEmailError("Email is required.");
      return false;
    }
    if (!emailPattern.test(email)) {
      setEmailError("Enter a valid email address.");
      return false;
    }
    setEmailError(null);
    return true;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!validateForm()) return;

    setIsSubmitting(true);
    let rateLimited = false;
    try {
      await requestPasswordReset({ email });
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        rateLimited = true;
      }
    } finally {
      if (rateLimited) {
        setFormError("Please wait and try again shortly.");
      } else {
        setIsConfirmed(true);
      }
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="border-slate-200 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
      <CardHeader className="px-8 pb-0 pt-8 text-center">
        <CardTitle className="text-2xl font-semibold tracking-tight">Forgot password?</CardTitle>
        <CardDescription>Enter your work email to request a password reset link.</CardDescription>
      </CardHeader>
      <CardContent className="px-8 pb-8 pt-8">
        {isConfirmed ? (
          <p role="status" className="text-sm text-slate-600">
            If an account exists for that address, a reset link has been sent. Please check your inbox.
          </p>
        ) : (
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="email">Work email</label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={Boolean(emailError)}
                className={emailError ? "border-red-400 focus-visible:ring-red-500" : undefined}
                placeholder="name@company.com"
              />
              {emailError ? <p className="text-sm text-red-600">{emailError}</p> : null}
            </div>
            {formError ? (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            ) : null}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <><Loader2 className="mr-2 size-4 animate-spin" />Sending...</>
              ) : "Send reset link"}
            </Button>
          </form>
        )}
        <p className="mt-6 text-center text-sm text-slate-500">
          <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/login" prefetch={false}>
            Back to sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
