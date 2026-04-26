"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { adminRegister, ApiError } from "@/lib/api-client";
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

type FieldErrors = {
  full_name?: string;
  email?: string;
  password?: string;
  confirm_password?: string;
  accepted_terms?: string;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getFieldMessage(value: unknown, fallback: string) {
  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value) && typeof value[0] === "string") {
    return value[0];
  }

  return fallback;
}

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

      if (
        fieldValue === "full_name" ||
        fieldValue === "email" ||
        fieldValue === "password" ||
        fieldValue === "confirm_password" ||
        fieldValue === "accepted_terms"
      ) {
        const field: keyof FieldErrors = fieldValue;
        accumulator[field] = message;
      }

      return accumulator;
    }, {});
  }

  if (typeof details === "object") {
    const record = details as Record<string, unknown>;
    const fieldErrors: FieldErrors = {};

    for (const field of [
      "full_name",
      "email",
      "password",
      "confirm_password",
      "accepted_terms",
    ] as const) {
      if (field in record) {
        fieldErrors[field] = getFieldMessage(record[field], error.message);
      }
    }

    return fieldErrors;
  }

  return {};
}

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

export function AdminRegisterForm() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validateForm() {
    const nextErrors: FieldErrors = {};

    if (!fullName.trim()) {
      nextErrors.full_name = "Full name is required.";
    }

    if (!email.trim()) {
      nextErrors.email = "Email is required.";
    } else if (!emailPattern.test(email.trim())) {
      nextErrors.email = "Enter a valid email address.";
    }

    if (!password) {
      nextErrors.password = "Password is required.";
    } else if (password.length < 8) {
      nextErrors.password = "Password must be at least 8 characters.";
    }

    if (!confirmPassword) {
      nextErrors.confirm_password = "Confirm password is required.";
    } else if (confirmPassword !== password) {
      nextErrors.confirm_password = "Passwords must match.";
    }

    if (!acceptedTerms) {
      nextErrors.accepted_terms = "You must agree to the Terms of Service.";
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
      await adminRegister({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });

      router.replace("/admin/login");
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
      </CardHeader>

      <CardContent className="px-8 pb-8 pt-8">
        <div className="mb-6 space-y-2">
          <h1 className="text-xl font-semibold text-slate-950">
            Create your ForecourtOS account
          </h1>
          <p className="text-sm leading-6 text-slate-500">
            Start by creating the owner account for your business.
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="full_name">
              Full name
            </label>
            <Input
              id="full_name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              aria-invalid={Boolean(fieldErrors.full_name)}
              className={fieldClass(Boolean(fieldErrors.full_name))}
              placeholder="Jane Smith"
            />
            {fieldErrors.full_name ? (
              <p className="text-sm text-red-600">{fieldErrors.full_name}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              className={fieldClass(Boolean(fieldErrors.email))}
              placeholder="name@company.com"
            />
            {fieldErrors.email ? (
              <p className="text-sm text-red-600">{fieldErrors.email}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.password)}
                className={cn("pr-11", fieldClass(Boolean(fieldErrors.password)))}
                placeholder="Create a password"
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

          <div className="space-y-2">
            <label
              className="text-sm font-medium text-slate-700"
              htmlFor="confirm_password"
            >
              Confirm password
            </label>
            <div className="relative">
              <Input
                id="confirm_password"
                type={showConfirmPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.confirm_password)}
                className={cn("pr-11", fieldClass(Boolean(fieldErrors.confirm_password)))}
                placeholder="Confirm your password"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword((current) => !current)}
                className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-500 transition hover:text-slate-700"
                aria-label={showConfirmPassword ? "Hide password" : "Show password"}
              >
                {showConfirmPassword ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </button>
            </div>
            {fieldErrors.confirm_password ? (
              <p className="text-sm text-red-600">{fieldErrors.confirm_password}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <label className="flex items-start gap-3 text-sm leading-6 text-slate-600">
              <input
                type="checkbox"
                checked={acceptedTerms}
                onChange={(event) => setAcceptedTerms(event.target.checked)}
                className="mt-1 size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-600"
              />
              <span>
                By creating an account you agree to our Terms of Service
              </span>
            </label>
            {fieldErrors.accepted_terms ? (
              <p className="text-sm text-red-600">{fieldErrors.accepted_terms}</p>
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
                Creating account...
              </>
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link className="font-medium text-blue-600 hover:text-blue-700" href="/admin/login">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
