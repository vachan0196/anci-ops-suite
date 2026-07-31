"use client";

import {
  AlertTriangle,
  Loader2,
  MapPin,
  Plus,
  Settings2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createCoverageTemplate,
  createWorkArea,
  deactivateCoverageTemplate,
  deactivateWorkArea,
  listCoverageTemplates,
  listWorkAreas,
  type CoverageTemplate,
  type Store,
  type WorkArea,
  updateCoverageTemplate,
  updateWorkArea,
} from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth-token";
import { staffRoleOptions } from "@/lib/staff-roles";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const coverageDays = [
  { value: 0, label: "Monday", shortLabel: "Mon" },
  { value: 1, label: "Tuesday", shortLabel: "Tue" },
  { value: 2, label: "Wednesday", shortLabel: "Wed" },
  { value: 3, label: "Thursday", shortLabel: "Thu" },
  { value: 4, label: "Friday", shortLabel: "Fri" },
  { value: 5, label: "Saturday", shortLabel: "Sat" },
  { value: 6, label: "Sunday", shortLabel: "Sun" },
] as const;

type CoverageRuleDraft = {
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  requiredHeadcount: string;
  requiredRole: string;
  workAreaId: string;
  displayLabel: string;
};

const emptyCoverageRuleDraft: CoverageRuleDraft = {
  dayOfWeek: 0,
  startTime: "09:00",
  endTime: "17:00",
  requiredHeadcount: "1",
  requiredRole: "",
  workAreaId: "",
  displayLabel: "",
};

function timeInputValue(value: string) {
  return value.slice(0, 5);
}

function formatTime(value: string) {
  return timeInputValue(value);
}

function joinDayLabels(days: number[]) {
  const labels = days.map(
    (day) => coverageDays.find((candidate) => candidate.value === day)?.label ?? "",
  );
  if (labels.length <= 1) {
    return labels[0] ?? "";
  }
  return `${labels.slice(0, -1).join(", ")} and ${labels.at(-1)}`;
}

function coverageRuleTitle(rule: CoverageTemplate) {
  return rule.display_label?.trim() || rule.required_role?.trim() || "Staffing coverage";
}

function getCoverageErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again.";
    }
    if (error.status === 403) {
      return "You do not have permission to manage coverage rules.";
    }
    if (error.code === "COVERAGE_TEMPLATE_WORK_AREA_INVALID") {
      return "Choose an active work area for this site, or clear the optional work area.";
    }
    if (error.status === 422) {
      return "Check the rule details and try again.";
    }
    return error.message || "The coverage rule could not be saved.";
  }
  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to the server.";
  }
  return "The coverage rule could not be saved.";
}

function getWorkAreaErrorMessage(error: unknown, label?: string) {
  if (error instanceof ApiError) {
    if (error.code === "WORK_AREA_IN_USE") {
      return `Can't deactivate '${label ?? "this work area"}' — it's still used by active coverage rules.`;
    }
    if (error.code === "WORK_AREA_LABEL_EXISTS") {
      return "An active work area already uses this label.";
    }
    if (error.code === "VALIDATION_ERROR") {
      return "Enter a work-area label.";
    }
    if (error.status === 403) {
      return "You do not have permission to manage work areas.";
    }
    return error.message || "The work area could not be saved.";
  }
  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to the server.";
  }
  return "The work area could not be saved.";
}

function validateCoverageRule(draft: CoverageRuleDraft) {
  const errors: string[] = [];
  const headcount = Number(draft.requiredHeadcount);
  if (!draft.startTime || !draft.endTime) {
    errors.push("Enter both a start and end time.");
  } else if (draft.endTime <= draft.startTime) {
    errors.push(
      "End time must be after start time. Overnight coverage isn't supported yet.",
    );
  }
  if (!Number.isInteger(headcount) || headcount < 1) {
    errors.push("Headcount must be at least 1.");
  }
  return errors;
}

function ruleDraftFromTemplate(rule: CoverageTemplate): CoverageRuleDraft {
  return {
    dayOfWeek: rule.day_of_week,
    startTime: timeInputValue(rule.start_time),
    endTime: timeInputValue(rule.end_time),
    requiredHeadcount: String(rule.required_headcount),
    requiredRole: rule.required_role ?? "",
    workAreaId: rule.work_area_id ?? "",
    displayLabel: rule.display_label ?? "",
  };
}

function CoverageRuleCard({
  rule,
  workArea,
  showWorkAreaTag,
  onEdit,
}: {
  rule: CoverageTemplate;
  workArea: WorkArea | undefined;
  showWorkAreaTag: boolean;
  onEdit: (rule: CoverageTemplate) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onEdit(rule)}
      className={cn(
        "w-full rounded-2xl border border-violet-200 bg-violet-50 px-3 py-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500",
        !rule.is_active && "border-slate-200 bg-slate-100 opacity-65",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-sm font-semibold leading-5 text-slate-950">
          {coverageRuleTitle(rule)}
        </p>
        <span className="shrink-0 rounded-full bg-violet-600 px-2 py-1 text-xs font-semibold text-white">
          ×{rule.required_headcount}
        </span>
      </div>
      <p className="mt-2 text-xs font-medium text-slate-600">
        {formatTime(rule.start_time)}–{formatTime(rule.end_time)}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {rule.required_role ? (
          <span className="rounded-full border border-violet-200 bg-white px-2 py-0.5 text-[11px] font-medium text-violet-700">
            {rule.required_role}
          </span>
        ) : null}
        {showWorkAreaTag && workArea ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600",
              !workArea.is_active && "border-slate-300 bg-slate-200 text-slate-500",
            )}
          >
            <MapPin className="size-3" aria-hidden="true" />
            {workArea.label}
            {!workArea.is_active ? " (inactive)" : ""}
          </span>
        ) : null}
      </div>
      {!rule.is_active ? (
        <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Inactive
        </p>
      ) : null}
    </button>
  );
}

function RuleDay({
  day,
  rules,
  workAreaById,
  showWorkAreaTags,
  onAdd,
  onEdit,
  compact = false,
}: {
  day: (typeof coverageDays)[number];
  rules: CoverageTemplate[];
  workAreaById: Map<string, WorkArea>;
  showWorkAreaTags: boolean;
  onAdd: () => void;
  onEdit: (rule: CoverageTemplate) => void;
  compact?: boolean;
}) {
  return (
    <section
      className={cn(
        "min-w-0 border-slate-200 bg-white",
        compact ? "rounded-2xl border" : "border-r last:border-r-0",
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between border-b border-slate-200 bg-slate-50",
          compact ? "rounded-t-2xl px-4 py-3" : "px-3 py-3",
        )}
      >
        <h3 className="text-sm font-semibold text-slate-800">
          <span className="hidden lg:inline">{day.label}</span>
          <span className="lg:hidden">{day.shortLabel}</span>
        </h3>
        <span className="text-xs text-slate-400">{rules.length}</span>
      </div>
      <div className={cn("space-y-3", compact ? "p-4" : "min-h-44 p-2")}>
        {rules.map((rule) => (
          <CoverageRuleCard
            key={rule.id}
            rule={rule}
            workArea={
              rule.work_area_id ? workAreaById.get(rule.work_area_id) : undefined
            }
            showWorkAreaTag={showWorkAreaTags}
            onEdit={onEdit}
          />
        ))}
        <button
          type="button"
          onClick={onAdd}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-violet-200 bg-white px-2 py-2 text-xs font-medium text-violet-700 transition hover:border-violet-400 hover:bg-violet-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          Add rule
        </button>
      </div>
    </section>
  );
}

export function CoverageRules({ store }: { store: Store | null }) {
  const [rules, setRules] = useState<CoverageTemplate[]>([]);
  const [workAreas, setWorkAreas] = useState<WorkArea[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pageMessage, setPageMessage] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [isRuleFormOpen, setIsRuleFormOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CoverageTemplate | null>(null);
  const [ruleDraft, setRuleDraft] =
    useState<CoverageRuleDraft>(emptyCoverageRuleDraft);
  const [selectedDays, setSelectedDays] = useState<number[]>(
    coverageDays.map((day) => day.value),
  );
  const [retryDays, setRetryDays] = useState<number[] | null>(null);
  const [ruleFormError, setRuleFormError] = useState<string | null>(null);
  const [ruleFormMessage, setRuleFormMessage] = useState<string | null>(null);
  const [isSavingRule, setIsSavingRule] = useState(false);
  const [isManagingWorkAreas, setIsManagingWorkAreas] = useState(false);
  const [newWorkAreaLabel, setNewWorkAreaLabel] = useState("");
  const [editingWorkAreaId, setEditingWorkAreaId] = useState<string | null>(null);
  const [editingWorkAreaLabel, setEditingWorkAreaLabel] = useState("");
  const [workAreaError, setWorkAreaError] = useState<string | null>(null);
  const [workAreaMessage, setWorkAreaMessage] = useState<string | null>(null);
  const [workAreaMutationId, setWorkAreaMutationId] = useState<string | null>(null);

  const activeWorkAreas = useMemo(
    () => workAreas.filter((workArea) => workArea.is_active),
    [workAreas],
  );
  const inactiveWorkAreas = useMemo(
    () => workAreas.filter((workArea) => !workArea.is_active),
    [workAreas],
  );
  const workAreaById = useMemo(
    () => new Map(workAreas.map((workArea) => [workArea.id, workArea])),
    [workAreas],
  );
  const visibleRules = useMemo(
    () => rules.filter((rule) => showInactive || rule.is_active),
    [rules, showInactive],
  );
  const rulesByDay = useMemo(
    () =>
      coverageDays.map((day) =>
        visibleRules
          .filter((rule) => rule.day_of_week === day.value)
          .sort(
            (first, second) =>
              first.start_time.localeCompare(second.start_time) ||
              first.created_at.localeCompare(second.created_at),
          ),
      ),
    [visibleRules],
  );

  const refreshData = useCallback(
    async (showLoading = true) => {
      if (!store) {
        setRules([]);
        setWorkAreas([]);
        setLoadError(null);
        return;
      }
      const token = getAccessToken();
      if (!token) {
        setLoadError("Your session has expired. Sign in again.");
        return;
      }
      if (showLoading) {
        setIsLoading(true);
      }
      setLoadError(null);
      try {
        const [nextRules, nextWorkAreas] = await Promise.all([
          listCoverageTemplates(token, store.id),
          listWorkAreas(token, store.id),
        ]);
        setRules(nextRules);
        setWorkAreas(nextWorkAreas);
      } catch (error) {
        setLoadError(getCoverageErrorMessage(error));
      } finally {
        if (showLoading) {
          setIsLoading(false);
        }
      }
    },
    [store],
  );

  useEffect(() => {
    setPageMessage(null);
    setShowInactive(false);
    setIsRuleFormOpen(false);
    setIsManagingWorkAreas(false);
    void refreshData();
  }, [refreshData]);

  function openCreateRule() {
    setEditingRule(null);
    setRuleDraft(emptyCoverageRuleDraft);
    setSelectedDays(coverageDays.map((day) => day.value));
    setRetryDays(null);
    setRuleFormError(null);
    setRuleFormMessage(null);
    setIsRuleFormOpen(true);
  }

  function openEditRule(rule: CoverageTemplate) {
    setEditingRule(rule);
    setRuleDraft(ruleDraftFromTemplate(rule));
    setSelectedDays([rule.day_of_week]);
    setRetryDays(null);
    setRuleFormError(null);
    setRuleFormMessage(null);
    setIsRuleFormOpen(true);
  }

  function closeRuleForm() {
    if (!isSavingRule) {
      setIsRuleFormOpen(false);
    }
  }

  function updateRuleDraft<Key extends keyof CoverageRuleDraft>(
    key: Key,
    value: CoverageRuleDraft[Key],
  ) {
    setRuleDraft((current) => ({ ...current, [key]: value }));
    setRuleFormError(null);
  }

  function toggleCreateDay(day: number) {
    if (retryDays && !retryDays.includes(day)) {
      return;
    }
    setSelectedDays((current) =>
      current.includes(day)
        ? current.filter((candidate) => candidate !== day)
        : [...current, day].sort(),
    );
    setRuleFormError(null);
  }

  function validateRuleForSave() {
    const errors = validateCoverageRule(ruleDraft);
    if (!editingRule && selectedDays.length === 0) {
      errors.push("Choose at least one day.");
    }
    const selectedWorkArea = ruleDraft.workAreaId
      ? workAreaById.get(ruleDraft.workAreaId)
      : null;
    if (selectedWorkArea && !selectedWorkArea.is_active) {
      errors.push("Choose an active work area, or clear the optional work area.");
    }
    return errors;
  }

  function coveragePayload(dayOfWeek: number) {
    return {
      store_id: store?.id ?? "",
      day_of_week: dayOfWeek,
      start_time: ruleDraft.startTime,
      end_time: ruleDraft.endTime,
      required_headcount: Number(ruleDraft.requiredHeadcount),
      required_role: ruleDraft.requiredRole || null,
      work_area_id: ruleDraft.workAreaId || null,
      display_label: ruleDraft.displayLabel.trim() || null,
    };
  }

  async function submitCreateBatch() {
    if (!store || isSavingRule) {
      return;
    }
    const validationErrors = validateRuleForSave();
    if (validationErrors.length > 0) {
      setRuleFormError(validationErrors[0]);
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setRuleFormError("Your session has expired. Sign in again.");
      return;
    }

    setIsSavingRule(true);
    setRuleFormError(null);
    setRuleFormMessage(null);
    const attemptedDays = [...selectedDays].sort();
    const results = await Promise.allSettled(
      attemptedDays.map((day) =>
        createCoverageTemplate(token, coveragePayload(day)),
      ),
    );
    const succeededDays = attemptedDays.filter(
      (_, index) => results[index].status === "fulfilled",
    );
    const failedDays = attemptedDays.filter(
      (_, index) => results[index].status === "rejected",
    );

    await refreshData(false);
    const successCount = succeededDays.length;
    if (failedDays.length === 0) {
      const message = `Created ${successCount} ${
        successCount === 1 ? "rule" : "rules"
      }.`;
      setPageMessage(message);
      setIsRuleFormOpen(false);
      setRetryDays(null);
    } else {
      const failedLabel = joinDayLabels(failedDays);
      const message =
        successCount > 0
          ? `Created ${successCount} ${
              successCount === 1 ? "rule" : "rules"
            }. ${failedLabel} could not be created.`
          : `No rules were created. ${failedLabel} could not be created.`;
      setRuleFormMessage(message);
      setPageMessage(message);
      setSelectedDays(failedDays);
      setRetryDays(failedDays);
    }
    setIsSavingRule(false);
  }

  async function submitRuleUpdate(reactivate = false) {
    if (!store || !editingRule || isSavingRule) {
      return;
    }
    const validationErrors = validateRuleForSave();
    if (validationErrors.length > 0) {
      setRuleFormError(validationErrors[0]);
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setRuleFormError("Your session has expired. Sign in again.");
      return;
    }

    setIsSavingRule(true);
    setRuleFormError(null);
    try {
      await updateCoverageTemplate(token, editingRule.id, {
        day_of_week: ruleDraft.dayOfWeek,
        start_time: ruleDraft.startTime,
        end_time: ruleDraft.endTime,
        required_headcount: Number(ruleDraft.requiredHeadcount),
        required_role: ruleDraft.requiredRole || null,
        work_area_id: ruleDraft.workAreaId || null,
        display_label: ruleDraft.displayLabel.trim() || null,
        ...(reactivate ? { is_active: true } : {}),
      });
      await refreshData(false);
      setPageMessage(reactivate ? "Coverage rule reactivated." : "Coverage rule saved.");
      setIsRuleFormOpen(false);
    } catch (error) {
      setRuleFormError(getCoverageErrorMessage(error));
    } finally {
      setIsSavingRule(false);
    }
  }

  async function submitRuleDeactivation() {
    if (!editingRule || isSavingRule) {
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setRuleFormError("Your session has expired. Sign in again.");
      return;
    }
    setIsSavingRule(true);
    setRuleFormError(null);
    try {
      await deactivateCoverageTemplate(token, editingRule.id);
      await refreshData(false);
      setPageMessage("Coverage rule deactivated.");
      setIsRuleFormOpen(false);
    } catch (error) {
      setRuleFormError(getCoverageErrorMessage(error));
    } finally {
      setIsSavingRule(false);
    }
  }

  async function submitNewWorkArea(event: FormEvent) {
    event.preventDefault();
    if (!store || workAreaMutationId) {
      return;
    }
    const label = newWorkAreaLabel.trim();
    if (!label) {
      setWorkAreaError("Enter a work-area label.");
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setWorkAreaError("Your session has expired. Sign in again.");
      return;
    }
    setWorkAreaMutationId("create");
    setWorkAreaError(null);
    setWorkAreaMessage(null);
    try {
      await createWorkArea(token, store.id, { label });
      await refreshData(false);
      setNewWorkAreaLabel("");
      setWorkAreaMessage(`Created '${label}'.`);
    } catch (error) {
      setWorkAreaError(getWorkAreaErrorMessage(error, label));
    } finally {
      setWorkAreaMutationId(null);
    }
  }

  async function submitWorkAreaRename(workArea: WorkArea) {
    if (!store || !workArea.is_active || workAreaMutationId) {
      return;
    }
    const label = editingWorkAreaLabel.trim();
    if (!label) {
      setWorkAreaError("Enter a work-area label.");
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setWorkAreaError("Your session has expired. Sign in again.");
      return;
    }
    setWorkAreaMutationId(workArea.id);
    setWorkAreaError(null);
    setWorkAreaMessage(null);
    try {
      await updateWorkArea(token, store.id, workArea.id, { label });
      await refreshData(false);
      setEditingWorkAreaId(null);
      setEditingWorkAreaLabel("");
      setWorkAreaMessage(`Renamed work area to '${label}'.`);
    } catch (error) {
      setWorkAreaError(getWorkAreaErrorMessage(error, label));
    } finally {
      setWorkAreaMutationId(null);
    }
  }

  async function submitWorkAreaDeactivation(workArea: WorkArea) {
    if (!store || workAreaMutationId) {
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setWorkAreaError("Your session has expired. Sign in again.");
      return;
    }
    setWorkAreaMutationId(workArea.id);
    setWorkAreaError(null);
    setWorkAreaMessage(null);
    try {
      await deactivateWorkArea(token, store.id, workArea.id);
      await refreshData(false);
      setWorkAreaMessage(`Deactivated '${workArea.label}'.`);
    } catch (error) {
      setWorkAreaError(getWorkAreaErrorMessage(error, workArea.label));
    } finally {
      setWorkAreaMutationId(null);
    }
  }

  if (!store) {
    return (
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-6 text-sm text-slate-600">
          Create an active site before configuring coverage rules.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-violet-100 bg-gradient-to-br from-white to-violet-50/50 shadow-sm">
        <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-lg">Weekly coverage rules</CardTitle>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              These rules describe how many people you need. Generate Week turns them
              into actual shifts.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setWorkAreaError(null);
                setWorkAreaMessage(null);
                setIsManagingWorkAreas(true);
              }}
            >
              <Settings2 className="mr-2 size-4" aria-hidden="true" />
              Manage work areas (optional)
            </Button>
            <Button type="button" onClick={openCreateRule}>
              <Plus className="mr-2 size-4" aria-hidden="true" />
              Add coverage rule
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 border-t border-violet-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">
              {rules.filter((rule) => rule.is_active).length} active{" "}
              {rules.filter((rule) => rule.is_active).length === 1 ? "rule" : "rules"}{" "}
              for {store.name}
            </p>
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(event) => setShowInactive(event.target.checked)}
                className="size-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
              />
              Show inactive
            </label>
          </div>
        </CardContent>
      </Card>

      {pageMessage ? (
        <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {pageMessage}
        </p>
      ) : null}
      {loadError ? (
        <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError}
        </p>
      ) : null}

      {isLoading ? (
        <div className="flex items-center justify-center gap-3 rounded-3xl border border-slate-200 bg-white px-5 py-16 text-sm text-slate-600 shadow-sm">
          <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          Loading coverage rules...
        </div>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-3xl border border-slate-200 shadow-sm md:grid md:grid-cols-7">
            {coverageDays.map((day, index) => (
              <RuleDay
                key={day.value}
                day={day}
                rules={rulesByDay[index]}
                workAreaById={workAreaById}
                showWorkAreaTags={workAreas.length > 0}
                onAdd={openCreateRule}
                onEdit={openEditRule}
              />
            ))}
          </div>
          <div className="space-y-4 md:hidden">
            {coverageDays.map((day, index) => (
              <RuleDay
                key={day.value}
                day={day}
                rules={rulesByDay[index]}
                workAreaById={workAreaById}
                showWorkAreaTags={workAreas.length > 0}
                onAdd={openCreateRule}
                onEdit={openEditRule}
                compact
              />
            ))}
          </div>
        </>
      )}

      {isRuleFormOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/40 px-4 py-6 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="coverage-rule-dialog-title"
        >
          <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3
                  id="coverage-rule-dialog-title"
                  className="text-lg font-semibold text-slate-950"
                >
                  {editingRule ? "Edit coverage rule" : "Create coverage rules"}
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  {editingRule
                    ? `Update the ${coverageDays[editingRule.day_of_week]?.label ?? ""} rule.`
                    : "Choose the days that share this staffing pattern."}
                </p>
              </div>
              <button
                type="button"
                onClick={closeRuleForm}
                disabled={isSavingRule}
                className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
                aria-label="Close coverage rule form"
              >
                <X className="size-5" />
              </button>
            </div>

            <form
              className="space-y-5 px-5 py-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (editingRule) {
                  void submitRuleUpdate();
                } else {
                  void submitCreateBatch();
                }
              }}
            >
              {ruleFormError ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {ruleFormError}
                </p>
              ) : null}
              {ruleFormMessage ? (
                <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {ruleFormMessage}
                </p>
              ) : null}

              {!editingRule ? (
                <fieldset>
                  <legend className="text-sm font-medium text-slate-700">Days</legend>
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {coverageDays.map((day) => {
                      const disabled = Boolean(
                        retryDays && !retryDays.includes(day.value),
                      );
                      return (
                        <label
                          key={day.value}
                          className={cn(
                            "flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700",
                            selectedDays.includes(day.value) &&
                              "border-violet-300 bg-violet-50 text-violet-800",
                            disabled && "cursor-not-allowed bg-slate-50 opacity-45",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={selectedDays.includes(day.value)}
                            onChange={() => toggleCreateDay(day.value)}
                            disabled={disabled || isSavingRule}
                            className="size-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
                          />
                          {day.label}
                        </label>
                      );
                    })}
                  </div>
                  {retryDays ? (
                    <p className="mt-2 text-sm text-slate-500">
                      Successful days are locked for this retry so they cannot be
                      duplicated.
                    </p>
                  ) : null}
                </fieldset>
              ) : (
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-700">Day</span>
                  <select
                    value={ruleDraft.dayOfWeek}
                    onChange={(event) =>
                      updateRuleDraft("dayOfWeek", Number(event.target.value))
                    }
                    disabled={isSavingRule}
                    className="flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  >
                    {coverageDays.map((day) => (
                      <option key={day.value} value={day.value}>
                        {day.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">Start time</span>
                  <Input
                    type="time"
                    value={ruleDraft.startTime}
                    onChange={(event) =>
                      updateRuleDraft("startTime", event.target.value)
                    }
                    disabled={isSavingRule}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">End time</span>
                  <Input
                    type="time"
                    value={ruleDraft.endTime}
                    onChange={(event) =>
                      updateRuleDraft("endTime", event.target.value)
                    }
                    disabled={isSavingRule}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    People needed
                  </span>
                  <Input
                    type="number"
                    min={1}
                    step={1}
                    value={ruleDraft.requiredHeadcount}
                    onChange={(event) =>
                      updateRuleDraft("requiredHeadcount", event.target.value)
                    }
                    disabled={isSavingRule}
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    Required role (optional)
                  </span>
                  <select
                    value={ruleDraft.requiredRole}
                    onChange={(event) =>
                      updateRuleDraft("requiredRole", event.target.value)
                    }
                    disabled={isSavingRule}
                    className="flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  >
                    <option value="">Any operational role</option>
                    {ruleDraft.requiredRole &&
                    !staffRoleOptions.includes(ruleDraft.requiredRole) ? (
                      <option value={ruleDraft.requiredRole} disabled>
                        {ruleDraft.requiredRole} (existing role)
                      </option>
                    ) : null}
                    {staffRoleOptions.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">
                  Display label (optional)
                </span>
                <Input
                  value={ruleDraft.displayLabel}
                  onChange={(event) =>
                    updateRuleDraft("displayLabel", event.target.value)
                  }
                  placeholder="e.g. Morning opening cover"
                  disabled={isSavingRule}
                />
              </label>

              {activeWorkAreas.length > 0 ? (
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    Work area (optional)
                  </span>
                  <select
                    value={ruleDraft.workAreaId}
                    onChange={(event) =>
                      updateRuleDraft("workAreaId", event.target.value)
                    }
                    disabled={isSavingRule}
                    className="flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  >
                    <option value="">No work area</option>
                    {ruleDraft.workAreaId &&
                    !activeWorkAreas.some(
                      (workArea) => workArea.id === ruleDraft.workAreaId,
                    ) ? (
                      <option value={ruleDraft.workAreaId} disabled>
                        {workAreaById.get(ruleDraft.workAreaId)?.label ??
                          "Historical work area"}{" "}
                        (inactive)
                      </option>
                    ) : null}
                    {activeWorkAreas.map((workArea) => (
                      <option key={workArea.id} value={workArea.id}>
                        {workArea.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : ruleDraft.workAreaId ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800">
                  <p>
                    This inactive rule references{" "}
                    <strong>
                      {workAreaById.get(ruleDraft.workAreaId)?.label ??
                        "an inactive work area"}
                    </strong>
                    . Clear it before reactivating the rule.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-3 border-amber-300 bg-white text-amber-800"
                    onClick={() => updateRuleDraft("workAreaId", "")}
                    disabled={isSavingRule}
                  >
                    Clear inactive work area
                  </Button>
                </div>
              ) : null}

              <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  {editingRule?.is_active ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void submitRuleDeactivation()}
                      disabled={isSavingRule}
                      className="border-red-200 text-red-700 hover:bg-red-50"
                    >
                      Deactivate rule
                    </Button>
                  ) : editingRule ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void submitRuleUpdate(true)}
                      disabled={isSavingRule}
                      className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                    >
                      Reactivate rule
                    </Button>
                  ) : null}
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={closeRuleForm}
                    disabled={isSavingRule}
                  >
                    Close
                  </Button>
                  <Button type="submit" disabled={isSavingRule}>
                    {isSavingRule ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Saving...
                      </>
                    ) : editingRule ? (
                      "Save rule"
                    ) : retryDays ? (
                      `Retry ${selectedDays.length} failed ${
                        selectedDays.length === 1 ? "day" : "days"
                      }`
                    ) : (
                      `Create ${selectedDays.length} ${
                        selectedDays.length === 1 ? "rule" : "rules"
                      }`
                    )}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {isManagingWorkAreas ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/40 px-4 py-6 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="work-area-dialog-title"
        >
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3
                  id="work-area-dialog-title"
                  className="text-lg font-semibold text-slate-950"
                >
                  Manage work areas
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Optional operational tags for {store.name}.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (!workAreaMutationId) {
                    setIsManagingWorkAreas(false);
                  }
                }}
                disabled={Boolean(workAreaMutationId)}
                className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
                aria-label="Close work-area manager"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-5 px-5 py-5">
              {workAreaError ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {workAreaError}
                </p>
              ) : null}
              {workAreaMessage ? (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  {workAreaMessage}
                </p>
              ) : null}

              <form
                className="flex flex-col gap-3 sm:flex-row"
                onSubmit={(event) => void submitNewWorkArea(event)}
              >
                <label className="flex-1 space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    New work-area label
                  </span>
                  <Input
                    value={newWorkAreaLabel}
                    onChange={(event) => {
                      setNewWorkAreaLabel(event.target.value);
                      setWorkAreaError(null);
                    }}
                    placeholder="e.g. Front counter"
                    disabled={Boolean(workAreaMutationId)}
                  />
                </label>
                <Button
                  type="submit"
                  className="sm:mt-7"
                  disabled={Boolean(workAreaMutationId)}
                >
                  {workAreaMutationId === "create" ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 size-4" />
                  )}
                  Add work area
                </Button>
              </form>

              <div className="space-y-3 border-t border-slate-200 pt-5">
                {workAreas.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                    No work areas. Coverage rules remain available without them.
                  </p>
                ) : (
                  <div className="space-y-6">
                    {activeWorkAreas.length > 0 ? (
                      <section className="space-y-3">
                        <div>
                          <h4 className="text-sm font-semibold text-slate-900">
                            Active work areas
                          </h4>
                          <p className="mt-1 text-sm text-slate-500">
                            Available for new and active coverage rules.
                          </p>
                        </div>
                        {activeWorkAreas.map((workArea) => (
                          <div
                            key={workArea.id}
                            className="rounded-2xl border border-slate-200 px-4 py-3"
                          >
                            {editingWorkAreaId === workArea.id ? (
                              <div className="flex flex-col gap-3 sm:flex-row">
                                <Input
                                  value={editingWorkAreaLabel}
                                  onChange={(event) => {
                                    setEditingWorkAreaLabel(event.target.value);
                                    setWorkAreaError(null);
                                  }}
                                  disabled={workAreaMutationId === workArea.id}
                                  aria-label={`Rename ${workArea.label}`}
                                />
                                <div className="flex gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    onClick={() => void submitWorkAreaRename(workArea)}
                                    disabled={Boolean(workAreaMutationId)}
                                  >
                                    Save
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setEditingWorkAreaId(null)}
                                    disabled={Boolean(workAreaMutationId)}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                  <p className="font-medium text-slate-900">
                                    {workArea.label}
                                  </p>
                                  <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                                    Active
                                  </p>
                                </div>
                                <div className="flex gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setEditingWorkAreaId(workArea.id);
                                      setEditingWorkAreaLabel(workArea.label);
                                      setWorkAreaError(null);
                                      setWorkAreaMessage(null);
                                    }}
                                    disabled={Boolean(workAreaMutationId)}
                                  >
                                    Rename
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="border-red-200 text-red-700 hover:bg-red-50"
                                    onClick={() =>
                                      void submitWorkAreaDeactivation(workArea)
                                    }
                                    disabled={Boolean(workAreaMutationId)}
                                  >
                                    {workAreaMutationId === workArea.id ? (
                                      <Loader2 className="mr-2 size-4 animate-spin" />
                                    ) : null}
                                    Deactivate
                                  </Button>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </section>
                    ) : null}

                    {inactiveWorkAreas.length > 0 ? (
                      <section className="space-y-3 border-t border-slate-200 pt-5">
                        <div>
                          <h4 className="text-sm font-semibold text-slate-900">
                            Inactive work areas
                          </h4>
                          <p className="mt-1 text-sm leading-6 text-slate-500">
                            Kept for historical coverage rules. Create a new work area
                            if this operational label is needed again.
                          </p>
                        </div>
                        {inactiveWorkAreas.map((workArea) => (
                          <div
                            key={workArea.id}
                            className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 opacity-70"
                          >
                            <p className="font-medium text-slate-700">
                              {workArea.label}
                            </p>
                            <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                              Inactive · Historical record
                            </p>
                          </div>
                        ))}
                      </section>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
                <AlertTriangle
                  className="mt-1 size-4 shrink-0 text-slate-400"
                  aria-hidden="true"
                />
                Work areas cannot be deactivated while active coverage rules still
                use them.
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
