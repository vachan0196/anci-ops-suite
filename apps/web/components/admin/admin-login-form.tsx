"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { adminLogin, ApiError } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

type FieldErrors = {
  email?: string;
  password?: string;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function mapFieldErrors(error: ApiError): FieldErrors {
  const details = error.details;

  if (!details) {
    return {};
  }

  if (Array.isArray(details)) {
    return details.reduce<FieldErrors>((accumulator, item) => {
      if (!item || typeof item !== "object") {
        return accumulator;
      }

      const record = item as { field?: unknown; loc?: unknown; msg?: unknown };
      const message = typeof record.msg === "string" ? record.msg : error.message;
      const fieldValue =
        typeof record.field === "string"
          ? record.field
          : Array.isArray(record.loc)
            ? record.loc[record.loc.length - 1]
            : undefined;

      if (fieldValue === "email" || fieldValue === "password") {
        const field: keyof FieldErrors = fieldValue;
        accumulator[field] = message;
      }

      return accumulator;
    }, {});
  }

  if (typeof details === "object") {
    const record = details as Record<string, unknown>;
    const fieldErrors: FieldErrors = {};

    if (typeof record.email === "string") {
      fieldErrors.email = record.email;
    }

    if (typeof record.password === "string") {
      fieldErrors.password = record.password;
    }

    return fieldErrors;
  }

  return {};
}

export function AdminLoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (getAccessToken()) {
      router.replace("/admin");
    }
  }, [router]);

  function validateForm() {
    const nextErrors: FieldErrors = {};

    if (!email.trim()) {
      nextErrors.email = "Work email is required.";
    } else if (!emailPattern.test(email.trim())) {
      nextErrors.email = "Enter a valid work email address.";
    }

    if (!password) {
      nextErrors.password = "Password is required.";
    }

    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setFieldErrors({});

    try {
      const response = await adminLogin({
        email: email.trim(),
        password,
      });

      const access_token = response.access_token;

      console.log(access_token);
      localStorage.setItem("forecourt_access_token", access_token);
      router.replace("/admin");
    } catch (error) {
      if (error instanceof ApiError) {
        const nextFieldErrors = mapFieldErrors(error);

        if (Object.keys(nextFieldErrors).length > 0) {
          setFieldErrors(nextFieldErrors);
        } else {
          setFormError(error.message);
        }
      } else {
        setFormError("Unable to connect to server. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="border-slate-200 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
      <CardHeader className="space-y-6 px-8 pb-0 pt-8 text-center">
        <div className="space-y-2">
          <CardTitle className="text-2xl font-semibold tracking-tight">
            ForecourtOS
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">
            Secure access for operators managing sites, staff, and setup.
          </CardDescription>
        </div>

        <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
          <div className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm">
            Admin Portal
          </div>
          <div className="cursor-not-allowed rounded-lg px-3 py-2 text-sm font-medium text-slate-400">
            Employee Portal
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-8 pb-8 pt-8">
        <div className="mb-6 space-y-2">
          <h1 className="text-xl font-semibold text-slate-950">
            Sign in to Admin Portal
          </h1>
          <p className="text-sm leading-6 text-slate-500">
            Use your work email and password to access the admin dashboard.
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          <Button
            type="button"
            variant="outline"
            className="w-full cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400 hover:bg-slate-50 hover:text-slate-400"
            disabled
          >
            Continue with Google
          </Button>

          <div className="flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-slate-400">
            <Separator className="flex-1" />
            <span>or continue with work email</span>
            <Separator className="flex-1" />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="email">
              Work email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              className={cn(fieldErrors.email && "border-red-400 focus-visible:ring-red-500")}
              placeholder="name@company.com"
            />
            {fieldErrors.email ? (
              <p className="text-sm text-red-600">{fieldErrors.email}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-700" htmlFor="password">
                Password
              </label>
              <Link
                href="#"
                className="text-sm text-slate-400"
                onClick={(event) => event.preventDefault()}
              >
                Forgot password?
              </Link>
            </div>

            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.password)}
                className={cn(
                  "pr-11",
                  fieldErrors.password && "border-red-400 focus-visible:ring-red-500",
                )}
                placeholder="Enter your password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            {fieldErrors.password ? (
              <p className="text-sm text-red-600">{fieldErrors.password}</p>
            ) : null}
          </div>

          {formError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </div>
          ) : null}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Signing in...
              </>
            ) : (
              "Sign in to Admin Portal"
            )}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Don&apos;t have an account?{" "}
          <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/register">
            Create account
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
