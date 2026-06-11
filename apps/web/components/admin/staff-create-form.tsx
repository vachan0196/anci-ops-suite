"use client";

import { ArrowLeft, CheckCircle2, Loader2, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import {
  addStaffRole,
  ApiError,
  createAdminUser,
  createStaffProfile,
  listStores,
  type Store,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { staffRoleOptions } from "@/lib/staff-roles";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type StaffAccountStatus = "active" | "inactive";

type StaffCreateFormState = {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  storeId: string;
  roles: string[];
  baseHourlyRate: string;
  weeklyWorkingHourSoftCap: string;
  monthlyWorkingHourSoftCap: string;
  username: string;
  temporaryPassword: string;
  confirmTemporaryPassword: string;
  accountStatus: StaffAccountStatus;
};

type StaffCreateFieldErrors = Partial<Record<keyof StaffCreateFormState, string>>;

type SubmitProgress = {
  userId: string | null;
  staffId: string | null;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const initialForm: StaffCreateFormState = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  storeId: "",
  roles: [],
  baseHourlyRate: "",
  weeklyWorkingHourSoftCap: "",
  monthlyWorkingHourSoftCap: "",
  username: "",
  temporaryPassword: "",
  confirmTemporaryPassword: "",
  accountStatus: "active",
};

function buildStaffDisplayName(
  staff: Pick<StaffCreateFormState, "firstName" | "lastName">,
) {
  return `${staff.firstName} ${staff.lastName}`.trim();
}

function buildAdminUserPayload(staff: StaffCreateFormState) {
  return {
    email: staff.email.trim(),
    password: staff.temporaryPassword,
    full_name: buildStaffDisplayName(staff),
    role: "member" as const,
  };
}

function buildStaffProfilePayload(
  staff: StaffCreateFormState,
  userId: string,
  storeId: string,
) {
  const roles = staff.roles.map((role) => role.trim()).filter(Boolean);
  const hourlyRate = staff.baseHourlyRate.trim();
  const weeklySoftCap = staff.weeklyWorkingHourSoftCap.trim();
  const monthlySoftCap = staff.monthlyWorkingHourSoftCap.trim();

  return {
    user_id: userId,
    store_id: storeId,
    employee_username: staff.username.trim(),
    employee_password: staff.temporaryPassword,
    display_name: buildStaffDisplayName(staff),
    job_title: roles[0] ?? null,
    weekly_working_hour_soft_cap: weeklySoftCap || null,
    monthly_working_hour_soft_cap: monthlySoftCap || null,
    hourly_rate: hourlyRate || null,
    pay_type: hourlyRate ? ("hourly" as const) : null,
    phone: staff.phone.trim() || null,
    is_active: staff.accountStatus === "active",
  };
}

function getStaffSaveErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 409 && error.code === "AUTH_EMAIL_EXISTS") {
      return "Email is already registered.";
    }

    if (error.status === 409) {
      return error.message || "A matching staff record already exists.";
    }

    if (error.status === 422) {
      return error.message || "Check the staff details and try again.";
    }

    if (error.status === 403) {
      return "You do not have permission to create staff.";
    }

    return error.message;
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server.";
  }

  return "Staff member could not be fully added.";
}

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

export function StaffCreateForm() {
  const router = useRouter();
  const [stores, setStores] = useState<Store[]>([]);
  const [form, setForm] = useState<StaffCreateFormState>(initialForm);
  const [errors, setErrors] = useState<StaffCreateFieldErrors>({});
  const [progress, setProgress] = useState<SubmitProgress>({
    userId: null,
    staffId: null,
  });
  const [isLoadingStores, setIsLoadingStores] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const activeStores = useMemo(
    () => stores.filter((store) => store.is_active !== false),
    [stores],
  );

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    let isMounted = true;

    async function loadStores(accessToken: string) {
      setIsLoadingStores(true);
      setFormError(null);

      try {
        const storeRows = await listStores(accessToken);

        if (isMounted) {
          setStores(storeRows);
          const firstActiveStore = storeRows.find((store) => store.is_active !== false);
          setForm((current) => ({
            ...current,
            storeId: current.storeId || firstActiveStore?.id || "",
          }));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setFormError(getStaffSaveErrorMessage(error));
        }
      } finally {
        if (isMounted) {
          setIsLoadingStores(false);
        }
      }
    }

    loadStores(token);

    return () => {
      isMounted = false;
    };
  }, [router]);

  function updateField<Key extends keyof StaffCreateFormState>(
    key: Key,
    value: StaffCreateFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setSuccessMessage(null);
  }

  function toggleRole(role: string) {
    setForm((current) => ({
      ...current,
      roles: current.roles.includes(role)
        ? current.roles.filter((item) => item !== role)
        : [...current.roles, role],
    }));
    setErrors((current) => {
      const next = { ...current };
      delete next.roles;
      return next;
    });
  }

  function validateForm() {
    const nextErrors: StaffCreateFieldErrors = {};

    if (!form.firstName.trim()) {
      nextErrors.firstName = "First name is required.";
    }

    if (!form.lastName.trim()) {
      nextErrors.lastName = "Last name is required.";
    }

    if (!form.email.trim()) {
      nextErrors.email = "Email address is required.";
    }

    if (form.email.trim() && !emailPattern.test(form.email.trim())) {
      nextErrors.email = "Enter a valid email address.";
    }

    if (!form.storeId) {
      nextErrors.storeId = "Choose a location.";
    }

    if (form.roles.length === 0) {
      nextErrors.roles = "Choose at least one role.";
    }

    if (
      form.baseHourlyRate.trim() &&
      (Number.isNaN(Number(form.baseHourlyRate)) || Number(form.baseHourlyRate) < 0)
    ) {
      nextErrors.baseHourlyRate = "Base hourly rate must be a valid amount.";
    }

    if (
      form.weeklyWorkingHourSoftCap.trim() &&
      (Number.isNaN(Number(form.weeklyWorkingHourSoftCap)) ||
        Number(form.weeklyWorkingHourSoftCap) < 0)
    ) {
      nextErrors.weeklyWorkingHourSoftCap =
        "Weekly working-hour soft cap must be zero or more.";
    }

    if (
      form.monthlyWorkingHourSoftCap.trim() &&
      (Number.isNaN(Number(form.monthlyWorkingHourSoftCap)) ||
        Number(form.monthlyWorkingHourSoftCap) < 0)
    ) {
      nextErrors.monthlyWorkingHourSoftCap =
        "Monthly working-hour soft cap must be zero or more.";
    }

    if (!form.username.trim()) {
      nextErrors.username = "Username is required.";
    }

    if (!form.temporaryPassword.trim()) {
      nextErrors.temporaryPassword = "Temporary password is required.";
    }

    if (form.temporaryPassword !== form.confirmTemporaryPassword) {
      nextErrors.confirmTemporaryPassword = "Temporary passwords must match.";
    }

    setErrors(nextErrors);
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
    const attemptProgress: SubmitProgress = {
      userId: progress.userId,
      staffId: progress.staffId,
    };

    try {
      let userId = progress.userId;
      let staffId = progress.staffId;

      if (!userId) {
        const user = await createAdminUser(token, buildAdminUserPayload(form));
        userId = user.id;
        attemptProgress.userId = userId;
        setProgress((current) => ({ ...current, userId }));
      }

      if (!staffId) {
        const profile = await createStaffProfile(
          token,
          buildStaffProfilePayload(form, userId, form.storeId),
        );
        staffId = profile.id;
        attemptProgress.staffId = staffId;
        setProgress((current) => ({ ...current, userId, staffId }));
      }

      const roles = Array.from(
        new Set(form.roles.map((role) => role.trim()).filter(Boolean)),
      );

      for (const role of roles) {
        try {
          await addStaffRole(token, staffId, { role });
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 409) {
            throw error;
          }
        }
      }

      setForm((current) => ({
        ...initialForm,
        storeId: current.storeId,
      }));
      setProgress({ userId: null, staffId: null });
      setSuccessMessage("Staff member added. Returning to the staff directory...");
      router.push("/admin/staff");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAccessToken();
        router.replace("/admin/login");
        return;
      }

      const completedSteps = [
        attemptProgress.userId ? "admin user created" : null,
        attemptProgress.staffId ? "staff profile created" : null,
      ].filter(Boolean);
      const prefix =
        completedSteps.length > 0
          ? `Partial save: ${completedSteps.join(", ")}. Retry will resume from the failed step. `
          : "";

      setFormError(`${prefix}${getStaffSaveErrorMessage(error)}`);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Button asChild variant="outline">
            <Link href="/admin/staff">
              <ArrowLeft className="mr-2 size-4" />
              Back to Staff
            </Link>
          </Button>
          <h2 className="mt-5 text-2xl font-semibold text-slate-950">Add Staff</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Add a staff member to an existing active location.
          </p>
        </div>
      </div>

      {formError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {formError}
        </div>
      ) : null}

      {successMessage ? (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <CheckCircle2 className="size-4" />
          {successMessage}
        </div>
      ) : null}

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">Staff identity</h3>
          </div>

          {isLoadingStores ? (
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <Loader2 className="size-4 animate-spin" />
              Loading locations...
            </div>
          ) : activeStores.length === 0 ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Create an active location before adding staff.
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="First Name" error={errors.firstName}>
              <Input
                value={form.firstName}
                onChange={(event) => updateField("firstName", event.target.value)}
                className={fieldClass(Boolean(errors.firstName))}
                disabled={isSaving}
              />
            </Field>
            <Field label="Last Name" error={errors.lastName}>
              <Input
                value={form.lastName}
                onChange={(event) => updateField("lastName", event.target.value)}
                className={fieldClass(Boolean(errors.lastName))}
                disabled={isSaving}
              />
            </Field>
            <Field label="Email Address" error={errors.email}>
              <Input
                type="email"
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                className={fieldClass(Boolean(errors.email))}
                disabled={isSaving || Boolean(progress.userId)}
              />
            </Field>
            <Field label="Phone Number" error={errors.phone}>
              <Input
                type="tel"
                value={form.phone}
                onChange={(event) => updateField("phone", event.target.value)}
                className={fieldClass(Boolean(errors.phone))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
            <Field label="Location" error={errors.storeId}>
              <select
                value={form.storeId}
                onChange={(event) => updateField("storeId", event.target.value)}
                className={cn(selectClassName, fieldClass(Boolean(errors.storeId)))}
                disabled={isSaving || isLoadingStores || Boolean(progress.staffId)}
              >
                <option value="">Choose location</option>
                {activeStores.map((store) => (
                  <option key={store.id} value={store.id}>
                    {store.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Base Hourly Rate" error={errors.baseHourlyRate}>
              <Input
                type="number"
                min="0"
                value={form.baseHourlyRate}
                onChange={(event) => updateField("baseHourlyRate", event.target.value)}
                className={fieldClass(Boolean(errors.baseHourlyRate))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700">Role Assignment</p>
            <div className="flex flex-wrap gap-2">
              {staffRoleOptions.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => toggleRole(role)}
                  disabled={isSaving}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                    form.roles.includes(role)
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:text-blue-700",
                  )}
                >
                  {role}
                </button>
              ))}
            </div>
            {errors.roles ? <p className="text-sm text-red-600">{errors.roles}</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">
              Working hour soft caps
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Used for rota planning warnings later. These do not affect pay and do
              not block scheduling.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field
              label="Weekly working-hour soft cap"
              error={errors.weeklyWorkingHourSoftCap}
            >
              <Input
                type="number"
                min="0"
                step="0.25"
                value={form.weeklyWorkingHourSoftCap}
                onChange={(event) =>
                  updateField("weeklyWorkingHourSoftCap", event.target.value)
                }
                className={fieldClass(Boolean(errors.weeklyWorkingHourSoftCap))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
            <Field
              label="Monthly working-hour soft cap"
              error={errors.monthlyWorkingHourSoftCap}
            >
              <Input
                type="number"
                min="0"
                step="0.25"
                value={form.monthlyWorkingHourSoftCap}
                onChange={(event) =>
                  updateField("monthlyWorkingHourSoftCap", event.target.value)
                }
                className={fieldClass(Boolean(errors.monthlyWorkingHourSoftCap))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">
              Employee portal access
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              These credentials are used for the employee portal account.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Username" error={errors.username}>
              <Input
                value={form.username}
                onChange={(event) => updateField("username", event.target.value)}
                className={fieldClass(Boolean(errors.username))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
            <Field label="Account Status" error={errors.accountStatus}>
              <select
                value={form.accountStatus}
                onChange={(event) =>
                  updateField("accountStatus", event.target.value as StaffAccountStatus)
                }
                className={selectClassName}
                disabled={isSaving || Boolean(progress.staffId)}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </Field>
            <Field label="Temporary Password" error={errors.temporaryPassword}>
              <Input
                type="password"
                value={form.temporaryPassword}
                onChange={(event) =>
                  updateField("temporaryPassword", event.target.value)
                }
                className={fieldClass(Boolean(errors.temporaryPassword))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
            <Field
              label="Confirm Temporary Password"
              error={errors.confirmTemporaryPassword}
            >
              <Input
                type="password"
                value={form.confirmTemporaryPassword}
                onChange={(event) =>
                  updateField("confirmTemporaryPassword", event.target.value)
                }
                className={fieldClass(Boolean(errors.confirmTemporaryPassword))}
                disabled={isSaving || Boolean(progress.staffId)}
              />
            </Field>
          </div>
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
          disabled={isSaving || isLoadingStores || activeStores.length === 0}
        >
          {isSaving ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <UserPlus className="mr-2 size-4" />
              Add Staff
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

const selectClassName =
  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

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
