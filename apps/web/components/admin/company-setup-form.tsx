"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  getCompanyProfile,
  updateCompanyProfile,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import {
  BusinessType,
  CompanyFormProfile,
  toCompanyFormProfile,
} from "@/lib/company-profile";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type CompanyFormState = {
  companyName: string;
  businessType: BusinessType;
  companyRegistrationNumber: string;
  vatRegistered: boolean;
  vatNumber: string;
  primaryContactName: string;
  businessEmail: string;
  businessPhone: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  postcode: string;
  country: string;
  timezone: string;
  currency: string;
};

type FieldErrors = Partial<Record<keyof CompanyFormState, string>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const initialFormState: CompanyFormState = {
  companyName: "",
  businessType: "limited_company",
  companyRegistrationNumber: "",
  vatRegistered: false,
  vatNumber: "",
  primaryContactName: "",
  businessEmail: "",
  businessPhone: "",
  addressLine1: "",
  addressLine2: "",
  city: "",
  postcode: "",
  country: "United Kingdom",
  timezone: "Europe/London",
  currency: "GBP",
};

const businessTypeOptions: Array<{ label: string; value: BusinessType }> = [
  { label: "Limited company", value: "limited_company" },
  { label: "Sole trader", value: "sole_trader" },
  { label: "Partnership", value: "partnership" },
  { label: "LLP", value: "llp" },
  { label: "Other", value: "other" },
];

function toFormState(profile: CompanyFormProfile): CompanyFormState {
  return {
    companyName: profile.companyName,
    businessType: profile.businessType,
    companyRegistrationNumber: profile.companyRegistrationNumber ?? "",
    vatRegistered: profile.vatRegistered,
    vatNumber: profile.vatNumber ?? "",
    primaryContactName: profile.primaryContactName,
    businessEmail: profile.businessEmail,
    businessPhone: profile.businessPhone,
    addressLine1: profile.addressLine1,
    addressLine2: profile.addressLine2 ?? "",
    city: profile.city,
    postcode: profile.postcode,
    country: profile.country,
    timezone: profile.timezone,
    currency: profile.currency,
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

function buildRegisteredAddress(form: CompanyFormState) {
  return [
    form.addressLine1,
    form.addressLine2,
    form.city,
    form.postcode,
    form.country,
  ]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(", ");
}

export function CompanySetupForm() {
  const router = useRouter();
  const [form, setForm] = useState<CompanyFormState>(initialFormState);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
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
          setForm(toFormState(toCompanyFormProfile(profile)));
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

    if (!form.businessType) {
      nextErrors.businessType = "Business type is required.";
    }

    if (!form.primaryContactName.trim()) {
      nextErrors.primaryContactName = "Primary contact name is required.";
    }

    if (!form.businessEmail.trim()) {
      nextErrors.businessEmail = "Business email is required.";
    } else if (!emailPattern.test(form.businessEmail.trim())) {
      nextErrors.businessEmail = "Enter a valid business email address.";
    }

    if (!form.businessPhone.trim()) {
      nextErrors.businessPhone = "Business phone number is required.";
    }

    if (!form.addressLine1.trim()) {
      nextErrors.addressLine1 = "Registered address is required.";
    }

    if (form.vatRegistered && !form.vatNumber.trim()) {
      nextErrors.vatNumber = "VAT number is required when VAT registered.";
    }

    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

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
        owner_name: form.primaryContactName.trim() || null,
        business_email: form.businessEmail.trim() || null,
        phone_number: form.businessPhone.trim() || null,
        registered_address: buildRegisteredAddress(form) || null,
      });

      setForm(toFormState(toCompanyFormProfile(updatedProfile)));
      router.replace("/admin");
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

            <Field label="Business type" error={fieldErrors.businessType}>
              <select
                value={form.businessType}
                onChange={(event) =>
                  updateField("businessType", event.target.value as BusinessType)
                }
                className={cn(
                  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  fieldClass(Boolean(fieldErrors.businessType)),
                )}
              >
                {businessTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              label="Company registration number"
              error={fieldErrors.companyRegistrationNumber}
              helper={
                form.businessType === "limited_company" || form.businessType === "llp"
                  ? "Recommended for Limited company and LLP."
                  : "Optional."
              }
            >
              <Input
                value={form.companyRegistrationNumber}
                onChange={(event) =>
                  updateField("companyRegistrationNumber", event.target.value)
                }
                className={fieldClass(Boolean(fieldErrors.companyRegistrationNumber))}
                placeholder="12345678"
              />
            </Field>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">VAT registered?</p>
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
                <button
                  type="button"
                  onClick={() => updateField("vatRegistered", true)}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm font-medium transition",
                    form.vatRegistered
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={() => updateField("vatRegistered", false)}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm font-medium transition",
                    !form.vatRegistered
                      ? "bg-white text-slate-800 shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  No
                </button>
              </div>
            </div>

            {form.vatRegistered ? (
              <Field label="VAT number" error={fieldErrors.vatNumber}>
                <Input
                  value={form.vatNumber}
                  onChange={(event) => updateField("vatNumber", event.target.value)}
                  className={fieldClass(Boolean(fieldErrors.vatNumber))}
                  placeholder="GB123456789"
                />
              </Field>
            ) : null}
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
            <Field label="Primary contact name" error={fieldErrors.primaryContactName}>
              <Input
                value={form.primaryContactName}
                onChange={(event) => updateField("primaryContactName", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.primaryContactName))}
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

            <Field label="Business phone number" error={fieldErrors.businessPhone}>
              <Input
                type="tel"
                value={form.businessPhone}
                onChange={(event) => updateField("businessPhone", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.businessPhone))}
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
              Business address and defaults
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              These defaults keep sites, reports, and payroll aligned.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Address line 1" error={fieldErrors.addressLine1}>
              <Input
                value={form.addressLine1}
                onChange={(event) => updateField("addressLine1", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.addressLine1))}
                placeholder="1 High Street"
              />
            </Field>

            <Field label="Address line 2" helper="Optional." error={fieldErrors.addressLine2}>
              <Input
                value={form.addressLine2}
                onChange={(event) => updateField("addressLine2", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.addressLine2))}
                placeholder="Unit or building name"
              />
            </Field>

            <Field label="Town / city" error={fieldErrors.city}>
              <Input
                value={form.city}
                onChange={(event) => updateField("city", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.city))}
                placeholder="London"
              />
            </Field>

            <Field label="Postcode" error={fieldErrors.postcode}>
              <Input
                value={form.postcode}
                onChange={(event) => updateField("postcode", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.postcode))}
                placeholder="SW1A 1AA"
              />
            </Field>

            <Field label="Country" error={fieldErrors.country}>
              <Input
                value={form.country}
                onChange={(event) => updateField("country", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.country))}
              />
            </Field>

            <Field label="Timezone" error={fieldErrors.timezone}>
              <Input
                value={form.timezone}
                onChange={(event) => updateField("timezone", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.timezone))}
              />
            </Field>

            <Field label="Currency" error={fieldErrors.currency}>
              <Input
                value={form.currency}
                onChange={(event) => updateField("currency", event.target.value)}
                className={fieldClass(Boolean(fieldErrors.currency))}
              />
            </Field>
          </div>
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
