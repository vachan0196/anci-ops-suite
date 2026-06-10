"use client";

import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Loader2,
  MapPin,
  Pencil,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, type ReactNode, useEffect, useState } from "react";

import {
  ApiError,
  getStore,
  listStores,
  restoreAdminSession,
  type Store,
  type StoreUpdate,
  updateStore,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type SiteFormState = {
  code: string;
  name: string;
  timezone: string;
  address_line1: string;
  city: string;
  postcode: string;
  phone: string;
  email: string;
  notes: string;
};

type SiteFormErrors = Partial<Record<keyof SiteFormState, string>>;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function getAdminToken() {
  const existingToken = getAccessToken();
  if (existingToken) {
    return existingToken;
  }

  return restoreAdminSession();
}

function getSiteErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Please sign in again.";
    }

    if (error.status === 403) {
      return "You do not have permission to manage sites.";
    }

    if (error.status === 404) {
      return "This site could not be found.";
    }

    if (error.status === 409) {
      return error.message || "A site with this code already exists.";
    }

    if (error.status === 422) {
      return error.message || "Check the site details and try again.";
    }

    return error.message || fallback;
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server. Please try again.";
  }

  return fallback;
}

function formatAddress(store: Store) {
  return [store.address_line1, store.city, store.postcode]
    .map((part) => part?.trim())
    .filter(Boolean)
    .join(", ");
}

function toFormState(store: Store): SiteFormState {
  return {
    code: store.code ?? "",
    name: store.name ?? "",
    timezone: store.timezone ?? "Europe/London",
    address_line1: store.address_line1 ?? "",
    city: store.city ?? "",
    postcode: store.postcode ?? "",
    phone: store.phone ?? "",
    email: store.email ?? "",
    notes: store.notes ?? "",
  };
}

function buildUpdatePayload(form: SiteFormState): StoreUpdate {
  return {
    code: form.code.trim() || null,
    name: form.name.trim(),
    timezone: form.timezone.trim() || "Europe/London",
    address_line1: form.address_line1.trim() || null,
    city: form.city.trim() || null,
    postcode: form.postcode.trim() || null,
    phone: form.phone.trim() || null,
    email: form.email.trim() || null,
    notes: form.notes.trim() || null,
  };
}

export function SitesManagement() {
  const router = useRouter();
  const [sites, setSites] = useState<Store[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSites() {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const token = await getAdminToken();
        const stores = await listStores(token);

        if (isMounted) {
          setSites(stores);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setErrorMessage(
            getSiteErrorMessage(error, "Sites could not be loaded right now."),
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSites();

    return () => {
      isMounted = false;
    };
  }, [router]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-[#3F4A42]">Site management</p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-950">
            Sites and locations
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Review existing locations and keep their profile details up to date.
          </p>
        </div>
        <Button asChild className="bg-[#3F4A42] text-white hover:bg-[#303832]">
          <Link href="/admin/sites/new">
            <Plus className="mr-2 size-4" />
            Add Site
          </Link>
        </Button>
      </div>

      {errorMessage ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-600 shadow-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading sites...
        </div>
      ) : sites.length === 0 && !errorMessage ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center shadow-sm">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-[#3F4A42]/10 text-[#3F4A42]">
            <Building2 className="size-6" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-slate-950">No sites yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
            Create your first location so rota, staff, and operations can be tied to
            a real site.
          </p>
          <Button asChild className="mt-5 bg-[#3F4A42] text-white hover:bg-[#303832]">
            <Link href="/admin/sites/new">
              <Plus className="mr-2 size-4" />
              Add Site
            </Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {sites.map((site) => {
            const address = formatAddress(site);

            return (
              <Card key={site.id} className="border-slate-200 bg-white shadow-sm">
                <CardContent className="space-y-5 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-lg font-semibold text-slate-950">
                        {site.name}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {site.code || "No site code"}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-medium",
                        site.is_active === false
                          ? "bg-slate-100 text-slate-500"
                          : "bg-emerald-50 text-emerald-700",
                      )}
                    >
                      {site.is_active === false ? "Inactive" : "Active"}
                    </span>
                  </div>

                  <div className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
                    <div className="flex gap-2">
                      <MapPin className="mt-0.5 size-4 shrink-0 text-[#3F4A42]" />
                      <span>{address || "No address added"}</span>
                    </div>
                    <div>
                      <span className="font-medium text-slate-700">Phone: </span>
                      {site.phone || "Not added"}
                    </div>
                    <div>
                      <span className="font-medium text-slate-700">Time zone: </span>
                      {site.timezone || "Not added"}
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
                    <Button asChild variant="outline">
                      <Link href={`/admin/sites/${site.id}`}>
                        <Pencil className="mr-2 size-4" />
                        Edit / View
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function SiteEditForm({ siteId }: { siteId: string }) {
  const router = useRouter();
  const [form, setForm] = useState<SiteFormState | null>(null);
  const [errors, setErrors] = useState<SiteFormErrors>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSite() {
      setIsLoading(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      try {
        const token = await getAdminToken();
        const store = await getStore(token, siteId);

        if (isMounted) {
          setForm(toFormState(store));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setErrorMessage(getSiteErrorMessage(error, "Site could not be loaded."));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSite();

    return () => {
      isMounted = false;
    };
  }, [router, siteId]);

  function updateField<Key extends keyof SiteFormState>(
    key: Key,
    value: SiteFormState[Key],
  ) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setSuccessMessage(null);
  }

  function validate() {
    if (!form) {
      return false;
    }

    const nextErrors: SiteFormErrors = {};

    if (!form.name.trim()) {
      nextErrors.name = "Location name is required.";
    }

    if (!form.timezone.trim()) {
      nextErrors.timezone = "Time zone is required.";
    }

    if (form.email.trim() && !emailPattern.test(form.email.trim())) {
      nextErrors.email = "Enter a valid site email address.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!form || !validate()) {
      setErrorMessage("Check the highlighted fields and try again.");
      return;
    }

    setIsSaving(true);

    try {
      const token = await getAdminToken();
      const updatedStore = await updateStore(token, siteId, buildUpdatePayload(form));
      setForm(toFormState(updatedStore));
      setSuccessMessage("Site details saved.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAccessToken();
        router.replace("/admin/login");
        return;
      }

      setErrorMessage(getSiteErrorMessage(error, "Site details could not be saved."));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-600 shadow-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading site details...
      </div>
    );
  }

  if (!form) {
    return (
      <div className="space-y-5">
        <Button asChild variant="outline">
          <Link href="/admin/sites">
            <ArrowLeft className="mr-2 size-4" />
            Back to Sites
          </Link>
        </Button>
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage || "This site could not be loaded."}
        </div>
      </div>
    );
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Button asChild variant="outline">
            <Link href="/admin/sites">
              <ArrowLeft className="mr-2 size-4" />
              Back to Sites
            </Link>
          </Button>
          <h2 className="mt-5 text-2xl font-semibold text-slate-950">
            Edit location
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Update normal site profile details. Lifecycle actions are managed
            separately.
          </p>
        </div>
      </div>

      {errorMessage ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      {successMessage ? (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <CheckCircle2 className="size-4" />
          {successMessage}
        </div>
      ) : null}

      <Card className="border-slate-200 bg-white shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">
              Location information
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              These details are saved to the existing backend store profile.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Site ID / Site Code" error={errors.code}>
              <Input
                value={form.code}
                onChange={(event) => updateField("code", event.target.value)}
                className={fieldClass(Boolean(errors.code))}
                placeholder="SITE-001"
              />
            </Field>
            <Field label="Location Name" error={errors.name}>
              <Input
                value={form.name}
                onChange={(event) => updateField("name", event.target.value)}
                className={fieldClass(Boolean(errors.name))}
                placeholder="Coalville Store"
              />
            </Field>
            <Field label="Street Address" error={errors.address_line1}>
              <Input
                value={form.address_line1}
                onChange={(event) => updateField("address_line1", event.target.value)}
                className={fieldClass(Boolean(errors.address_line1))}
                placeholder="Street address"
              />
            </Field>
            <Field label="City" error={errors.city}>
              <Input
                value={form.city}
                onChange={(event) => updateField("city", event.target.value)}
                className={fieldClass(Boolean(errors.city))}
                placeholder="City"
              />
            </Field>
            <Field label="Postcode" error={errors.postcode}>
              <Input
                value={form.postcode}
                onChange={(event) => updateField("postcode", event.target.value)}
                className={fieldClass(Boolean(errors.postcode))}
                placeholder="Postcode"
              />
            </Field>
            <Field label="Site Phone Number" error={errors.phone}>
              <Input
                type="tel"
                value={form.phone}
                onChange={(event) => updateField("phone", event.target.value)}
                className={fieldClass(Boolean(errors.phone))}
                placeholder="+44 1234 567890"
              />
            </Field>
            <Field label="Site Email" error={errors.email}>
              <Input
                type="email"
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                className={fieldClass(Boolean(errors.email))}
                placeholder="location@example.com"
              />
            </Field>
            <Field label="Time Zone" error={errors.timezone}>
              <select
                value={form.timezone}
                onChange={(event) => updateField("timezone", event.target.value)}
                className={cn(selectClassName, fieldClass(Boolean(errors.timezone)))}
              >
                <option value="Europe/London">GMT (London) / Europe/London</option>
              </select>
            </Field>
          </div>

          <Field label="Notes" error={errors.notes}>
            <textarea
              value={form.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              className={cn(textareaClassName, fieldClass(Boolean(errors.notes)))}
              placeholder="Additional details about this location..."
            />
          </Field>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/admin/sites")}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          className="bg-[#3F4A42] text-white hover:bg-[#303832]"
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}

const selectClassName =
  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

const textareaClassName =
  "flex min-h-28 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {error ? <span className="block text-sm text-red-600">{error}</span> : null}
    </label>
  );
}
