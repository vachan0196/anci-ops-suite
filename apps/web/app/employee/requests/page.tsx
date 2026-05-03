"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  acceptEmployeeInboundRequest,
  cancelEmployeeRequest,
  createEmployeeRequest,
  declineEmployeeInboundRequest,
  getCurrentEmployeeSession,
  getEmployeeInboundRequests,
  getEmployeeMyRota,
  getEmployeeRequestTargets,
  getEmployeeRequests,
  type EmployeeInboundRequestItem,
  type EmployeeMeResponse,
  type EmployeeMyRotaShift,
  type EmployeeRequestItem,
  type EmployeeRequestTargetItem,
} from "@/lib/api-client";
import {
  clearEmployeeAccessToken,
  getEmployeeAccessToken,
} from "@/lib/employee-auth-token";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const requestLabels = {
  leave: "Leave",
  swap: "Swap",
  cover: "Cover",
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

function formatShift(shift: EmployeeMyRotaShift) {
  const start = new Date(shift.start_time);
  const end = new Date(shift.end_time);
  const date = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
  }).format(start);
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return `${date}, ${time.format(start)} - ${time.format(end)}`;
}

function friendlyRequestError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "REQUEST_DUPLICATE") {
      return "A pending request already exists for that item.";
    }
    if (error.code === "REQUEST_NOT_PENDING") {
      return "Only pending requests can be changed.";
    }
    return error.message;
  }
  return "Could not update requests. Please try again.";
}

export default function EmployeeRequestsPage() {
  const [weekStart, setWeekStart] = useState(() => getMondayWeekStart(new Date()));
  const [session, setSession] = useState<EmployeeMeResponse | null>(null);
  const [requests, setRequests] = useState<EmployeeRequestItem[]>([]);
  const [inboundRequests, setInboundRequests] = useState<EmployeeInboundRequestItem[]>([]);
  const [shifts, setShifts] = useState<EmployeeMyRotaShift[]>([]);
  const [targets, setTargets] = useState<EmployeeRequestTargetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingTargets, setIsLoadingTargets] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [leaveStart, setLeaveStart] = useState("");
  const [leaveEnd, setLeaveEnd] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [coverShiftId, setCoverShiftId] = useState("");
  const [coverReason, setCoverReason] = useState("");
  const [swapShiftId, setSwapShiftId] = useState("");
  const [swapTargetId, setSwapTargetId] = useState("");
  const [swapReason, setSwapReason] = useState("");
  const weekStartParam = formatDateParam(weekStart);
  const weekEnd = addDays(weekStart, 6);

  useEffect(() => {
    const token = getEmployeeAccessToken();
    if (!token) {
      setIsLoading(false);
      setSession(null);
      setRequests([]);
      setShifts([]);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    async function loadRequests(accessToken: string) {
      try {
        const [employeeSession, requestList, rota] = await Promise.all([
          getCurrentEmployeeSession(accessToken),
          getEmployeeRequests(accessToken),
          getEmployeeMyRota(accessToken, weekStartParam),
        ]);
        const inboundList = await getEmployeeInboundRequests(accessToken);
        if (isMounted) {
          setSession(employeeSession);
          setRequests(requestList.items);
          setInboundRequests(inboundList.items);
          setShifts(rota.shifts);
          setCoverShiftId(rota.shifts[0]?.id ?? "");
          setSwapShiftId(rota.shifts[0]?.id ?? "");
        }
      } catch {
        if (isMounted) {
          clearEmployeeAccessToken();
          setSession(null);
          setRequests([]);
          setInboundRequests([]);
          setShifts([]);
          setTargets([]);
          setError("Could not load your requests. Please sign in again.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadRequests(token);

    return () => {
      isMounted = false;
    };
  }, [weekStartParam]);

  useEffect(() => {
    const token = getEmployeeAccessToken();
    if (!token || !swapShiftId) {
      setTargets([]);
      setSwapTargetId("");
      return;
    }

    let isMounted = true;
    setIsLoadingTargets(true);

    async function loadTargets(accessToken: string) {
      try {
        const targetList = await getEmployeeRequestTargets(accessToken, {
          request_type: "swap",
          shift_id: swapShiftId,
        });
        if (isMounted) {
          setTargets(targetList.items);
          setSwapTargetId((current) =>
            targetList.items.some((target) => target.employee_account_id === current)
              ? current
              : targetList.items[0]?.employee_account_id ?? "",
          );
        }
      } catch {
        if (isMounted) {
          setTargets([]);
          setSwapTargetId("");
        }
      } finally {
        if (isMounted) {
          setIsLoadingTargets(false);
        }
      }
    }

    loadTargets(token);

    return () => {
      isMounted = false;
    };
  }, [swapShiftId]);

  async function submitLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getEmployeeAccessToken();
    if (!token) return;

    setIsSaving(true);
    setFormError(null);
    try {
      const created = await createEmployeeRequest(token, {
        request_type: "leave",
        start_date: leaveStart,
        end_date: leaveEnd,
        reason: leaveReason.trim(),
      });
      setRequests((current) => [created, ...current]);
      setLeaveReason("");
    } catch (caughtError) {
      setFormError(friendlyRequestError(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function submitCover(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getEmployeeAccessToken();
    if (!token) return;

    setIsSaving(true);
    setFormError(null);
    try {
      const created = await createEmployeeRequest(token, {
        request_type: "cover",
        shift_id: coverShiftId,
        reason: coverReason.trim(),
      });
      setRequests((current) => [created, ...current]);
      setCoverReason("");
    } catch (caughtError) {
      setFormError(friendlyRequestError(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function submitSwap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getEmployeeAccessToken();
    if (!token) return;

    setIsSaving(true);
    setFormError(null);
    try {
      const created = await createEmployeeRequest(token, {
        request_type: "swap",
        shift_id: swapShiftId,
        target_employee_account_id: swapTargetId,
        reason: swapReason.trim(),
      });
      setRequests((current) => [created, ...current]);
      setSwapReason("");
    } catch (caughtError) {
      setFormError(friendlyRequestError(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function cancelRequest(requestId: string) {
    const token = getEmployeeAccessToken();
    if (!token) return;

    setFormError(null);
    try {
      const cancelled = await cancelEmployeeRequest(token, requestId);
      setRequests((current) =>
        current.map((request) => (request.id === requestId ? cancelled : request)),
      );
    } catch (caughtError) {
      setFormError(friendlyRequestError(caughtError));
    }
  }

  async function decideInboundRequest(
    requestId: string,
    decision: "accept" | "decline",
  ) {
    const token = getEmployeeAccessToken();
    if (!token) return;

    setFormError(null);
    try {
      const result =
        decision === "accept"
          ? await acceptEmployeeInboundRequest(token, requestId)
          : await declineEmployeeInboundRequest(token, requestId);
      setInboundRequests((current) =>
        current.map((request) =>
          request.id === requestId ? { ...request, status: result.status } : request,
        ),
      );
      setRequests((current) =>
        current.map((request) =>
          request.id === requestId ? { ...request, status: result.status } : request,
        ),
      );
      setFormError(result.message);
    } catch (caughtError) {
      setFormError(friendlyRequestError(caughtError));
    }
  }

  if (!isLoading && !session) {
    return (
      <main className="min-h-screen bg-slate-100 px-4 py-10">
        <div className="mx-auto max-w-md">
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-6">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
                Requests
              </h1>
              <p className="text-sm leading-6 text-slate-500">
                Sign in to manage your requests.
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
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
              Employee Portal
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              Requests
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {session ? `${session.display_name} at site ${session.site_id}` : "Loading..."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/employee">My rota</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/employee/availability">Availability</Link>
            </Button>
          </div>
        </div>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Own Published Shifts</CardTitle>
                <p className="mt-1 text-sm text-slate-500">
                  {formatDisplayDate(weekStart)} - {formatDisplayDate(weekEnd)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => setWeekStart(addDays(weekStart, -7))}>
                  Previous
                </Button>
                <Button type="button" variant="outline" onClick={() => setWeekStart(getMondayWeekStart(new Date()))}>
                  This week
                </Button>
                <Button type="button" variant="outline" onClick={() => setWeekStart(addDays(weekStart, 7))}>
                  Next
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-3">
            <form className="space-y-4" onSubmit={submitLeave}>
              <h2 className="text-base font-semibold text-slate-950">Leave request</h2>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="leave-start">
                    Start
                  </label>
                  <input
                    id="leave-start"
                    type="date"
                    value={leaveStart}
                    onChange={(event) => setLeaveStart(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700" htmlFor="leave-end">
                    End
                  </label>
                  <input
                    id="leave-end"
                    type="date"
                    value={leaveEnd}
                    onChange={(event) => setLeaveEnd(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    required
                  />
                </div>
              </div>
              <textarea
                value={leaveReason}
                maxLength={500}
                onChange={(event) => setLeaveReason(event.target.value)}
                placeholder="Reason"
                className="min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              />
              <Button type="submit" disabled={isSaving} className="w-full">
                Submit leave
              </Button>
            </form>

            <form className="space-y-4" onSubmit={submitCover}>
              <h2 className="text-base font-semibold text-slate-950">Cover request</h2>
              <select
                value={coverShiftId}
                onChange={(event) => setCoverShiftId(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              >
                {shifts.length === 0 ? (
                  <option value="">No published shifts this week</option>
                ) : (
                  shifts.map((shift) => (
                    <option key={shift.id} value={shift.id}>
                      {formatShift(shift)}
                    </option>
                  ))
                )}
              </select>
              <textarea
                value={coverReason}
                maxLength={500}
                onChange={(event) => setCoverReason(event.target.value)}
                placeholder="Reason"
                className="min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              />
              <Button type="submit" disabled={isSaving || shifts.length === 0} className="w-full">
                Submit cover
              </Button>
            </form>

            <form className="space-y-4" onSubmit={submitSwap}>
              <h2 className="text-base font-semibold text-slate-950">Swap request</h2>
              <select
                value={swapShiftId}
                onChange={(event) => setSwapShiftId(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              >
                {shifts.length === 0 ? (
                  <option value="">No published shifts this week</option>
                ) : (
                  shifts.map((shift) => (
                    <option key={shift.id} value={shift.id}>
                      {formatShift(shift)}
                    </option>
                  ))
                )}
              </select>
              <select
                value={swapTargetId}
                onChange={(event) => setSwapTargetId(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
                disabled={isLoadingTargets || targets.length === 0}
              >
                {isLoadingTargets ? (
                  <option value="">Loading co-workers...</option>
                ) : targets.length === 0 ? (
                  <option value="">No same-site co-workers available</option>
                ) : (
                  targets.map((target) => (
                    <option key={target.employee_account_id} value={target.employee_account_id}>
                      {target.display_name}
                      {target.role_labels.length ? ` (${target.role_labels.join(", ")})` : ""}
                    </option>
                  ))
                )}
              </select>
              <textarea
                value={swapReason}
                maxLength={500}
                onChange={(event) => setSwapReason(event.target.value)}
                placeholder="Reason"
                className="min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                required
              />
              <Button
                type="submit"
                disabled={isSaving || shifts.length === 0 || targets.length === 0}
                className="w-full"
              >
                Submit swap
              </Button>
            </form>
          </CardContent>
        </Card>

        {formError ? (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {formError}
          </p>
        ) : null}

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle>My requests</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                Loading requests...
              </p>
            ) : requests.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
                No requests yet.
              </p>
            ) : (
              <div className="space-y-3">
                {requests.map((request) => (
                  <div
                    key={request.id}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-slate-950">
                          {requestLabels[request.request_type]} · {request.status}
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          {request.start_date
                            ? `${formatDisplayDate(request.start_date)} - ${formatDisplayDate(request.end_date ?? request.start_date)}`
                            : request.shift_id
                              ? `Shift ${request.shift_id}`
                              : "Request"}
                        </p>
                        {request.reason ? (
                          <p className="mt-2 text-sm text-slate-500">{request.reason}</p>
                        ) : null}
                      </div>
                      {request.status === "pending" ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => cancelRequest(request.id)}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle>Inbound requests</CardTitle>
            <p className="text-sm text-slate-500">
              Accepting does not change the rota. A manager must still approve before any rota changes happen.
            </p>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                Loading inbound requests...
              </p>
            ) : inboundRequests.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
                No inbound requests.
              </p>
            ) : (
              <div className="space-y-3">
                {inboundRequests.map((request) => (
                  <div
                    key={request.id}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-slate-950">
                          {requestLabels[request.request_type]} from{" "}
                          {request.requester_display_name ?? "co-worker"} · {request.status}
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          {request.shift
                            ? `${formatShift({
                                id: request.shift.id,
                                start_time: request.shift.start_time,
                                end_time: request.shift.end_time,
                                role_required: request.shift.role_required,
                                status: request.status,
                              })}${request.shift.role_required ? ` · ${request.shift.role_required}` : ""}`
                            : "Shift details unavailable"}
                        </p>
                        {request.reason ? (
                          <p className="mt-2 text-sm text-slate-500">{request.reason}</p>
                        ) : null}
                      </div>
                      {request.status === "pending" ? (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            onClick={() => decideInboundRequest(request.id, "accept")}
                          >
                            Accept
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => decideInboundRequest(request.id, "decline")}
                          >
                            Decline
                          </Button>
                        </div>
                      ) : null}
                    </div>
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
