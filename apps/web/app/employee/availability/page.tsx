"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createEmployeeAvailability,
  deleteEmployeeAvailability,
  getCurrentEmployeeSession,
  getEmployeeAvailability,
  restoreEmployeeSession,
  type EmployeeAvailabilityItem,
  type EmployeeAvailabilityType,
  type EmployeeMeResponse,
} from "@/lib/api-client";
import {
  clearEmployeeAccessToken,
  getEmployeeAccessToken,
} from "@/lib/employee-auth-token";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const availabilityLabels: Record<EmployeeAvailabilityType, string> = {
  available: "Available",
  unavailable: "Unavailable",
  available_extra: "Extra availability",
};

function getMondayWeekStart(date: Date) {
  const next = new Date(date);
  const day = next.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  next.setDate(next.getDate() + diff);
  next.setHours(0, 0, 0, 0);
  return next;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function formatDateParam(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDisplayDate(value: string | Date) {
  const date = typeof value === "string" ? new Date(`${value}T00:00:00`) : value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatTime(item: EmployeeAvailabilityItem) {
  if (!item.start_time || !item.end_time) {
    return "All day";
  }
  return `${item.start_time.slice(0, 5)} - ${item.end_time.slice(0, 5)}`;
}

function friendlyAvailabilityError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA") {
      return "This week is locked because your rota has already been published.";
    }
    if (error.code === "AVAILABILITY_DUPLICATE") {
      return "That availability row already exists.";
    }
    return error.message;
  }
  return "Could not update availability. Please try again.";
}

export default function EmployeeAvailabilityPage() {
  const [weekStart, setWeekStart] = useState(() => getMondayWeekStart(new Date()));
  const [session, setSession] = useState<EmployeeMeResponse | null>(null);
  const [items, setItems] = useState<EmployeeAvailabilityItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [type, setType] = useState<EmployeeAvailabilityType>("available");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [notes, setNotes] = useState("");
  const weekStartParam = formatDateParam(weekStart);
  const weekEnd = addDays(weekStart, 6);
  const defaultDate = useMemo(() => formatDateParam(weekStart), [weekStart]);

  useEffect(() => {
    setDate(defaultDate);
  }, [defaultDate]);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    async function loadAvailability() {
      let accessToken = getEmployeeAccessToken();
      if (!accessToken) {
        try {
          accessToken = await restoreEmployeeSession();
        } catch {
          if (isMounted) {
            setIsLoading(false);
            setSession(null);
            setItems([]);
          }
          return;
        }
      }

      try {
        const [employeeSession, availability] = await Promise.all([
          getCurrentEmployeeSession(accessToken),
          getEmployeeAvailability(accessToken, weekStartParam),
        ]);
        if (isMounted) {
          setSession(employeeSession);
          setItems(availability.items);
        }
      } catch {
        if (isMounted) {
          clearEmployeeAccessToken();
          setSession(null);
          setItems([]);
          setError("Could not load your availability. Please sign in again.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadAvailability();

    return () => {
      isMounted = false;
    };
  }, [weekStartParam]);

  function moveWeek(delta: number) {
    setWeekStart((current) => addDays(current, delta * 7));
  }

  async function submitAvailability(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getEmployeeAccessToken();
    if (!token) {
      setSession(null);
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      const created = await createEmployeeAvailability(token, {
        week_start: weekStartParam,
        date,
        start_time: startTime || null,
        end_time: endTime || null,
        type,
        notes: notes.trim() || null,
      });
      setItems((current) => [...current, created].sort((a, b) => a.date.localeCompare(b.date)));
      setNotes("");
    } catch (caughtError) {
      setFormError(friendlyAvailabilityError(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteEntry(entryId: string) {
    const token = getEmployeeAccessToken();
    if (!token) {
      setSession(null);
      return;
    }

    setFormError(null);
    try {
      await deleteEmployeeAvailability(token, entryId);
      setItems((current) => current.filter((item) => item.id !== entryId));
    } catch (caughtError) {
      setFormError(friendlyAvailabilityError(caughtError));
    }
  }

  if (!isLoading && !session) {
    return (
      <main className="min-h-screen bg-slate-100 px-4 py-10">
        <div className="mx-auto max-w-md">
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-6">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
                Availability
              </h1>
              <p className="text-sm leading-6 text-slate-500">
                Sign in to manage your availability.
              </p>
              {error ? (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </p>
              ) : null}
              <Button asChild className="w-full">
                <Link href="/employee/login">Sign in</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
              Employee Portal
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              Availability
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {session ? `${session.display_name} at site ${session.site_id}` : "Loading..."}
            </p>
          </div>
          <Button asChild variant="outline">
            <Link href="/employee">My rota</Link>
          </Button>
        </div>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Week</CardTitle>
                <p className="mt-1 text-sm text-slate-500">
                  {formatDisplayDate(weekStart)} - {formatDisplayDate(weekEnd)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => moveWeek(-1)}>
                  Previous
                </Button>
                <Button type="button" variant="outline" onClick={() => setWeekStart(getMondayWeekStart(new Date()))}>
                  This week
                </Button>
                <Button type="button" variant="outline" onClick={() => moveWeek(1)}>
                  Next
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
            <form className="space-y-4" onSubmit={submitAvailability}>
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="availability-date">
                  Date
                </label>
                <input
                  id="availability-date"
                  type="date"
                  value={date}
                  min={weekStartParam}
                  max={formatDateParam(weekEnd)}
                  onChange={(event) => setDate(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="availability-type">
                  Type
                </label>
                <select
                  id="availability-type"
                  value={type}
                  onChange={(event) => setType(event.target.value as EmployeeAvailabilityType)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="available">Available</option>
                  <option value="unavailable">Unavailable</option>
                  <option value="available_extra">Extra availability</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="availability-start">
                    Start
                  </label>
                  <input
                    id="availability-start"
                    type="time"
                    value={startTime}
                    onChange={(event) => setStartTime(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="availability-end">
                    End
                  </label>
                  <input
                    id="availability-end"
                    type="time"
                    value={endTime}
                    onChange={(event) => setEndTime(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700" htmlFor="availability-notes">
                  Notes
                </label>
                <textarea
                  id="availability-notes"
                  value={notes}
                  maxLength={500}
                  onChange={(event) => setNotes(event.target.value)}
                  className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              {formError ? (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {formError}
                </p>
              ) : null}
              <Button type="submit" disabled={isSaving || isLoading} className="w-full">
                {isSaving ? "Saving..." : "Add availability"}
              </Button>
            </form>

            <div>
              {isLoading ? (
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  Loading availability...
                </p>
              ) : items.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
                  No availability rows for this week.
                </p>
              ) : (
                <div className="space-y-3">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="font-medium text-slate-950">
                            {formatDisplayDate(item.date)}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">
                            {availabilityLabels[item.type]} · {formatTime(item)}
                          </p>
                          {item.notes ? (
                            <p className="mt-2 text-sm text-slate-500">{item.notes}</p>
                          ) : null}
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => deleteEntry(item.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
