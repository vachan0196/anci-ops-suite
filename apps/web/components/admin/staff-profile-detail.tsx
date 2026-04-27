"use client";

import { ArrowLeft, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import {
  ApiError,
  getStaffDirectoryItem,
  StaffDirectoryItem,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type StaffProfileDetailProps = {
  staffId: string;
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

function getLocationName(profile: StaffDirectoryItem) {
  return profile.store_name ?? (profile.store_id ? "Unknown location" : "Unassigned");
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have access to this staff profile.";
    }

    if (error.status >= 500) {
      return "Could not load staff profile. Please try again.";
    }

    return "Could not load staff profile. Please try again.";
  }

  if (error instanceof Error && error.message === "NETWORK_ERROR") {
    return "Unable to connect to server. Please try again.";
  }

  return "Could not load staff profile. Please try again.";
}

export function StaffProfileDetail({ staffId }: StaffProfileDetailProps) {
  const router = useRouter();
  const normalisedStaffId = staffId.trim();
  const [profile, setProfile] = useState<StaffDirectoryItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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
      setIsNotFound(false);

      if (!normalisedStaffId) {
        setProfile(null);
        setIsNotFound(true);
        setIsLoading(false);
        return;
      }

      try {
        const staffProfile = await getStaffDirectoryItem(accessToken, normalisedStaffId);

        if (isMounted) {
          if (staffProfile) {
            setProfile(staffProfile);
          } else {
            setProfile(null);
            setIsNotFound(true);
          }
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

    loadProfile(token);

    return () => {
      isMounted = false;
    };
  }, [normalisedStaffId, router]);

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

  const roles = profile.roles;
  const locationName = getLocationName(profile);

  return (
    <div className="space-y-5">
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
                {profile.job_title || "Job title not set"}
              </p>
            </div>
            <span
              className={cn(
                "inline-flex w-fit rounded-full px-3 py-1.5 text-sm font-medium",
                profile.is_active
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-slate-100 text-slate-500",
              )}
            >
              {profile.is_active ? "Active" : "Inactive"}
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DetailItem label="Email">{profile.email || "Not available"}</DetailItem>
            <DetailItem label="Phone">{profile.phone || "Not added"}</DetailItem>
            <DetailItem label="Location">{locationName}</DetailItem>
            <DetailItem label="Added">{formatDate(profile.created_at)}</DetailItem>
          </div>

          <section className="space-y-2">
            <p className="text-sm font-medium text-slate-700">Roles</p>
            <div className="flex flex-wrap gap-2">
              {roles.length > 0 ? (
                roles.map((role) => (
                  <span
                    key={role}
                    className="rounded-full bg-blue-50 px-3 py-1.5 text-sm font-medium capitalize text-blue-700"
                  >
                    {role}
                  </span>
                ))
              ) : (
                <span className="text-sm text-slate-500">No role</span>
              )}
            </div>
          </section>
        </CardContent>
      </Card>

      <Card className="border-blue-200 bg-blue-50 shadow-sm">
        <CardContent className="p-5 text-sm leading-6 text-blue-900">
          This is a basic read-only profile view. Additional staff management tools
          will be added in later controlled phases.
        </CardContent>
      </Card>
    </div>
  );
}

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
