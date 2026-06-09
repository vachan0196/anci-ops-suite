"use client";

import { ArrowLeft, CheckCircle2, Loader2, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getStaffProfile,
  listStaffRoles,
  listStores,
  type StaffProfile,
  type StaffRole,
  type StaffSafeEditUpdate,
  type Store,
  updateStaffSafeProfile,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type StaffProfileDetailProps = {
  staffId: string;
};

type ContractType = StaffSafeEditUpdate["contract_type"];

type SafeEditFormState = {
  job_title: string;
  phone: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  contract_type: ContractType | "";
  weekly_working_hour_soft_cap: string;
  monthly_working_hour_soft_cap: string;
  notes: string;
};

const initialForm: SafeEditFormState = {
  job_title: "",
  phone: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  contract_type: "",
  weekly_working_hour_soft_cap: "",
  monthly_working_hour_soft_cap: "",
  notes: "",
};

function formatDate(value?: string) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function buildFormState(profile: StaffProfile): SafeEditFormState {
  return {
    job_title: profile.job_title ?? "",
    phone: profile.phone ?? "",
    emergency_contact_name: profile.emergency_contact_name ?? "",
    emergency_contact_phone: profile.emergency_contact_phone ?? "",
    contract_type:
      profile.contract_type === "full_time" ||
      profile.contract_type === "part_time" ||
      profile.contract_type === "zero_hours"
        ? profile.contract_type
        : "",
    weekly_working_hour_soft_cap: formatSoftCapInput(
      profile.weekly_working_hour_soft_cap,
    ),
    monthly_working_hour_soft_cap: formatSoftCapInput(
      profile.monthly_working_hour_soft_cap,
    ),
    notes: profile.notes ?? "",
  };
}

function buildSafePayload(form: SafeEditFormState): StaffSafeEditUpdate {
  return {
    job_title: form.job_title,
    phone: form.phone,
    emergency_contact_name: form.emergency_contact_name,
    emergency_contact_phone: form.emergency_contact_phone,
    contract_type: form.contract_type || null,
    weekly_working_hour_soft_cap: form.weekly_working_hour_soft_cap.trim() || null,
    monthly_working_hour_soft_cap: form.monthly_working_hour_soft_cap.trim() || null,
    notes: form.notes,
  };
}

function formatSoftCapInput(value: string | number | null | undefined) {
  return value == null ? "" : String(value);
}

function validateSoftCapInput(value: string, label: string) {
  const trimmed = value.trim();

  if (!trimmed) {
    return null;
  }

  const numericValue = Number(trimmed);

  if (Number.isNaN(numericValue) || numericValue < 0) {
    return `${label} must be zero or more.`;
  }

  return null;
}

function getLocationName(profile: StaffProfile, stores: Store[]) {
  if (!profile.store_id) {
    return "Unassigned";
  }

  return stores.find((store) => store.id === profile.store_id)?.name ?? "Unknown location";
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have access to this staff profile.";
    }

    if (error.status === 404) {
      return "This staff member could not be found.";
    }

    if (error.status === 422) {
      return error.message || "Check the staff details and try again.";
    }

    if (error.status >= 500) {
      return "Could not load staff profile. Please try again.";
    }

    return error.message || "Could not load staff profile. Please try again.";
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server. Please try again.";
  }

  return "Could not load staff profile. Please try again.";
}

function getSaveErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have permission to update this staff profile.";
    }

    if (error.status === 404) {
      return "This staff member could not be found.";
    }

    if (error.status === 422 || error.status === 400) {
      return error.message || "Check the staff details and try again.";
    }

    return error.message || "Staff profile could not be saved.";
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server.";
  }

  return "Staff profile could not be saved.";
}

function isNotFoundError(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}

export function StaffProfileDetail({ staffId }: StaffProfileDetailProps) {
  const router = useRouter();
  const normalisedStaffId = staffId.trim();
  const [profile, setProfile] = useState<StaffProfile | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [roles, setRoles] = useState<StaffRole[]>([]);
  const [form, setForm] = useState<SafeEditFormState>(initialForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    let isMounted = true;

    async function loadProfile(accessToken: string) {
      setIsLoading(true);
      setErrorMessage(null);
      setSaveMessage(null);
      setSaveError(null);
      setIsNotFound(false);

      if (!normalisedStaffId) {
        setProfile(null);
        setIsNotFound(true);
        setIsLoading(false);
        return;
      }

      try {
        const [staffProfile, storeRows, roleRows] = await Promise.all([
          getStaffProfile(accessToken, normalisedStaffId),
          listStores(accessToken),
          listStaffRoles(accessToken, normalisedStaffId).catch((error) => {
            if (error instanceof ApiError && error.status === 404) {
              return [];
            }
            throw error;
          }),
        ]);

        if (isMounted) {
          setProfile(staffProfile);
          setStores(storeRows);
          setRoles(roleRows);
          setForm(buildFormState(staffProfile));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setProfile(null);
          setErrorMessage(isNotFoundError(error) ? null : getErrorMessage(error));
          setIsNotFound(isNotFoundError(error));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadProfile(token);

    return () => {
      isMounted = false;
    };
  }, [normalisedStaffId, router]);

  const locationName = useMemo(
    () => (profile ? getLocationName(profile, stores) : "Unassigned"),
    [profile, stores],
  );

  function updateField<Key extends keyof SafeEditFormState>(
    key: Key,
    value: SafeEditFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setSaveMessage(null);
    setSaveError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveMessage(null);
    setSaveError(null);

    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    if (!normalisedStaffId) {
      setIsNotFound(true);
      return;
    }

    const softCapError =
      validateSoftCapInput(
        form.weekly_working_hour_soft_cap,
        "Weekly working-hour soft cap",
      ) ||
      validateSoftCapInput(
        form.monthly_working_hour_soft_cap,
        "Monthly working-hour soft cap",
      );

    if (softCapError) {
      setSaveError(softCapError);
      return;
    }

    setIsSaving(true);

    try {
      await updateStaffSafeProfile(
        token,
        normalisedStaffId,
        buildSafePayload(form),
      );
      const refreshedProfile = await getStaffProfile(token, normalisedStaffId);
      setProfile(refreshedProfile);
      setForm(buildFormState(refreshedProfile));
      setSaveMessage("Staff profile saved.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAccessToken();
        router.replace("/admin/login");
        return;
      }

      if (isNotFoundError(error)) {
        setProfile(null);
        setIsNotFound(true);
        return;
      }

      setSaveError(getSaveErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="flex items-center gap-3 p-6 text-sm text-slate-600">
          <Loader2 className="size-4 animate-spin" />
          Loading profile...
        </CardContent>
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card className="border-red-200 bg-red-50 shadow-sm">
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-red-700">{errorMessage}</p>
          <Button type="button" variant="outline" onClick={() => window.location.reload()}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (isNotFound || !profile) {
    return (
      <Card className="border-slate-200 bg-white shadow-sm">
        <CardContent className="flex flex-col gap-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">
              Staff member not found
            </h3>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
              This staff member may not exist or you may not have access.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => router.push("/admin/staff")}>
            Back to Staff
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit} noValidate>
      <Button
        type="button"
        variant="outline"
        onClick={() => router.push("/admin/staff")}
        className="gap-2"
      >
        <ArrowLeft className="size-4" />
        Back to Staff
      </Button>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-6 p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
                Staff Profile
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                {profile.display_name}
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                {form.job_title || "Job title not set"}
              </p>
            </div>
            <span
              className={cn(
                "inline-flex w-fit rounded-full px-3 py-1.5 text-sm font-medium",
                profile.is_active !== false
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-slate-100 text-slate-500",
              )}
            >
              {profile.is_active !== false ? "Active" : "Inactive"}
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DetailItem label="Location">{locationName}</DetailItem>
            <DetailItem label="Added">{formatDate(profile.created_at)}</DetailItem>
          </div>

          <section className="space-y-2">
            <p className="text-sm font-medium text-slate-700">Roles</p>
            <div className="flex flex-wrap gap-2">
              {roles.length > 0 ? (
                roles.map((role) => (
                  <span
                    key={role.id}
                    className="rounded-full bg-blue-50 px-3 py-1.5 text-sm font-medium capitalize text-blue-700"
                  >
                    {role.role}
                  </span>
                ))
              ) : (
                <span className="text-sm text-slate-500">No role</span>
              )}
            </div>
          </section>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">
              Operational details
            </h3>
          </div>

          {saveError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {saveError}
            </div>
          ) : null}

          {saveMessage ? (
            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              <CheckCircle2 className="size-4" />
              {saveMessage}
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Job Title">
              <Input
                value={form.job_title}
                onChange={(event) => updateField("job_title", event.target.value)}
                disabled={isSaving}
              />
            </Field>

            <Field label="Phone Number">
              <Input
                type="tel"
                value={form.phone}
                onChange={(event) => updateField("phone", event.target.value)}
                disabled={isSaving}
              />
            </Field>

            <Field label="Emergency Contact Name">
              <Input
                value={form.emergency_contact_name}
                onChange={(event) =>
                  updateField("emergency_contact_name", event.target.value)
                }
                disabled={isSaving}
              />
            </Field>

            <Field label="Emergency Contact Phone">
              <Input
                type="tel"
                value={form.emergency_contact_phone}
                onChange={(event) =>
                  updateField("emergency_contact_phone", event.target.value)
                }
                disabled={isSaving}
              />
            </Field>

            <Field label="Contract Type">
              <select
                value={form.contract_type ?? ""}
                onChange={(event) =>
                  updateField(
                    "contract_type",
                    event.target.value as SafeEditFormState["contract_type"],
                  )
                }
                className={selectClassName}
                disabled={isSaving}
              >
                <option value="">Not set</option>
                <option value="full_time">Full time</option>
                <option value="part_time">Part time</option>
                <option value="zero_hours">Zero hours</option>
              </select>
            </Field>
          </div>

          <section className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-800">
                Working hour soft caps
              </h4>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Used for rota planning warnings later. These do not affect pay and do
                not block scheduling.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <Field label="Weekly working-hour soft cap">
                <Input
                  type="number"
                  min="0"
                  step="0.25"
                  value={form.weekly_working_hour_soft_cap}
                  onChange={(event) =>
                    updateField("weekly_working_hour_soft_cap", event.target.value)
                  }
                  disabled={isSaving}
                />
              </Field>

              <Field label="Monthly working-hour soft cap">
                <Input
                  type="number"
                  min="0"
                  step="0.25"
                  value={form.monthly_working_hour_soft_cap}
                  onChange={(event) =>
                    updateField("monthly_working_hour_soft_cap", event.target.value)
                  }
                  disabled={isSaving}
                />
              </Field>
            </div>
          </section>

          <Field
            label="Notes"
            helper="Do not store NI numbers, right-to-work document details, passport/BRP/share-code details, medical information, payroll-sensitive data, or other sensitive personal data in notes."
          >
            <textarea
              value={form.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              className={textareaClassName}
              rows={5}
              disabled={isSaving}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/admin/staff")}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          className="bg-[#3F4A42] text-white hover:bg-[#303832]"
          disabled={isSaving}
        >
          {isSaving ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 size-4" />
              Save Profile
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

const selectClassName =
  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

const textareaClassName =
  "flex min-h-28 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

function DetailItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">
        {label}
      </p>
      <div className="mt-2 break-words text-sm font-medium text-slate-800">{children}</div>
    </div>
  );
}

function Field({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {helper ? <span className="block text-sm leading-6 text-amber-700">{helper}</span> : null}
    </label>
  );
}
