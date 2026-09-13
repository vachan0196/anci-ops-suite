"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, confirmPasswordReset } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type FieldErrors = {
  new_password?: string;
  confirm_password?: string;
};

export function ResetPasswordForm({ initialToken }: { initialToken: string | null }) {
  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
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

  function validateForm() {
    const nextErrors: FieldErrors = {};
    if (!password) {
      nextErrors.new_password = "Password is required.";
    } else if (password.length < 8) {
      nextErrors.new_password = "Password must be at least 8 characters.";
    }
    if (!confirmPassword) {
      nextErrors.confirm_password = "Confirm password is required.";
    } else if (confirmPassword !== password) {
      nextErrors.confirm_password = "Passwords must match.";
    }
    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!token || !validateForm()) return;

    setIsSubmitting(true);
    try {
      await confirmPasswordReset({
        token,
        new_password: password,
        confirm_password: confirmPassword,
      });
      setToken(null);
      setPassword("");
      setConfirmPassword("");
      setIsSuccessful(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "AUTH_PASSWORD_RESET_INVALID") {
        setToken(null);
        setPassword("");
        setConfirmPassword("");
      } else if (error instanceof ApiError && error.status === 429) {
        setFormError("Please wait and try again shortly.");
      } else {
        setFormError("Unable to reset your password. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="border-slate-200 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
      <CardHeader className="px-8 pb-0 pt-8 text-center">
        <CardTitle className="text-2xl font-semibold tracking-tight">Reset password</CardTitle>
        <CardDescription>Choose a new password for your admin account.</CardDescription>
      </CardHeader>
      <CardContent className="px-8 pb-8 pt-8">
        {isSuccessful ? (
          <div className="space-y-5 text-sm text-slate-600" role="status">
            <p>Your password has been reset. You can now sign in with your new password.</p>
            <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/login" prefetch={false}>
              Sign in
            </Link>
          </div>
        ) : !token ? (
          <div className="space-y-5 text-sm text-slate-600" role="alert">
            <p>This reset link is invalid, expired, or already used. Please request a new link.</p>
            <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/forgot-password" prefetch={false}>
              Request a new reset link
            </Link>
          </div>
        ) : (
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="new_password">New password</label>
              <div className="relative">
                <Input
                  id="new_password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={Boolean(fieldErrors.new_password)}
                  className={cn("pr-11", fieldErrors.new_password && "border-red-400 focus-visible:ring-red-500")}
                  placeholder="Create a password"
                />
                <button type="button" onClick={() => setShowPassword((current) => !current)}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700"
                  aria-label={showPassword ? "Hide password" : "Show password"}>
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldErrors.new_password ? <p className="text-sm text-red-600">{fieldErrors.new_password}</p> : null}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="confirm_password">Confirm password</label>
              <div className="relative">
                <Input
                  id="confirm_password"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  aria-invalid={Boolean(fieldErrors.confirm_password)}
                  className={cn("pr-11", fieldErrors.confirm_password && "border-red-400 focus-visible:ring-red-500")}
                  placeholder="Confirm your password"
                />
                <button type="button" onClick={() => setShowConfirmPassword((current) => !current)}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700"
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}>
                  {showConfirmPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldErrors.confirm_password ? <p className="text-sm text-red-600">{fieldErrors.confirm_password}</p> : null}
            </div>
            {formError ? (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            ) : null}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? <><Loader2 className="mr-2 size-4 animate-spin" />Resetting password...</> : "Reset password"}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
