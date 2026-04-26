"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { FormEvent, useState } from "react";

import { ApiError, createStore, StoreCreate } from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import {
  OpeningHoursType,
  SiteStatus,
  StaffAccountStatus,
  StaffPreview,
} from "@/lib/site-profile";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type SiteFormState = {
  siteCode: string;
  locationName: string;
  fullAddress: string;
  sitePhone: string;
  siteEmail: string;
  openingHoursType: OpeningHoursType;
  openingTime: string;
  closingTime: string;
  timezone: string;
  status: SiteStatus;
  notes: string;
  managerFirstName: string;
  managerLastName: string;
  managerEmail: string;
  managerPhone: string;
  assignExistingEmployee: boolean;
};

type StaffFormState = {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  weeklyHourCap: string;
  roles: string[];
  rightToWorkStatus: string;
  nationalInsuranceNumber: string;
  documentType: string;
  baseHourlyRate: string;
  baseHoursThreshold: string;
  overtimeHourlyRate: string;
  username: string;
  temporaryPassword: string;
  confirmTemporaryPassword: string;
  accountStatus: StaffAccountStatus;
  requirePasswordReset: boolean;
  sendLoginDetailsLater: boolean;
};

type SiteFieldErrors = Partial<Record<keyof SiteFormState, string>>;
type StaffFieldErrors = Partial<Record<keyof StaffFormState, string>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const roleOptions = ["Cashier", "Hot Food", "Stock", "Cleaner", "Supervisor", "Manager"];

const initialSiteForm: SiteFormState = {
  siteCode: "",
  locationName: "",
  fullAddress: "",
  sitePhone: "",
  siteEmail: "",
  openingHoursType: "24_7",
  openingTime: "",
  closingTime: "",
  timezone: "Europe/London",
  status: "active",
  notes: "",
  managerFirstName: "",
  managerLastName: "",
  managerEmail: "",
  managerPhone: "",
  assignExistingEmployee: false,
};

const initialStaffForm: StaffFormState = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  weeklyHourCap: "",
  roles: [],
  rightToWorkStatus: "not_checked",
  nationalInsuranceNumber: "",
  documentType: "brp",
  baseHourlyRate: "",
  baseHoursThreshold: "",
  overtimeHourlyRate: "",
  username: "",
  temporaryPassword: "",
  confirmTemporaryPassword: "",
  accountStatus: "active",
  requirePasswordReset: true,
  sendLoginDetailsLater: false,
};

function fieldClass(hasError: boolean) {
  return cn(hasError && "border-red-400 focus-visible:ring-red-500");
}

function createLocalId() {
  return `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function SiteSetupForm() {
  const router = useRouter();
  const [form, setForm] = useState<SiteFormState>(initialSiteForm);
  const [staffMembers, setStaffMembers] = useState<StaffPreview[]>([]);
  const [siteErrors, setSiteErrors] = useState<SiteFieldErrors>({});
  const [staffErrors, setStaffErrors] = useState<StaffFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [staffMessage, setStaffMessage] = useState<string | null>(null);
  const [isStaffFormOpen, setIsStaffFormOpen] = useState(false);
  const [staffForm, setStaffForm] = useState<StaffFormState>(initialStaffForm);
  const [isSaving, setIsSaving] = useState(false);
  const [savingAction, setSavingAction] = useState<SiteStatus | null>(null);

  function updateField<Key extends keyof SiteFormState>(
    key: Key,
    value: SiteFormState[Key],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateStaffField<Key extends keyof StaffFormState>(
    key: Key,
    value: StaffFormState[Key],
  ) {
    setStaffForm((current) => ({ ...current, [key]: value }));
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

  function validateForCreate() {
    const nextErrors: SiteFieldErrors = {};

    if (!form.locationName.trim()) {
      nextErrors.locationName = "Location name is required.";
    }

    if (!form.fullAddress.trim()) {
      nextErrors.fullAddress = "Full address is required.";
    }

    if (!form.sitePhone.trim()) {
      nextErrors.sitePhone = "Site phone number is required.";
    }

    if (!form.timezone.trim()) {
      nextErrors.timezone = "Time zone is required.";
    }

    validateSharedOptionalFields(nextErrors);
    setSiteErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function validateForDraft() {
    const nextErrors: SiteFieldErrors = {};

    if (!form.locationName.trim()) {
      nextErrors.locationName = "Location name is required to save a backend store.";
    }

    validateSharedOptionalFields(nextErrors);
    setSiteErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function buildStorePayload(): StoreCreate {
    return {
      code: form.siteCode.trim() || null,
      name: form.locationName.trim(),
      timezone: form.timezone.trim() || "Europe/London",
      address_line1: form.fullAddress.trim() || null,
      city: null,
      postcode: null,
      phone: form.sitePhone.trim() || null,
      manager_user_id: null,
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

  async function saveSite(status: SiteStatus) {
    setFormError(null);

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
      // Phase B sends only fields supported by the current backend Stores API.
      // Manager details, opening hours, notes, site email, status, and staff remain UI-only.
      await createStore(token, buildStorePayload());
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

  function validateStaffForm() {
    const nextErrors: StaffFieldErrors = {};

    if (!staffForm.firstName.trim()) {
      nextErrors.firstName = "First name is required.";
    }

    if (!staffForm.lastName.trim()) {
      nextErrors.lastName = "Last name is required.";
    }

    if (staffForm.roles.length === 0) {
      nextErrors.roles = "Select at least one role.";
    }

    if (staffForm.email.trim() && !emailPattern.test(staffForm.email.trim())) {
      nextErrors.email = "Enter a valid email address.";
    }

    if (
      staffForm.weeklyHourCap.trim() &&
      (Number.isNaN(Number(staffForm.weeklyHourCap)) || Number(staffForm.weeklyHourCap) <= 0)
    ) {
      nextErrors.weeklyHourCap = "Weekly hour cap must be a positive number.";
    }

    if (
      staffForm.temporaryPassword &&
      staffForm.temporaryPassword !== staffForm.confirmTemporaryPassword
    ) {
      nextErrors.confirmTemporaryPassword = "Temporary passwords must match.";
    }

    setStaffErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function saveStaffMember() {
    setStaffMessage(null);

    if (!validateStaffForm()) {
      return;
    }

    // Sensitive staff data is UI-only in this frontend prototype and must be
    // persisted only through secure backend endpoints later.
    setStaffMembers((current) => [
      ...current,
      {
        id: createLocalId(),
        firstName: staffForm.firstName.trim(),
        lastName: staffForm.lastName.trim(),
        email: staffForm.email.trim(),
        phone: staffForm.phone.trim(),
        weeklyHourCap: staffForm.weeklyHourCap.trim()
          ? Number(staffForm.weeklyHourCap)
          : null,
        roles: staffForm.roles,
        accountStatus: staffForm.accountStatus,
      },
    ]);
    setStaffForm(initialStaffForm);
    setStaffErrors({});
    setIsStaffFormOpen(false);
  }

  function cancelStaffForm() {
    setStaffForm(initialStaffForm);
    setStaffErrors({});
    setIsStaffFormOpen(false);
  }

  function toggleRole(role: string) {
    setStaffForm((current) => ({
      ...current,
      roles: current.roles.includes(role)
        ? current.roles.filter((item) => item !== role)
        : [...current.roles, role],
    }));
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

            <Field label="Full Address" error={siteErrors.fullAddress}>
              <Input
                value={form.fullAddress}
                onChange={(event) => updateField("fullAddress", event.target.value)}
                className={fieldClass(Boolean(siteErrors.fullAddress))}
                placeholder="Street address, City, Postcode"
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
              <>
                <Field label="Opening Time" error={siteErrors.openingTime}>
                  <Input
                    type="time"
                    value={form.openingTime}
                    onChange={(event) => updateField("openingTime", event.target.value)}
                    className={fieldClass(Boolean(siteErrors.openingTime))}
                  />
                </Field>
                <Field label="Closing Time" error={siteErrors.closingTime}>
                  <Input
                    type="time"
                    value={form.closingTime}
                    onChange={(event) => updateField("closingTime", event.target.value)}
                    className={fieldClass(Boolean(siteErrors.closingTime))}
                  />
                </Field>
              </>
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
              setStaffMessage(
                "Existing employee assignment will be available after the staff directory is created.",
              );
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
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Staff Members</h2>
              <p className="mt-1 text-sm text-slate-500">
                You can create the location first and add more staff later.
              </p>
            </div>
            <Button type="button" variant="outline" onClick={() => setIsStaffFormOpen(true)}>
              + Add Staff Member
            </Button>
          </div>

          {staffMessage ? (
            <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
              {staffMessage}
            </div>
          ) : null}

          {staffMembers.length === 0 && !isStaffFormOpen ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              No staff members added yet. Click Add Staff Member to get started.
            </div>
          ) : null}

          {isStaffFormOpen ? (
            <div className="space-y-5 rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <StaffIdentitySection
                staffForm={staffForm}
                staffErrors={staffErrors}
                locationName={form.locationName}
                updateStaffField={updateStaffField}
                toggleRole={toggleRole}
              />
              <EmploymentPaySection
                staffForm={staffForm}
                staffErrors={staffErrors}
                updateStaffField={updateStaffField}
              />
              <EmployeePortalSection
                staffForm={staffForm}
                staffErrors={staffErrors}
                updateStaffField={updateStaffField}
              />
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={cancelStaffForm}>
                  Cancel
                </Button>
                <Button type="button" onClick={saveStaffMember}>
                  Save Staff Member
                </Button>
              </div>
            </div>
          ) : null}

          {staffMembers.length > 0 ? (
            <div className="overflow-hidden rounded-2xl border border-slate-200">
              <div className="grid grid-cols-[1.3fr_1.2fr_1.4fr_1fr_0.8fr_0.9fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-medium uppercase tracking-[0.12em] text-slate-400">
                <span>Name</span>
                <span>Roles</span>
                <span>Email</span>
                <span>Phone</span>
                <span>Hours</span>
                <span>Status</span>
              </div>
              {staffMembers.map((staff) => (
                <div
                  key={staff.id}
                  className="grid grid-cols-[1.3fr_1.2fr_1.4fr_1fr_0.8fr_0.9fr] gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-600"
                >
                  <span className="font-medium text-slate-900">
                    {staff.firstName} {staff.lastName}
                  </span>
                  <span>{staff.roles.join(", ")}</span>
                  <span className="truncate">{staff.email || "Not added"}</span>
                  <span>{staff.phone || "Not added"}</span>
                  <span>{staff.weeklyHourCap ?? "None"}</span>
                  <span className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "rounded-full px-2 py-1 text-xs font-medium",
                        staff.accountStatus === "active"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-500",
                      )}
                    >
                      {staff.accountStatus === "active"
                        ? "Portal Access Active"
                        : "Inactive"}
                    </span>
                    <span className="flex gap-1">
                      <button
                        type="button"
                        className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        aria-label="Edit staff member"
                        onClick={() =>
                          setStaffMessage("Edit staff member will be refined next.")
                        }
                      >
                        <Pencil className="size-4" />
                      </button>
                      <button
                        type="button"
                        className="rounded-md p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                        aria-label="Remove staff member"
                        onClick={() =>
                          setStaffMembers((current) =>
                            current.filter((item) => item.id !== staff.id),
                          )
                        }
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </span>
                  </span>
                </div>
              ))}
            </div>
          ) : null}
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

function StaffIdentitySection({
  staffForm,
  staffErrors,
  locationName,
  updateStaffField,
  toggleRole,
}: {
  staffForm: StaffFormState;
  staffErrors: StaffFieldErrors;
  locationName: string;
  updateStaffField: <Key extends keyof StaffFormState>(
    key: Key,
    value: StaffFormState[Key],
  ) => void;
  toggleRole: (role: string) => void;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="font-semibold text-slate-950">Staff Identity</h3>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="First Name" error={staffErrors.firstName}>
          <Input
            value={staffForm.firstName}
            onChange={(event) => updateStaffField("firstName", event.target.value)}
            className={fieldClass(Boolean(staffErrors.firstName))}
          />
        </Field>
        <Field label="Last Name" error={staffErrors.lastName}>
          <Input
            value={staffForm.lastName}
            onChange={(event) => updateStaffField("lastName", event.target.value)}
            className={fieldClass(Boolean(staffErrors.lastName))}
          />
        </Field>
        <Field label="Email Address" error={staffErrors.email}>
          <Input
            type="email"
            value={staffForm.email}
            onChange={(event) => updateStaffField("email", event.target.value)}
            className={fieldClass(Boolean(staffErrors.email))}
          />
        </Field>
        <Field label="Phone Number" error={staffErrors.phone}>
          <Input
            type="tel"
            value={staffForm.phone}
            onChange={(event) => updateStaffField("phone", event.target.value)}
            className={fieldClass(Boolean(staffErrors.phone))}
          />
        </Field>
        <Field label="Site Assigned">
          <Input value={locationName || "Current location"} readOnly />
        </Field>
        <Field label="Weekly Hour Cap" error={staffErrors.weeklyHourCap}>
          <Input
            type="number"
            min="0"
            value={staffForm.weeklyHourCap}
            onChange={(event) => updateStaffField("weeklyHourCap", event.target.value)}
            className={fieldClass(Boolean(staffErrors.weeklyHourCap))}
          />
        </Field>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">Role Assignment</p>
        <div className="flex flex-wrap gap-2">
          {roleOptions.map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => toggleRole(role)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-medium transition",
                staffForm.roles.includes(role)
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:text-blue-700",
              )}
            >
              {role}
            </button>
          ))}
        </div>
        {staffErrors.roles ? (
          <p className="text-sm text-red-600">{staffErrors.roles}</p>
        ) : null}
      </div>
    </section>
  );
}

function EmploymentPaySection({
  staffForm,
  staffErrors,
  updateStaffField,
}: {
  staffForm: StaffFormState;
  staffErrors: StaffFieldErrors;
  updateStaffField: <Key extends keyof StaffFormState>(
    key: Key,
    value: StaffFormState[Key],
  ) => void;
}) {
  return (
    <section className="space-y-4 border-t border-slate-200 pt-5">
      <div>
        <h3 className="font-semibold text-slate-950">Employment & Pay Setup</h3>
        <p className="mt-1 text-sm text-amber-700">
          Sensitive information. Visible only to authorised admins.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          For this prototype, sensitive fields are UI-only and must later be saved via
          secure backend endpoints.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Right to Work Status">
          <select
            value={staffForm.rightToWorkStatus}
            onChange={(event) => updateStaffField("rightToWorkStatus", event.target.value)}
            className={selectClassName}
          >
            <option value="not_checked">Not checked</option>
            <option value="checked">Checked</option>
            <option value="pending">Pending</option>
            <option value="not_required_yet">Not required yet</option>
          </select>
        </Field>
        <Field label="National Insurance Number">
          <Input
            value={staffForm.nationalInsuranceNumber}
            onChange={(event) =>
              updateStaffField("nationalInsuranceNumber", event.target.value)
            }
            placeholder="UI-only sensitive field"
          />
        </Field>
        <Field label="Document Upload">
          <div className="grid gap-2 sm:grid-cols-[160px_1fr]">
            <select
              value={staffForm.documentType}
              onChange={(event) => updateStaffField("documentType", event.target.value)}
              className={selectClassName}
            >
              <option value="brp">BRP</option>
              <option value="share_code">Share Code</option>
              <option value="passport_copy">Passport Copy</option>
              <option value="other">Other</option>
            </select>
            <Input type="file" />
          </div>
        </Field>
        <Field label="Base Hourly Rate">
          <Input
            type="number"
            value={staffForm.baseHourlyRate}
            onChange={(event) => updateStaffField("baseHourlyRate", event.target.value)}
            placeholder="UI-only"
          />
        </Field>
        <Field label="Base Hours Threshold">
          <Input
            type="number"
            value={staffForm.baseHoursThreshold}
            onChange={(event) => updateStaffField("baseHoursThreshold", event.target.value)}
            placeholder="UI-only"
          />
        </Field>
        <Field label="Overtime Hourly Rate">
          <Input
            type="number"
            value={staffForm.overtimeHourlyRate}
            onChange={(event) => updateStaffField("overtimeHourlyRate", event.target.value)}
            placeholder="UI-only"
          />
        </Field>
      </div>
    </section>
  );
}

function EmployeePortalSection({
  staffForm,
  staffErrors,
  updateStaffField,
}: {
  staffForm: StaffFormState;
  staffErrors: StaffFieldErrors;
  updateStaffField: <Key extends keyof StaffFormState>(
    key: Key,
    value: StaffFormState[Key],
  ) => void;
}) {
  return (
    <section className="space-y-4 border-t border-slate-200 pt-5">
      <div>
        <h3 className="font-semibold text-slate-950">Employee Portal Access</h3>
        <p className="mt-1 text-sm text-slate-500">
          These credentials will be used by the employee to access the employee portal.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Temporary password should be changed by the employee after first login.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Username">
          <Input
            value={staffForm.username}
            onChange={(event) => updateStaffField("username", event.target.value)}
          />
        </Field>
        <Field label="Account Status">
          <select
            value={staffForm.accountStatus}
            onChange={(event) =>
              updateStaffField("accountStatus", event.target.value as StaffAccountStatus)
            }
            className={selectClassName}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </Field>
        <Field label="Temporary Password">
          <Input
            type="password"
            value={staffForm.temporaryPassword}
            onChange={(event) => updateStaffField("temporaryPassword", event.target.value)}
            placeholder="UI-only, never stored"
          />
        </Field>
        <Field label="Confirm Temporary Password" error={staffErrors.confirmTemporaryPassword}>
          <Input
            type="password"
            value={staffForm.confirmTemporaryPassword}
            onChange={(event) =>
              updateStaffField("confirmTemporaryPassword", event.target.value)
            }
            className={fieldClass(Boolean(staffErrors.confirmTemporaryPassword))}
            placeholder="UI-only, never stored"
          />
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <CheckboxField
          checked={staffForm.requirePasswordReset}
          onChange={(checked) => updateStaffField("requirePasswordReset", checked)}
          label="Require password reset on first login"
        />
        <CheckboxField
          checked={staffForm.sendLoginDetailsLater}
          onChange={(checked) => updateStaffField("sendLoginDetailsLater", checked)}
          label="Send login details later"
        />
      </div>
    </section>
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

function CheckboxField({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-600"
      />
      <span className="font-medium text-slate-700">{label}</span>
    </label>
  );
}
