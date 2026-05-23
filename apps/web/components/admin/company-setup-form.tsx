"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  type CompanyProfileResponse,
  getCompanyProfile,
  updateCompanyProfile,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type CompanyFormState = {
  companyName: string;
  ownerName: string;
  businessEmail: string;
  phoneNumber: string;
  registeredAddress: string;
};

type FieldErrors = Partial<Record<keyof CompanyFormState, string>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const initialFormState: CompanyFormState = {
  companyName: "",
  ownerName: "",
  businessEmail: "",
  phoneNumber: "",
  registeredAddress: "",
};

function toFormState(profile: CompanyProfileResponse): CompanyFormState {
  return {
    companyName: profile.company_name ?? "",
    ownerName: profile.owner_name ?? "",
    businessEmail: profile.business_email ?? "",
    phoneNumber: profile.phone_number ?? "",
    registeredAddress: profile.registered_address ?? "",
  };
}

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have permission to update this company profile.";
    }

    if (error.status === 422) {
      return error.message || "Check the company profile details and try again.";
    }

    return error.message;
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server. Please try again.";
  }

  return "Something went wrong. Please try again.";
}

export function CompanySetupForm() {
  const router = useRouter();
  const [form, setForm] = useState<CompanyFormState>(initialFormState);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    let isMounted = true;

    async function loadProfile(accessToken: string) {
      try {
        const profile = await getCompanyProfile(accessToken);

        if (isMounted) {
          setForm(toFormState(profile));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setFormError(getErrorMessage(error));
        }
      } finally {
        if (isMounted) {
          setIsLoadingProfile(false);
        }
      }
    }

    loadProfile(token);

    return () => {
      isMounted = false;
    };
  }, [router]);

  function updateField<Key extends keyof CompanyFormState>(
    key: Key,
    value: CompanyFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function validateForm() {
    const nextErrors: FieldErrors = {};

    if (!form.companyName.trim()) {
      nextErrors.companyName = "Company or trading name is required.";
    }

    if (!form.ownerName.trim()) {
      nextErrors.ownerName = "Primary contact name is required.";
    }

    if (!form.businessEmail.trim()) {
      nextErrors.businessEmail = "Business email is required.";
    } else if (!emailPattern.test(form.businessEmail.trim())) {
      nextErrors.businessEmail = "Enter a valid business email address.";
    }

    if (!form.phoneNumber.trim()) {
      nextErrors.phoneNumber = "Business phone number is required.";
    }

    if (!form.registeredAddress.trim()) {
      nextErrors.registeredAddress = "Registered address is required.";
    }

    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    if (!validateForm()) {
      setFormError("Check the highlighted fields and try again.");
      return;
    }

    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    setIsSaving(true);

    try {
      const updatedProfile = await updateCompanyProfile(token, {
        company_name: form.companyName.trim() || null,
        owner_name: form.ownerName.trim() || null,
        business_email: form.businessEmail.trim() || null,
        phone_number: form.phoneNumber.trim() || null,
        registered_address: form.registeredAddress.trim() || null,
      });

      setForm(toFormState(updatedProfile));
      setSuccessMessage("Company profile saved.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAccessToken();
        router.replace("/admin/login");
        return;
      }

      setFormError(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoadingProfile) {
    return (
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-6 text-sm text-slate-500">
          Loading company profile...
        </CardContent>
      </Card>
    );
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate>
      {formError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {formError}
        </div>
      ) : null}
      {successMessage ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {successMessage}
        </div>
      ) : null}

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Business identity</h2>
            <p className="mt-1 text-sm text-slate-500">
              Tell ForecourtOS who operates this workspace.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Company / trading name" error={fieldErrors.companyName}>
              <Input
                value={form.companyName}
                onChange={(event) => updateField("companyName", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.companyName))}
                placeholder="Example Forecourts Ltd"
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Primary contact</h2>
            <p className="mt-1 text-sm text-slate-500">
              Add the person responsible for the business account.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <Field label="Primary contact name" error={fieldErrors.ownerName}>
              <Input
                value={form.ownerName}
                onChange={(event) => updateField("ownerName", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.ownerName))}
                placeholder="Vachan Sardar"
              />
            </Field>

            <Field label="Business email" error={fieldErrors.businessEmail}>
              <Input
                type="email"
                autoComplete="email"
                value={form.businessEmail}
                onChange={(event) => updateField("businessEmail", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.businessEmail))}
                placeholder="owner@example.com"
              />
            </Field>

            <Field label="Business phone number" error={fieldErrors.phoneNumber}>
              <Input
                type="tel"
                value={form.phoneNumber}
                onChange={(event) => updateField("phoneNumber", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.phoneNumber))}
                placeholder="020 0000 0000"
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Registered address
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              This is saved as the backend company profile registered address.
            </p>
          </div>

          <Field label="Registered address" error={fieldErrors.registeredAddress}>
            <textarea
              value={form.registeredAddress}
              onChange={(event) => updateField("registeredAddress", event.target.value)}
              className={cn(
                "min-h-28 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                fieldClass(Boolean(fieldErrors.registeredAddress)),
              )}
              placeholder={"1 High Street\nLondon\nSW1A 1AA"}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={() => router.push("/admin")}>
          Cancel / Back to dashboard
        </Button>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "Saving..." : "Save company setup"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  helper,
  error,
  children,
}: {
  label: string;
  helper?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="space-y-2">
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {helper ? <span className="block text-xs text-slate-500">{helper}</span> : null}
      {error ? <span className="block text-sm text-red-600">{error}</span> : null}
    </label>
  );
}
