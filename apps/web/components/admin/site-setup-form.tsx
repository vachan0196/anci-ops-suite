"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { FormEvent, useState } from "react";

import {
  ApiError,
  createStore,
  StoreCreate,
  updateStoreOpeningHours,
  type OpeningHoursBulkUpdate,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type OpeningHoursType = "24_7" | "custom";
type SiteStatus = "active" | "inactive" | "draft";

type SiteFormState = {
  siteCode: string;
  locationName: string;
  addressLine1: string;
  city: string;
  postcode: string;
  sitePhone: string;
  siteEmail: string;
  openingHoursType: OpeningHoursType;
  timezone: string;
  status: SiteStatus;
  notes: string;
  managerFirstName: string;
  managerLastName: string;
  managerEmail: string;
  managerPhone: string;
  assignExistingEmployee: boolean;
};

type SiteFieldErrors = Partial<Record<keyof SiteFormState, string>>;
type OpeningHoursFieldErrors = Partial<Record<number, string>>;

type OpeningHoursDayForm = {
  dayOfWeek: number;
  dayName: string;
  isClosed: boolean;
  openTime: string;
  closeTime: string;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const dayOptions = [
  { dayOfWeek: 0, dayName: "Monday" },
  { dayOfWeek: 1, dayName: "Tuesday" },
  { dayOfWeek: 2, dayName: "Wednesday" },
  { dayOfWeek: 3, dayName: "Thursday" },
  { dayOfWeek: 4, dayName: "Friday" },
  { dayOfWeek: 5, dayName: "Saturday" },
  { dayOfWeek: 6, dayName: "Sunday" },
];

const initialSiteForm: SiteFormState = {
  siteCode: "",
  locationName: "",
  addressLine1: "",
  city: "",
  postcode: "",
  sitePhone: "",
  siteEmail: "",
  openingHoursType: "24_7",
  timezone: "Europe/London",
  status: "active",
  notes: "",
  managerFirstName: "",
  managerLastName: "",
  managerEmail: "",
  managerPhone: "",
  assignExistingEmployee: false,
};

function buildInitialOpeningHours(): OpeningHoursDayForm[] {
  return dayOptions.map((day) => ({
    ...day,
    isClosed: false,
    openTime: "06:00",
    closeTime: "22:00",
  }));
}

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

export function SiteSetupForm() {
  const router = useRouter();
  const [form, setForm] = useState<SiteFormState>(initialSiteForm);
  const [siteErrors, setSiteErrors] = useState<SiteFieldErrors>({});
  const [openingHoursErrors, setOpeningHoursErrors] =
    useState<OpeningHoursFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [openingHours, setOpeningHours] = useState<OpeningHoursDayForm[]>(
    buildInitialOpeningHours,
  );
  const [isSaving, setIsSaving] = useState(false);
  const [savingAction, setSavingAction] = useState<SiteStatus | null>(null);
  const [siteCreatedWithPartialFailure, setSiteCreatedWithPartialFailure] = useState(false);

  function updateField<Key extends keyof SiteFormState>(
    key: Key,
    value: SiteFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateOpeningHoursDay(
    dayOfWeek: number,
    updates: Partial<Omit<OpeningHoursDayForm, "dayOfWeek" | "dayName">>,
  ) {
    setOpeningHours((current) =>
      current.map((day) => (day.dayOfWeek === dayOfWeek ? { ...day, ...updates } : day)),
    );
    setOpeningHoursErrors((current) => {
      const next = { ...current };
      delete next[dayOfWeek];
      return next;
    });
  }

  function applyMondayHoursToOpenDays() {
    const monday = openingHours.find((day) => day.dayOfWeek === 0);

    if (!monday || monday.isClosed || !monday.openTime || !monday.closeTime) {
      setOpeningHoursErrors((current) => ({
        ...current,
        0: "Add Monday opening and closing times before applying them.",
      }));
      return;
    }

    setOpeningHours((current) =>
      current.map((day) =>
        day.isClosed
          ? day
          : { ...day, openTime: monday.openTime, closeTime: monday.closeTime },
      ),
    );
    setOpeningHoursErrors({});
  }

  function validateSharedOptionalFields(nextErrors: SiteFieldErrors) {
    if (form.siteEmail.trim() && !emailPattern.test(form.siteEmail.trim())) {
      nextErrors.siteEmail = "Enter a valid site email address.";
    }

    if (form.managerEmail.trim() && !emailPattern.test(form.managerEmail.trim())) {
      nextErrors.managerEmail = "Enter a valid manager email address.";
    }

    if (form.managerPhone.length > 0 && !form.managerPhone.trim()) {
      nextErrors.managerPhone = "Manager phone number cannot be blank.";
    }
  }

  function validateOpeningHours(status: SiteStatus) {
    const nextErrors: OpeningHoursFieldErrors = {};

    if (form.openingHoursType !== "custom") {
      setOpeningHoursErrors(nextErrors);
      return true;
    }

    let openDayCount = 0;

    for (const day of openingHours) {
      if (day.dayOfWeek < 0 || day.dayOfWeek > 6) {
        nextErrors[day.dayOfWeek] = "Day must be between 0 and 6.";
        continue;
      }

      if (day.isClosed) {
        continue;
      }

      openDayCount += 1;

      if (!day.openTime || !day.closeTime) {
        nextErrors[day.dayOfWeek] = "Opening and closing times are required.";
        continue;
      }

      if (day.closeTime <= day.openTime) {
        nextErrors[day.dayOfWeek] = "Closing time must be later than opening time.";
      }
    }

    if (status === "active" && openDayCount === 0) {
      nextErrors[0] = "At least one day must be open before creating an operational site.";
    }

    setOpeningHoursErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function validateForCreate() {
    const nextErrors: SiteFieldErrors = {};

    if (!form.locationName.trim()) {
      nextErrors.locationName = "Location name is required.";
    }

    if (!form.addressLine1.trim()) {
      nextErrors.addressLine1 = "Street address is required.";
    }

    if (!form.sitePhone.trim()) {
      nextErrors.sitePhone = "Site phone number is required.";
    }

    if (!form.timezone.trim()) {
      nextErrors.timezone = "Time zone is required.";
    }

    validateSharedOptionalFields(nextErrors);
    setSiteErrors(nextErrors);
    return Object.keys(nextErrors).length === 0 && validateOpeningHours("active");
  }

  function validateForDraft() {
    const nextErrors: SiteFieldErrors = {};

    if (!form.locationName.trim()) {
      nextErrors.locationName = "Location name is required to save a backend store.";
    }

    validateSharedOptionalFields(nextErrors);
    setSiteErrors(nextErrors);
    return Object.keys(nextErrors).length === 0 && validateOpeningHours("draft");
  }

  function buildStorePayload(): StoreCreate {
    return {
      code: form.siteCode.trim() || null,
      name: form.locationName.trim(),
      timezone: form.timezone.trim() || "Europe/London",
      address_line1: form.addressLine1.trim() || null,
      city: form.city.trim() || null,
      postcode: form.postcode.trim() || null,
      phone: form.sitePhone.trim() || null,
      email: form.siteEmail.trim() || null,
      notes: form.notes.trim() || null,
      manager_user_id: null,
    };
  }

  function buildOpeningHoursPayload(): OpeningHoursBulkUpdate {
    if (form.openingHoursType === "24_7") {
      return {
        opening_hours: dayOptions.map((day) => ({
          day_of_week: day.dayOfWeek,
          open_time: "00:00",
          close_time: "23:59",
          is_closed: false,
        })),
      };
    }

    return {
      opening_hours: openingHours.map((day) => ({
        day_of_week: day.dayOfWeek,
        open_time: day.isClosed ? null : day.openTime,
        close_time: day.isClosed ? null : day.closeTime,
        is_closed: day.isClosed,
      })),
    };
  }

  function getSaveErrorMessage(error: unknown) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return "You do not have permission to create stores for this workspace.";
      }

      if (error.status === 409) {
        return error.message || "A store with this code already exists.";
      }

      if (error.status === 422) {
        return error.message || "Check the location details and try again.";
      }

      return error.message;
    }

    if (error instanceof Error && error.message === "NETWORK_ERROR") {
      return "Unable to connect to server. Please try again.";
    }

    return "Something went wrong. Please try again.";
  }

  function getOpeningHoursSaveErrorMessage(error: unknown) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return "You do not have permission to save opening hours for this location.";
      }

      if (error.status === 422) {
        return "Check the opening hours and try again.";
      }

      return error.message || "Opening hours could not be saved.";
    }

    if (error instanceof Error && error.message === "NETWORK_ERROR") {
      return "Unable to connect to server.";
    }

    return "Opening hours could not be saved.";
  }

  async function saveSite(status: SiteStatus) {
    setFormError(null);

    if (siteCreatedWithPartialFailure) {
      setFormError(
        "This location has already been created. Review or complete the remaining setup later to avoid creating duplicate stores.",
      );
      return;
    }

    const isValid = status === "active" ? validateForCreate() : validateForDraft();

    if (!isValid) {
      setFormError(
        status === "active"
          ? "Check the highlighted fields and try again."
          : "Add a location name before saving.",
      );
      return;
    }

    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    setIsSaving(true);
    setSavingAction(status);

    try {
      const store = await createStore(token, buildStorePayload());

      try {
        await updateStoreOpeningHours(token, store.id, buildOpeningHoursPayload());
      } catch (error) {
        setSiteCreatedWithPartialFailure(true);
        setFormError(
          `Location was created, but opening hours could not be saved. ${getOpeningHoursSaveErrorMessage(
            error,
          )}`,
        );
        return;
      }

      router.replace("/admin");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAccessToken();
        router.replace("/admin/login");
        return;
      }

      setFormError(getSaveErrorMessage(error));
    } finally {
      setIsSaving(false);
      setSavingAction(null);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    saveSite("active");
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
            <h2 className="text-lg font-semibold text-slate-950">
              Location Information
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Capture the identity and operating details of this site.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Site ID / Site Code" error={siteErrors.siteCode}>
              <Input
                value={form.siteCode}
                onChange={(event) => updateField("siteCode", event.target.value)}
                className={fieldClass(Boolean(siteErrors.siteCode))}
                placeholder="SITE-001"
              />
            </Field>

            <Field label="Location Name" error={siteErrors.locationName}>
              <Input
                value={form.locationName}
                onChange={(event) => updateField("locationName", event.target.value)}
                className={fieldClass(Boolean(siteErrors.locationName))}
                placeholder="Coalville Store"
              />
            </Field>

            <Field label="Street Address" error={siteErrors.addressLine1}>
              <Input
                value={form.addressLine1}
                onChange={(event) => updateField("addressLine1", event.target.value)}
                className={fieldClass(Boolean(siteErrors.addressLine1))}
                placeholder="Street address"
              />
            </Field>

            <Field label="City" error={siteErrors.city}>
              <Input
                value={form.city}
                onChange={(event) => updateField("city", event.target.value)}
                className={fieldClass(Boolean(siteErrors.city))}
                placeholder="City"
              />
            </Field>

            <Field label="Postcode" error={siteErrors.postcode}>
              <Input
                value={form.postcode}
                onChange={(event) => updateField("postcode", event.target.value)}
                className={fieldClass(Boolean(siteErrors.postcode))}
                placeholder="Postcode"
              />
            </Field>

            <Field label="Site Phone Number" error={siteErrors.sitePhone}>
              <Input
                type="tel"
                value={form.sitePhone}
                onChange={(event) => updateField("sitePhone", event.target.value)}
                className={fieldClass(Boolean(siteErrors.sitePhone))}
                placeholder="+44 1234 567890"
              />
            </Field>

            <Field label="Site Email" error={siteErrors.siteEmail}>
              <Input
                type="email"
                value={form.siteEmail}
                onChange={(event) => updateField("siteEmail", event.target.value)}
                className={fieldClass(Boolean(siteErrors.siteEmail))}
                placeholder="location@example.com"
              />
            </Field>

            <Field label="Time Zone" error={siteErrors.timezone}>
              <select
                value={form.timezone}
                onChange={(event) => updateField("timezone", event.target.value)}
                className={cn(selectClassName, fieldClass(Boolean(siteErrors.timezone)))}
              >
                <option value="Europe/London">GMT (London) / Europe/London</option>
              </select>
            </Field>

            <Field label="Opening Hours Type" error={siteErrors.openingHoursType}>
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
                <ToggleButton
                  isActive={form.openingHoursType === "24_7"}
                  onClick={() => updateField("openingHoursType", "24_7")}
                >
                  24/7
                </ToggleButton>
                <ToggleButton
                  isActive={form.openingHoursType === "custom"}
                  onClick={() => updateField("openingHoursType", "custom")}
                >
                  Custom Hours
                </ToggleButton>
              </div>
            </Field>

            <Field label="Status" error={siteErrors.status}>
              <select
                value={form.status}
                onChange={(event) => updateField("status", event.target.value as SiteStatus)}
                className={cn(selectClassName, fieldClass(Boolean(siteErrors.status)))}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="draft">Draft</option>
              </select>
            </Field>

            {form.openingHoursType === "custom" ? (
              <div className="space-y-3 md:col-span-2">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm font-medium text-slate-700">Opening Hours</p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={applyMondayHoursToOpenDays}
                    disabled={isSaving}
                  >
                    Apply Monday Hours
                  </Button>
                </div>
                <div className="overflow-x-auto rounded-2xl border border-slate-200">
                  <div className="min-w-[620px]">
                    <div className="grid grid-cols-[1fr_0.9fr_1fr_1fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-medium uppercase tracking-[0.12em] text-slate-400">
                      <span>Day</span>
                      <span>Status</span>
                      <span>Opens</span>
                      <span>Closes</span>
                    </div>
                    {openingHours.map((day) => (
                      <div
                        key={day.dayOfWeek}
                        className="grid grid-cols-[1fr_0.9fr_1fr_1fr] gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-600"
                      >
                        <span className="flex items-center font-medium text-slate-900">
                          {day.dayName}
                        </span>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={!day.isClosed}
                            onChange={(event) =>
                              updateOpeningHoursDay(day.dayOfWeek, {
                                isClosed: !event.target.checked,
                              })
                            }
                            className="size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-600"
                          />
                          <span>{day.isClosed ? "Closed" : "Open"}</span>
                        </label>
                        <Input
                          type="time"
                          value={day.openTime}
                          onChange={(event) =>
                            updateOpeningHoursDay(day.dayOfWeek, {
                              openTime: event.target.value,
                            })
                          }
                          disabled={day.isClosed}
                          className={fieldClass(Boolean(openingHoursErrors[day.dayOfWeek]))}
                        />
                        <Input
                          type="time"
                          value={day.closeTime}
                          onChange={(event) =>
                            updateOpeningHoursDay(day.dayOfWeek, {
                              closeTime: event.target.value,
                            })
                          }
                          disabled={day.isClosed}
                          className={fieldClass(Boolean(openingHoursErrors[day.dayOfWeek]))}
                        />
                        {openingHoursErrors[day.dayOfWeek] ? (
                          <p className="col-span-4 text-sm text-red-600">
                            {openingHoursErrors[day.dayOfWeek]}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <Field label="Notes" helper="Optional." error={siteErrors.notes}>
            <textarea
              value={form.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              className={cn(textareaClassName, fieldClass(Boolean(siteErrors.notes)))}
              placeholder="Additional details about this location..."
            />
          </Field>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Manager Information
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              This manager will be the primary contact for this location.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              updateField("assignExistingEmployee", true);
            }}
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Assign existing employee instead
          </button>

          {form.assignExistingEmployee ? (
            <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
              Existing employee assignment will be available after the staff directory is
              created.
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="First Name" error={siteErrors.managerFirstName}>
              <Input
                value={form.managerFirstName}
                onChange={(event) => updateField("managerFirstName", event.target.value)}
                className={fieldClass(Boolean(siteErrors.managerFirstName))}
              />
            </Field>

            <Field label="Last Name" error={siteErrors.managerLastName}>
              <Input
                value={form.managerLastName}
                onChange={(event) => updateField("managerLastName", event.target.value)}
                className={fieldClass(Boolean(siteErrors.managerLastName))}
              />
            </Field>

            <Field label="Email Address" error={siteErrors.managerEmail}>
              <Input
                type="email"
                value={form.managerEmail}
                onChange={(event) => updateField("managerEmail", event.target.value)}
                className={fieldClass(Boolean(siteErrors.managerEmail))}
              />
            </Field>

            <Field label="Phone Number" error={siteErrors.managerPhone}>
              <Input
                type="tel"
                value={form.managerPhone}
                onChange={(event) => updateField("managerPhone", event.target.value)}
                className={fieldClass(Boolean(siteErrors.managerPhone))}
              />
            </Field>

            <Field label="Role">
              <select value="manager" disabled className={selectClassName}>
                <option value="manager">Manager</option>
              </select>
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Staff Members</h2>
            <p className="mt-1 text-sm text-slate-500">
              Create this location first. After it is saved, add staff from Staff
              {" -> "}Add Staff.
            </p>
          </div>

          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
            Site setup creates the location only. Staff creation happens from the
            standalone Add Staff page after the site exists.
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="flex flex-col-reverse gap-3 p-4 sm:flex-row sm:items-center sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.push("/admin")}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => saveSite("draft")}
            disabled={isSaving}
          >
            {isSaving && savingAction === "draft" ? "Saving..." : "Save as Draft"}
          </Button>
          <Button
            type="submit"
            className="bg-[#5f6f3a] text-white hover:bg-[#4f5f2f]"
            disabled={isSaving}
          >
            {isSaving && savingAction === "active" ? "Creating..." : "Create Location"}
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}

const selectClassName =
  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

const textareaClassName =
  "min-h-28 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

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

function ToggleButton({
  isActive,
  onClick,
  children,
}: {
  isActive: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg px-3 py-2 text-sm font-medium transition",
        isActive ? "bg-blue-600 text-white shadow-sm" : "text-slate-500 hover:text-slate-700",
      )}
    >
      {children}
    </button>
  );
}
