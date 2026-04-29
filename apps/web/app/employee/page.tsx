"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  getCurrentEmployeeSession,
  getEmployeeMyRota,
  type EmployeeMeResponse,
  type EmployeeMyRotaShift,
} from "@/lib/api-client";
import {
  clearEmployeeAccessToken,
  getEmployeeAccessToken,
} from "@/lib/employee-auth-token";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const dayLabels = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

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

function formatDisplayDate(date: Date) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatTimeRange(shift: EmployeeMyRotaShift) {
  const formatter = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return `${formatter.format(new Date(shift.start_time))} - ${formatter.format(
    new Date(shift.end_time),
  )}`;
}

function getShiftDayLabel(shift: EmployeeMyRotaShift) {
  const dayIndex = new Date(shift.start_time).getDay();
  const mondayIndex = dayIndex === 0 ? 6 : dayIndex - 1;
  return dayLabels[mondayIndex] ?? "Shift";
}

export default function EmployeePortalPage() {
  const [weekStart, setWeekStart] = useState(() => getMondayWeekStart(new Date()));
  const [session, setSession] = useState<EmployeeMeResponse | null>(null);
  const [shifts, setShifts] = useState<EmployeeMyRotaShift[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const weekStartParam = formatDateParam(weekStart);
  const weekEnd = addDays(weekStart, 6);

  useEffect(() => {
    const token = getEmployeeAccessToken();
    if (!token) {
      setIsLoading(false);
      setSession(null);
      setShifts([]);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    async function loadEmployeeRota(accessToken: string) {
      try {
        const [employeeSession, rota] = await Promise.all([
          getCurrentEmployeeSession(accessToken),
          getEmployeeMyRota(accessToken, weekStartParam),
        ]);
        if (isMounted) {
          setSession(employeeSession);
          setShifts(rota.shifts);
        }
      } catch {
        if (isMounted) {
          clearEmployeeAccessToken();
          setSession(null);
          setShifts([]);
          setError("Could not load your rota. Please sign in again.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadEmployeeRota(token);

    return () => {
      isMounted = false;
    };
  }, [weekStartParam]);

  function moveWeek(delta: number) {
    setWeekStart((current) => addDays(current, delta * 7));
  }

  function resetToCurrentWeek() {
    setWeekStart(getMondayWeekStart(new Date()));
  }

  function signOut() {
    clearEmployeeAccessToken();
    setSession(null);
    setShifts([]);
  }

  if (!isLoading && !session) {
    return (
      <main className="min-h-screen bg-slate-100 px-4 py-10">
        <div className="mx-auto max-w-md">
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-6">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
                Employee Portal
              </h1>
              <p className="text-sm leading-6 text-slate-500">
                Sign in to view your published rota.
              </p>
              {error ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
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
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
              Employee Portal
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              My Rota
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {session ? `${session.display_name} at site ${session.site_id}` : "Loading..."}
            </p>
          </div>
          {session ? (
            <Button type="button" variant="outline" onClick={signOut}>
              Sign out
            </Button>
          ) : null}
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
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => moveWeek(-1)}>
                  Previous
                </Button>
                <Button type="button" variant="outline" onClick={resetToCurrentWeek}>
                  This week
                </Button>
                <Button type="button" variant="outline" onClick={() => moveWeek(1)}>
                  Next
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                Loading your rota...
              </p>
            ) : error ? (
              <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            ) : shifts.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
                No published shifts for this week.
              </p>
            ) : (
              <div className="space-y-3">
                {shifts.map((shift) => (
                  <div
                    key={shift.id}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-slate-950">
                          {getShiftDayLabel(shift)}
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          {formatTimeRange(shift)}
                        </p>
                      </div>
                      <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                        {shift.status}
                      </span>
                    </div>
                    {shift.role_required ? (
                      <p className="mt-3 text-sm text-slate-500">
                        Role: {shift.role_required}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
