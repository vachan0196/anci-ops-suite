"use client";

import { Loader2, Search, UserPlus, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  listStaffDirectory,
  StaffDirectoryItem,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type StatusFilter = "all" | "active" | "inactive";

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

function normalise(value: string) {
  return value.trim().toLowerCase();
}

function getLocationName(profile: StaffDirectoryItem) {
  return profile.store_name ?? (profile.store_id ? "Unknown location" : "Unassigned");
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have access to the staff directory.";
    }

    return "Could not load staff. Please try again.";
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server. Please try again.";
  }

  return "Could not load staff. Please try again.";
}

export function StaffDirectory() {
  const router = useRouter();
  const [staff, setStaff] = useState<StaffDirectoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [storeFilter, setStoreFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    let isMounted = true;

    async function loadDirectory(accessToken: string) {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const staffRows = await listStaffDirectory(accessToken);

        if (isMounted) {
          setStaff(staffRows);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          router.replace("/admin/login");
          return;
        }

        if (isMounted) {
          setErrorMessage(getErrorMessage(error));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadDirectory(token);

    return () => {
      isMounted = false;
    };
  }, [router]);

  const locationOptions = useMemo(() => {
    const locations = new Map<string, string>();

    staff.forEach((profile) => {
      if (profile.store_id) {
        locations.set(profile.store_id, getLocationName(profile));
      }
    });

    return Array.from(locations, ([id, name]) => ({ id, name })).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [staff]);

  const filteredStaff = useMemo(() => {
    const query = normalise(searchQuery);

    return staff.filter((profile) => {
      const locationName = getLocationName(profile);
      const roleNames = profile.roles.join(" ");
      const searchableText = normalise(
        [
          profile.display_name,
          profile.email ?? "",
          profile.job_title ?? "",
          profile.phone ?? "",
          roleNames,
          locationName,
        ].join(" "),
      );

      const matchesSearch = !query || searchableText.includes(query);
      const matchesStore = storeFilter === "all" || profile.store_id === storeFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && profile.is_active !== false) ||
        (statusFilter === "inactive" && profile.is_active === false);

      return matchesSearch && matchesStore && matchesStatus;
    });
  }, [searchQuery, staff, statusFilter, storeFilter]);

  const totalStaff = staff.length;
  const activeStaff = staff.filter((profile) => profile.is_active !== false).length;
  const locationsWithStaff = new Set(
    staff.map((profile) => profile.store_id).filter(Boolean),
  ).size;

  if (isLoading) {
    return (
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="flex items-center gap-3 p-6 text-sm text-slate-600">
          <Loader2 className="size-4 animate-spin" />
          Loading staff...
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

  if (staff.length === 0) {
    return (
      <Card className="border-dashed border-slate-300 bg-white shadow-sm">
        <CardContent className="flex flex-col items-start gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex size-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
              <UserPlus className="size-5" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-slate-950">
              No staff added yet.
            </h3>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
              Create a location and add staff to get started.
            </p>
          </div>
          <Button type="button" onClick={() => router.push("/admin/sites/new")}>
            Add New Location
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <SummaryCard label="Total Staff" value={totalStaff} />
        <SummaryCard label="Active Staff" value={activeStaff} />
        <SummaryCard label="Locations With Staff" value={locationsWithStaff} />
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="space-y-4 p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[1fr_220px_180px]">
            <label className="relative block">
              <span className="sr-only">Search staff</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="pl-9"
                placeholder="Search name, role, phone, location"
              />
            </label>
            <label>
              <span className="sr-only">Filter by location</span>
              <select
                value={storeFilter}
                onChange={(event) => setStoreFilter(event.target.value)}
                className={selectClassName}
              >
                <option value="all">All locations</option>
                {locationOptions.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by status</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                className={selectClassName}
              >
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>

          {filteredStaff.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              No staff match the current filters.
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-slate-200">
              <div className="hidden grid-cols-[1.1fr_1.2fr_0.9fr_1.1fr_1fr_0.9fr_0.75fr_0.8fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-medium uppercase tracking-[0.12em] text-slate-400 xl:grid">
                <span>Name</span>
                <span>Email</span>
                <span>Job title</span>
                <span>Role(s)</span>
                <span>Location</span>
                <span>Phone</span>
                <span>Status</span>
                <span>Created</span>
              </div>

              <div className="divide-y divide-slate-200">
                {filteredStaff.map((profile) => {
                  const locationName = getLocationName(profile);
                  const roles = profile.roles;

                  return (
                    <article
                      key={profile.id}
                      className="grid gap-4 px-4 py-4 text-sm text-slate-600 xl:grid-cols-[1.1fr_1.2fr_0.9fr_1.1fr_1fr_0.9fr_0.75fr_0.8fr] xl:items-center xl:gap-3"
                    >
                      <div>
                        <button
                          type="button"
                          onClick={() =>
                            router.push(`/admin/staff/${encodeURIComponent(profile.id)}`)
                          }
                          className="text-left font-semibold text-slate-950 transition hover:text-blue-700"
                        >
                          {profile.display_name}
                        </button>
                        <p className="mt-1 text-xs text-slate-400 xl:hidden">
                          {locationName}
                        </p>
                      </div>
                      <DataCell label="Email">
                        <span className="break-words">{profile.email || "Not available"}</span>
                      </DataCell>
                      <DataCell label="Job title">
                        {profile.job_title || "Not set"}
                      </DataCell>
                      <DataCell label="Roles">
                        <div className="flex flex-wrap gap-1.5">
                          {roles.length > 0 ? (
                            roles.map((role) => (
                              <span
                                key={role}
                                className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium capitalize text-blue-700"
                              >
                                {role}
                              </span>
                            ))
                          ) : (
                            <span>No role</span>
                          )}
                        </div>
                      </DataCell>
                      <DataCell label="Location">{locationName}</DataCell>
                      <DataCell label="Phone">{profile.phone || "Not added"}</DataCell>
                      <DataCell label="Status">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                            profile.is_active !== false
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-500",
                          )}
                        >
                          {profile.is_active !== false ? "Active" : "Inactive"}
                        </span>
                      </DataCell>
                      <DataCell label="Created">
                        <div className="space-y-2">
                          <span>{formatDate(profile.created_at)}</span>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-3 text-xs"
                            onClick={() =>
                              router.push(`/admin/staff/${encodeURIComponent(profile.id)}`)
                            }
                          >
                            View profile
                          </Button>
                        </div>
                      </DataCell>
                    </article>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const selectClassName =
  "flex h-11 w-full rounded-xl border border-input bg-white px-3 py-2 text-sm ring-offset-background transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardContent className="flex items-center justify-between gap-4 p-5">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
        </div>
        <div className="flex size-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
          <Users className="size-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function DataCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[104px_1fr] gap-3 xl:block">
      <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400 xl:hidden">
        {label}
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
