"use client";

import {
  BarChart3,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Home,
  Loader2,
  Lock,
  MapPinned,
  Settings,
  UserRound,
  Users,
  Utensils,
  WalletCards,
  X,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  createShift,
  getCompanyProfile,
  getCurrentAdminSession,
  getSiteWeeklyRota,
  getStoreReadiness,
  listStaffDirectory,
  listStores,
  type StaffDirectoryItem,
  type Store,
  type StoreReadinessResponse,
  type WeeklyRotaShift,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CompanySetupForm } from "@/components/admin/company-setup-form";
import { SiteSetupForm } from "@/components/admin/site-setup-form";
import { StaffDirectory } from "@/components/admin/staff-directory";
import { StaffProfileDetail } from "@/components/admin/staff-profile-detail";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SessionState = {
  role: "owner" | "admin" | "manager";
  tenantId: string;
  userId: string;
  email: string;
};

type CurrentAuthMeResponse = {
  id?: unknown;
  email?: unknown;
  active_tenant_id?: unknown;
  active_tenant_role?: unknown;
};

type SetupKey = "hasCompany" | "hasSite" | "isOperationalReady";

type SetupCard = {
  key: SetupKey;
  title: string;
  description: string;
  cta: string;
  href: string;
  icon: typeof Building2;
  isBlocked: boolean;
  blockedText?: string;
};

type ReadinessStatus = "idle" | "loading" | "loaded" | "empty" | "error";

type AdminShellProps = {
  activePage?: "dashboard" | "company" | "site" | "staff" | "staffProfile" | "rota";
  staffId?: string;
};

type CreateShiftDraft = {
  dayIndex: string;
  startTime: string;
  endTime: string;
  assignedStaffUserId: string;
  roleRequired: string;
  notes: string;
};

type CreateShiftErrors = Partial<
  Record<"dayIndex" | "startTime" | "endTime", string>
>;

const setupNavItems = [
  {
    label: "Company Setup",
    icon: Building2,
  },
  {
    label: "Sites",
    icon: MapPinned,
  },
  {
    label: "Staff",
    icon: Users,
  },
];

const operationNavItems: Array<{
  label: string;
  icon: typeof Home;
  href?: string;
}> = [
  { label: "Rota", icon: CalendarDays, href: "/admin/rota" },
  { label: "Hot Food", icon: Utensils },
  { label: "Reports", icon: BarChart3 },
  { label: "Payroll & Compensation", icon: WalletCards },
  { label: "Employee Profile", icon: UserRound },
  { label: "Settings", icon: Settings },
];

const weekDayLabels = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const emptyCreateShiftDraft: CreateShiftDraft = {
  dayIndex: "",
  startTime: "",
  endTime: "",
  assignedStaffUserId: "",
  roleRequired: "",
  notes: "",
};

function isCurrentAuthMeResponse(response: CurrentAuthMeResponse): response is {
  id: string;
  email: string;
  active_tenant_id: string;
  active_tenant_role: SessionState["role"];
} {
  return (
    typeof response.id === "string" &&
    typeof response.email === "string" &&
    typeof response.active_tenant_id === "string" &&
    (response.active_tenant_role === "owner" ||
      response.active_tenant_role === "admin" ||
      response.active_tenant_role === "manager")
  );
}

function getInitials(email: string, fullName?: string) {
  if (fullName?.trim()) {
    return fullName
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  }

  return email.trim()[0]?.toUpperCase() || "A";
}

function getNextSetupHref(
  setupState: Record<SetupKey, boolean>,
  readiness: StoreReadinessResponse | null,
) {
  if (!setupState.hasCompany) {
    return "/admin/company";
  }

  if (!setupState.hasSite) {
    return "/admin/sites/new";
  }

  if (readiness && !readiness.opening_hours_configured) {
    return "/admin/sites/new";
  }

  if (readiness && !readiness.staff_configured) {
    return "/admin/staff";
  }

  return "/admin/sites/new";
}

function getReadinessErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "You do not have permission to view this site readiness.";
    }
  }

  return "Site readiness could not be loaded right now.";
}

function getMondayWeekStart(date: Date) {
  const weekStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const daysSinceMonday = (weekStart.getDay() + 6) % 7;
  weekStart.setDate(weekStart.getDate() - daysSinceMonday);
  weekStart.setHours(0, 0, 0, 0);
  return weekStart;
}

function addDays(date: Date, days: number) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + days);
  return nextDate;
}

function formatDisplayDate(date: Date) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatDateParam(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTimeRange(startTime: string, endTime: string) {
  const formatter = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return `${formatter.format(new Date(startTime))} - ${formatter.format(new Date(endTime))}`;
}

function getShiftDayIndex(shift: WeeklyRotaShift, weekStart: Date) {
  const shiftDate = new Date(shift.start_time);
  const shiftDay = new Date(
    shiftDate.getFullYear(),
    shiftDate.getMonth(),
    shiftDate.getDate(),
  );
  const weekStartDay = new Date(
    weekStart.getFullYear(),
    weekStart.getMonth(),
    weekStart.getDate(),
  );
  return Math.floor((shiftDay.getTime() - weekStartDay.getTime()) / 86_400_000);
}

function validateCreateShiftDraft(draft: CreateShiftDraft): CreateShiftErrors {
  const errors: CreateShiftErrors = {};

  if (!draft.dayIndex) {
    errors.dayIndex = "Choose a day for this shift.";
  }

  if (!draft.startTime) {
    errors.startTime = "Add a start time.";
  }

  if (!draft.endTime) {
    errors.endTime = "Add an end time.";
  }

  if (
    draft.startTime &&
    draft.endTime &&
    draft.endTime <= draft.startTime
  ) {
    errors.endTime = "End time must be after start time.";
  }

  return errors;
}

function buildShiftDateTime(weekStart: Date, dayIndex: string, timeValue: string) {
  const [hours, minutes] = timeValue.split(":").map(Number);
  const shiftDate = addDays(weekStart, Number(dayIndex));
  return new Date(
    Date.UTC(
      shiftDate.getFullYear(),
      shiftDate.getMonth(),
      shiftDate.getDate(),
      hours,
      minutes,
      0,
      0,
    ),
  ).toISOString();
}

export function AdminShell({ activePage = "dashboard", staffId }: AdminShellProps) {
  const router = useRouter();
  const [session, setSession] = useState<SessionState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [gateMessage, setGateMessage] = useState(false);
  const [comingNextMessage, setComingNextMessage] = useState<string | null>(null);
  const [hasCompanyProfile, setHasCompanyProfile] = useState(false);
  const [hasFirstSiteProfile, setHasFirstSiteProfile] = useState(false);
  const [firstActiveStore, setFirstActiveStore] = useState<Store | null>(null);
  const [storeReadiness, setStoreReadiness] = useState<StoreReadinessResponse | null>(
    null,
  );
  const [readinessStatus, setReadinessStatus] = useState<ReadinessStatus>("idle");
  const [readinessError, setReadinessError] = useState<string | null>(null);

  // Setup readiness is derived from backend company profile, stores, and store
  // readiness endpoints. localStorage setup state is not used as readiness truth.
  const setupState = {
    hasCompany: hasCompanyProfile,
    hasSite: hasFirstSiteProfile,
    isOperationalReady: Boolean(storeReadiness?.operational_ready),
  };

  const setupCards: SetupCard[] = [
    {
      key: "hasCompany",
      title: "Complete company setup",
      description: "Add your business details so your workspace is ready.",
      cta: setupState.hasCompany ? "Review company setup" : "Start company setup",
      href: "/admin/company",
      icon: Building2,
      isBlocked: false,
    },
    {
      key: "hasSite",
      title: "Create your first site",
      description: "Set up your first forecourt or store location.",
      cta: setupState.hasSite ? "Review site setup" : "Create site",
      href: "/admin/sites/new",
      icon: MapPinned,
      isBlocked: !setupState.hasCompany,
      blockedText: "Complete company setup first.",
    },
  ];

  const completedSetupCount = Object.values(setupState).filter(Boolean).length;
  const setupProgress = (completedSetupCount / 3) * 100;
  const nextSetupHref = getNextSetupHref(setupState, storeReadiness);

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      router.replace("/admin/login");
      return;
    }

    let isMounted = true;

    async function loadSession(accessToken: string) {
      try {
        const response = await getCurrentAdminSession(accessToken);

        // Current backend /auth/me returns id/email/active_tenant_id/active_tenant_role.
        // Reconcile this with the newer API Contracts PRD shape later.
        if (!isCurrentAuthMeResponse(response)) {
          throw new Error("Invalid auth session");
        }

        if (isMounted) {
          setSession({
            role: response.active_tenant_role,
            tenantId: response.active_tenant_id,
            userId: response.id,
            email: response.email,
          });
        }

        try {
          const [companyProfile, stores] = await Promise.all([
            getCompanyProfile(accessToken),
            listStores(accessToken),
          ]);
          const activeStore = stores.find((store) => store.is_active !== false) ?? null;

          if (isMounted) {
            setHasCompanyProfile(companyProfile.company_setup_completed);
            setHasFirstSiteProfile(Boolean(activeStore));
            setFirstActiveStore(activeStore);
            setStoreReadiness(null);
            setReadinessError(null);
            setReadinessStatus(activeStore ? "loading" : "empty");
          }

          if (activeStore) {
            try {
              const readiness = await getStoreReadiness(accessToken, activeStore.id);

              if (isMounted) {
                setStoreReadiness(readiness);
                setReadinessStatus("loaded");
              }
            } catch (error) {
              if (isMounted) {
                setStoreReadiness(null);
                setReadinessError(getReadinessErrorMessage(error));
                setReadinessStatus("error");
              }
            }
          }
        } catch {
          if (isMounted) {
            setHasCompanyProfile(false);
            setHasFirstSiteProfile(false);
            setFirstActiveStore(null);
            setStoreReadiness(null);
            setReadinessError("Setup status could not be loaded right now.");
            setReadinessStatus("error");
          }
        }
      } catch {
        clearAccessToken();
        router.replace("/admin/login");
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSession(token);

    return () => {
      isMounted = false;
    };
  }, [router]);

  function showOperationGate() {
    setComingNextMessage(null);

    if (setupState.isOperationalReady) {
      setGateMessage(false);
      setComingNextMessage("This module will be built next.");
      return;
    }

    setGateMessage(true);
  }

  function showSetupComingNext(title: string) {
    setGateMessage(false);
    setComingNextMessage(`${title} will be built next.`);
  }

  function handleSetupNavigation(label: string) {
    setGateMessage(false);

    if (label === "Company Setup") {
      router.push("/admin/company");
      return;
    }

    if (label === "Sites") {
      if (!setupState.hasCompany) {
        setComingNextMessage("Complete company setup before creating your first site.");
        return;
      }

      router.push("/admin/sites/new");
      return;
    }

    if (!setupState.hasSite) {
      setComingNextMessage("Create your first site before opening the staff directory.");
      return;
    }

    router.push("/admin/staff");
  }

  if (isLoading || !session) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm text-slate-600 shadow-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading admin workspace...
        </div>
      </main>
    );
  }

  const avatarInitials = getInitials(session.email);
  const displayRole = session.role === "admin" ? "Admin" : session.role;
  const pageTitle =
    activePage === "company"
      ? "Company Setup"
      : activePage === "site"
        ? "Add New Location"
        : activePage === "staff"
          ? "Staff"
          : activePage === "staffProfile"
            ? "Staff Profile"
            : activePage === "rota"
              ? "Rota"
              : "Dashboard";

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[260px_1fr]">
        <aside className="hidden border-r border-slate-200 bg-slate-950 text-slate-100 lg:flex lg:flex-col">
          <div className="border-b border-white/10 px-6 py-6">
            <p className="text-lg font-semibold">ForecourtOS</p>
            <p className="mt-1 text-sm text-slate-400">Admin Portal</p>
          </div>
          <nav className="flex-1 space-y-7 px-4 py-6">
            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Setup
              </p>
              <div className="mt-3 space-y-1">
                {setupNavItems.map(({ label, icon: Icon }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => handleSetupNavigation(label)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition",
                      (activePage === "company" && label === "Company Setup") ||
                        (activePage === "site" && label === "Sites") ||
                        ((activePage === "staff" || activePage === "staffProfile") &&
                          label === "Staff") ||
                        (activePage === "dashboard" && label === "Company Setup")
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-300 hover:bg-white/5 hover:text-white",
                    )}
                  >
                    <Icon className="size-4" />
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Operations
              </p>
              <div className="mt-3 space-y-1">
                {operationNavItems.map(({ label, icon: Icon, href }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      if (href) {
                        setGateMessage(false);
                        setComingNextMessage(null);
                        router.push(href);
                        return;
                      }

                      showOperationGate();
                    }}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition",
                      activePage === "rota" && href === "/admin/rota"
                        ? "bg-blue-600 text-white shadow-sm"
                        : href
                          ? "text-slate-300 hover:bg-white/5 hover:text-white"
                          : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <Icon className="size-4 shrink-0" />
                      <span className="truncate">{label}</span>
                    </span>
                    {href ? null : <Lock className="size-3.5 shrink-0" />}
                  </button>
                ))}
              </div>
            </div>
          </nav>
        </aside>

        <div className="flex min-h-screen flex-col">
          <header className="border-b border-slate-200 bg-white">
            <div className="flex items-center justify-between px-5 py-4 sm:px-8">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                  ForecourtOS Admin
                </p>
                <h1 className="mt-1 text-2xl font-semibold">{pageTitle}</h1>
              </div>
              <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white py-1 pl-1 pr-3 shadow-sm">
                <div className="flex size-10 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
                  {avatarInitials}
                </div>
                <div className="hidden text-left sm:block">
                  <p className="text-sm font-medium capitalize text-slate-800">
                    {displayRole}
                  </p>
                  <p className="max-w-44 truncate text-xs text-slate-500">
                    {session.email}
                  </p>
                </div>
                <ChevronDown className="size-4 text-slate-400" />
              </div>
            </div>
          </header>

          <section className="flex-1 px-5 py-6 sm:px-8 sm:py-8">
            {gateMessage ? (
              <Card className="mb-6 border-blue-200 bg-blue-50 shadow-sm">
                <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">
                      Finish setup to unlock this feature
                    </h2>
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                      Complete company details and create your first site before using
                      this module. Opening hours and staff readiness are checked from
                      the backend before operations unlock.
                    </p>
                  </div>
                  <Button type="button" onClick={() => router.push(nextSetupHref)}>
                    Continue setup
                  </Button>
                </CardContent>
              </Card>
            ) : null}

            {comingNextMessage ? (
              <Card className="mb-6 border-slate-200 bg-white shadow-sm">
                <CardContent className="p-4 text-sm text-slate-600">
                  {comingNextMessage}
                </CardContent>
              </Card>
            ) : null}

            {activePage === "dashboard" ? (
              <DashboardContent
                completedSetupCount={completedSetupCount}
                setupProgress={setupProgress}
                setupCards={setupCards}
                firstActiveStore={firstActiveStore}
                readiness={storeReadiness}
                readinessStatus={readinessStatus}
                readinessError={readinessError}
                onContinueSetup={() => router.push(nextSetupHref)}
                onOpenCompany={() => router.push("/admin/company")}
                onOpenSite={() => router.push("/admin/sites/new")}
                onShowSiteGate={() => {
                  setGateMessage(false);
                  setComingNextMessage(
                    "Complete company setup before creating your first site.",
                  );
                }}
                onShowComingNext={showSetupComingNext}
              />
            ) : activePage === "company" ? (
              <CompanyContent />
            ) : activePage === "site" ? (
              <SiteContent />
            ) : activePage === "staff" ? (
              <StaffContent />
            ) : activePage === "rota" ? (
              <RotaContent
                store={firstActiveStore}
                readiness={storeReadiness}
                readinessStatus={readinessStatus}
                readinessError={readinessError}
              />
            ) : (
              <StaffProfileContent staffId={staffId ?? ""} />
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

function DashboardContent({
  completedSetupCount,
  setupProgress,
  setupCards,
  firstActiveStore,
  readiness,
  readinessStatus,
  readinessError,
  onContinueSetup,
  onOpenCompany,
  onOpenSite,
  onShowSiteGate,
  onShowComingNext,
}: {
  completedSetupCount: number;
  setupProgress: number;
  setupCards: SetupCard[];
  firstActiveStore: Store | null;
  readiness: StoreReadinessResponse | null;
  readinessStatus: ReadinessStatus;
  readinessError: string | null;
  onContinueSetup: () => void;
  onOpenCompany: () => void;
  onOpenSite: () => void;
  onShowSiteGate: () => void;
  onShowComingNext: (title: string) => void;
}) {
  return (
    <>
      <div className="mb-6 rounded-3xl bg-blue-600 px-6 py-6 text-white shadow-[0_18px_40px_rgba(37,99,235,0.18)]">
              <p className="text-sm text-blue-100">Welcome back</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                Let&apos;s get your business set up in a few quick steps.
              </h2>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-blue-50">
                Complete setup to unlock rota, hot food, reports, payroll, and staff
                operations across your ForecourtOS workspace.
              </p>
            </div>

            <Card className="mb-6 border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-500">Setup progress</p>
                    <h2 className="mt-1 text-xl font-semibold text-slate-950">
                      {completedSetupCount} of 3 completed
                    </h2>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onContinueSetup}
                  >
                    Continue setup
                  </Button>
                </div>
                <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-blue-600 transition-all"
                    style={{ width: `${setupProgress}%` }}
                  />
                </div>
                <div className="mt-4 grid gap-2 text-sm text-slate-500 sm:grid-cols-3">
                  <span>Company details</span>
                  <span>First site</span>
                  <span>Site readiness</span>
                </div>
              </CardContent>
            </Card>

            <StoreReadinessCard
              store={firstActiveStore}
              readiness={readiness}
              status={readinessStatus}
              error={readinessError}
            />

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {setupCards.map(
                ({ key, title, description, cta, href, icon: Icon, isBlocked, blockedText }) => (
                  <Card key={key} className="border-slate-200 shadow-sm">
                    <CardHeader className="space-y-4">
                      <div
                        className={cn(
                          "flex size-11 items-center justify-center rounded-2xl",
                          !isBlocked && cta.startsWith("Review")
                            ? "bg-emerald-50 text-emerald-600"
                            : isBlocked
                              ? "bg-slate-100 text-slate-400"
                              : "bg-blue-50 text-blue-600",
                        )}
                      >
                        {!isBlocked && cta.startsWith("Review") ? (
                          <CheckCircle2 className="size-5" />
                        ) : (
                          <Icon className="size-5" />
                        )}
                      </div>
                      <div>
                        <CardTitle className="text-lg">{title}</CardTitle>
                        {!isBlocked && cta.startsWith("Review") ? (
                          <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-emerald-600">
                            Completed
                          </p>
                        ) : null}
                        {isBlocked && blockedText ? (
                          <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
                            {blockedText}
                          </p>
                        ) : null}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm leading-6 text-slate-500">{description}</p>
                      <Button
                        type="button"
                        className="mt-5 w-full"
                        variant={isBlocked ? "outline" : "default"}
                        onClick={() =>
                          href === "/admin/company"
                            ? onOpenCompany()
                            : isBlocked
                              ? onShowSiteGate()
                              : href === "/admin/sites/new"
                                ? onOpenSite()
                                : onShowComingNext(`${title} (${href})`)
                        }
                      >
                        {cta}
                      </Button>
                    </CardContent>
                  </Card>
                ),
              )}
            </div>
    </>
  );
}

function StoreReadinessCard({
  store,
  readiness,
  status,
  error,
}: {
  store: Store | null;
  readiness: StoreReadinessResponse | null;
  status: ReadinessStatus;
  error: string | null;
}) {
  const siteDetailsCompleted = Boolean(store);
  const openingHoursConfigured = Boolean(readiness?.opening_hours_configured);
  const staffConfigured = Boolean(readiness?.staff_configured);
  const operationalReady = Boolean(readiness?.operational_ready);

  return (
    <Card className="mb-6 border-slate-200 shadow-sm">
      <CardContent className="p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Site readiness</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">
              {store ? store.name : "No site selected"}
            </h2>
          </div>
          <span
            className={cn(
              "inline-flex w-fit rounded-full px-3 py-1 text-xs font-medium",
              operationalReady
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700",
            )}
          >
            {operationalReady ? "Operational ready" : "Not operational yet"}
          </span>
        </div>

        {status === "loading" ? (
          <div className="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <Loader2 className="size-4 animate-spin" />
            Loading site readiness...
          </div>
        ) : null}

        {status === "empty" ? (
          <p className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Create your first site to start tracking readiness.
          </p>
        ) : null}

        {status === "error" ? (
          <p className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error ?? "Site readiness could not be loaded right now."}
          </p>
        ) : null}

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <ReadinessItem
            label="Site details completed"
            isComplete={siteDetailsCompleted}
            isUnavailable={status === "loading" || status === "error"}
          />
          <ReadinessItem
            label="Opening hours configured"
            isComplete={openingHoursConfigured}
            isUnavailable={!store || status === "loading" || status === "error"}
          />
          <ReadinessItem
            label="Staff added"
            isComplete={staffConfigured}
            isUnavailable={!store || status === "loading" || status === "error"}
          />
          <ReadinessItem
            label="Operational ready"
            isComplete={operationalReady}
            isUnavailable={!store || status === "loading" || status === "error"}
          />
        </div>

        {status === "loaded" && readiness && !readiness.operational_ready ? (
          <p className="mt-4 text-sm leading-6 text-slate-500">
            Missing items:{" "}
            {[
              readiness.opening_hours_configured ? null : "opening hours",
              readiness.staff_configured ? null : "staff member",
            ]
              .filter(Boolean)
              .join(", ")}
            .
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ReadinessItem({
  label,
  isComplete,
  isUnavailable,
}: {
  label: string;
  isComplete: boolean;
  isUnavailable: boolean;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm">
      {isComplete ? (
        <CheckCircle2 className="size-5 shrink-0 text-emerald-600" />
      ) : (
        <XCircle
          className={cn(
            "size-5 shrink-0",
            isUnavailable ? "text-slate-300" : "text-red-500",
          )}
        />
      )}
      <span className={cn("font-medium", isUnavailable ? "text-slate-400" : "text-slate-700")}>
        {label}
      </span>
    </div>
  );
}

function CompanyContent() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
          Setup
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
          Company Setup
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Add the basic business details needed to prepare your ForecourtOS workspace.
        </p>
      </div>

      <CompanySetupForm />
    </div>
  );
}

function SiteContent() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
          Setup
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
          Add New Location
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Set up a new site, assign a manager, and optionally add initial staff
          members.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          You can create the site first and add more staff later.
        </p>
      </div>

      <SiteSetupForm />
    </div>
  );
}

function StaffContent() {
  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
          Operations
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
          Staff
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Manage staff added to your locations.
        </p>
      </div>

      <StaffDirectory />
    </div>
  );
}

function RotaContent({
  store,
  readiness,
  readinessStatus,
  readinessError,
}: {
  store: Store | null;
  readiness: StoreReadinessResponse | null;
  readinessStatus: ReadinessStatus;
  readinessError: string | null;
}) {
  const [weekStart, setWeekStart] = useState(() => getMondayWeekStart(new Date()));
  const [activeStaffCount, setActiveStaffCount] = useState<number | null>(null);
  const [staffDirectory, setStaffDirectory] = useState<StaffDirectoryItem[]>([]);
  const [isLoadingStaffSummary, setIsLoadingStaffSummary] = useState(false);
  const [staffSummaryError, setStaffSummaryError] = useState<string | null>(null);
  const [weeklyShifts, setWeeklyShifts] = useState<WeeklyRotaShift[]>([]);
  const [isLoadingRota, setIsLoadingRota] = useState(false);
  const [rotaError, setRotaError] = useState<string | null>(null);
  const [isCreateShiftOpen, setIsCreateShiftOpen] = useState(false);
  const [createShiftDraft, setCreateShiftDraft] = useState<CreateShiftDraft>(
    emptyCreateShiftDraft,
  );
  const [touchedCreateShiftFields, setTouchedCreateShiftFields] = useState<
    Partial<Record<keyof CreateShiftDraft, boolean>>
  >({});
  const [isSubmittingShift, setIsSubmittingShift] = useState(false);
  const [createShiftError, setCreateShiftError] = useState<string | null>(null);
  const [createShiftSuccess, setCreateShiftSuccess] = useState<string | null>(null);
  const weekEnd = addDays(weekStart, 6);
  const weekStartParam = formatDateParam(weekStart);
  const weekDays = weekDayLabels.map((label, index) => ({
    label,
    date: addDays(weekStart, index),
  }));
  const isReadinessLoading = readinessStatus === "loading" || readinessStatus === "idle";
  const isReadinessError = readinessStatus === "error";
  const isOperationalReady = Boolean(readiness?.operational_ready);
  const canCreateShift = Boolean(store && isOperationalReady);
  const staffByUserId = new Map(staffDirectory.map((staff) => [staff.user_id, staff]));
  const activeStaffOptions = staffDirectory
    .filter((staff) => staff.is_active !== false)
    .sort((first, second) => first.display_name.localeCompare(second.display_name));
  const createShiftErrors = validateCreateShiftDraft(createShiftDraft);
  const isCreateShiftValid = Object.keys(createShiftErrors).length === 0;
  const shiftsByDay = weekDays.map((_, index) => {
    const dayShifts = weeklyShifts.filter(
      (shift) => getShiftDayIndex(shift, weekStart) === index,
    );

    return {
      open: dayShifts
        .filter((shift) => !shift.assigned_employee_account_id)
        .sort((first, second) => first.start_time.localeCompare(second.start_time)),
      assigned: dayShifts
        .filter((shift) => Boolean(shift.assigned_employee_account_id))
        .sort((first, second) => first.start_time.localeCompare(second.start_time)),
    };
  });

  useEffect(() => {
    if (!store) {
      setActiveStaffCount(null);
      setStaffDirectory([]);
      setStaffSummaryError(null);
      setIsLoadingStaffSummary(false);
      return;
    }

    const selectedStore = store;
    const token = getAccessToken();

    if (!token) {
      return;
    }

    let isMounted = true;
    setIsLoadingStaffSummary(true);
    setStaffSummaryError(null);

    async function loadStaffSummary(accessToken: string) {
      try {
        const staff = await listStaffDirectory(accessToken, {
          store_id: selectedStore.id,
        });

        if (isMounted) {
          setStaffDirectory(staff);
          setActiveStaffCount(staff.filter((item) => item.is_active).length);
        }
      } catch {
        if (isMounted) {
          setStaffDirectory([]);
          setActiveStaffCount(null);
          setStaffSummaryError("Staff summary could not be loaded right now.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingStaffSummary(false);
        }
      }
    }

    loadStaffSummary(token);

    return () => {
      isMounted = false;
    };
  }, [store]);

  useEffect(() => {
    if (!store) {
      setWeeklyShifts([]);
      setRotaError(null);
      setIsLoadingRota(false);
      return;
    }

    const selectedStore = store;
    const token = getAccessToken();

    if (!token) {
      return;
    }

    let isMounted = true;
    setIsLoadingRota(true);
    setRotaError(null);

    async function loadWeeklyRota(accessToken: string) {
      try {
        const rota = await getSiteWeeklyRota(
          accessToken,
          selectedStore.id,
          weekStartParam,
        );

        if (isMounted) {
          setWeeklyShifts(rota.shifts);
        }
      } catch {
        if (isMounted) {
          setWeeklyShifts([]);
          setRotaError("Weekly rota could not be loaded right now.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingRota(false);
        }
      }
    }

    loadWeeklyRota(token);

    return () => {
      isMounted = false;
    };
  }, [store, weekStartParam]);

  function moveWeek(delta: number) {
    setWeekStart((current) => addDays(current, delta * 7));
  }

  function resetToCurrentWeek() {
    setWeekStart(getMondayWeekStart(new Date()));
  }

  function updateCreateShiftField<Key extends keyof CreateShiftDraft>(
    key: Key,
    value: CreateShiftDraft[Key],
  ) {
    setCreateShiftDraft((current) => ({
      ...current,
      [key]: value,
    }));
    setTouchedCreateShiftFields((current) => ({
      ...current,
      [key]: true,
    }));
  }

  function openCreateShiftModal() {
    if (!canCreateShift) {
      return;
    }

    setCreateShiftDraft(emptyCreateShiftDraft);
    setTouchedCreateShiftFields({});
    setCreateShiftError(null);
    setIsCreateShiftOpen(true);
  }

  function closeCreateShiftModal() {
    setIsCreateShiftOpen(false);
  }

  async function submitCreateShift() {
    if (!store || !isCreateShiftValid || isSubmittingShift) {
      setTouchedCreateShiftFields({
        dayIndex: true,
        startTime: true,
        endTime: true,
      });
      return;
    }

    const token = getAccessToken();

    if (!token) {
      setCreateShiftError("Could not create shift. Please sign in and try again.");
      return;
    }

    setIsSubmittingShift(true);
    setCreateShiftError(null);
    setCreateShiftSuccess(null);

    try {
      await createShift(token, store.id, {
        assigned_employee_account_id:
          createShiftDraft.assignedStaffUserId.trim() || null,
        role_required: createShiftDraft.roleRequired.trim() || null,
        start_time: buildShiftDateTime(
          weekStart,
          createShiftDraft.dayIndex,
          createShiftDraft.startTime,
        ),
        end_time: buildShiftDateTime(
          weekStart,
          createShiftDraft.dayIndex,
          createShiftDraft.endTime,
        ),
      });

      const rota = await getSiteWeeklyRota(token, store.id, weekStartParam);
      setWeeklyShifts(rota.shifts);
      setCreateShiftDraft(emptyCreateShiftDraft);
      setTouchedCreateShiftFields({});
      setIsCreateShiftOpen(false);
      setCreateShiftSuccess("Draft shift created.");
    } catch {
      setCreateShiftError(
        "Could not create shift. Please check the details and try again.",
      );
    } finally {
      setIsSubmittingShift(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
            Operations
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            Rota
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Build and manage weekly rota for the selected site.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
              Selected site
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {store ? store.name : "No site selected"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
              Week
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {formatDisplayDate(weekStart)} - {formatDisplayDate(weekEnd)}
            </p>
          </div>
        </div>
      </div>

      <Card className="mb-6 border-slate-200 shadow-sm">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => moveWeek(-1)}>
              Previous week
            </Button>
            <Button type="button" variant="outline" onClick={resetToCurrentWeek}>
              Current week
            </Button>
            <Button type="button" variant="outline" onClick={() => moveWeek(1)}>
              Next week
            </Button>
          </div>
          <p className="text-sm text-slate-500">Weeks start on Monday.</p>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Site readiness</CardTitle>
            </CardHeader>
            <CardContent>
              {isReadinessLoading ? (
                <div className="mb-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  <Loader2 className="size-4 animate-spin" />
                  Loading site readiness...
                </div>
              ) : null}

              {!store ? (
                <p className="mb-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  Create your first site before building a rota.
                </p>
              ) : null}

              {isReadinessError ? (
                <p className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {readinessError ?? "Rota readiness could not be loaded right now."}
                </p>
              ) : null}

              <div className="grid gap-3 md:grid-cols-2">
                <ReadinessItem
                  label="Site details completed"
                  isComplete={Boolean(store)}
                  isUnavailable={isReadinessLoading || isReadinessError}
                />
                <ReadinessItem
                  label="Opening hours configured"
                  isComplete={Boolean(readiness?.opening_hours_configured)}
                  isUnavailable={!store || isReadinessLoading || isReadinessError}
                />
                <ReadinessItem
                  label="Staff added"
                  isComplete={Boolean(readiness?.staff_configured)}
                  isUnavailable={!store || isReadinessLoading || isReadinessError}
                />
                <ReadinessItem
                  label="Operational ready"
                  isComplete={isOperationalReady}
                  isUnavailable={!store || isReadinessLoading || isReadinessError}
                />
              </div>

              {store && readiness && !readiness.operational_ready ? (
                <p className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-800">
                  Rota setup is blocked until this site is operationally ready. Missing
                  items:{" "}
                  {[
                    readiness.opening_hours_configured ? null : "opening hours",
                    readiness.staff_configured ? null : "staff member",
                  ]
                    .filter(Boolean)
                    .join(", ")}
                  .
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="text-lg">Weekly rota</CardTitle>
                <p className="mt-1 text-sm text-slate-500">
                  {formatDisplayDate(weekStart)} - {formatDisplayDate(weekEnd)}
                </p>
              </div>
              <span
                className={cn(
                  "inline-flex w-fit rounded-full px-3 py-1 text-xs font-medium",
                  isOperationalReady
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-slate-100 text-slate-500",
                )}
              >
                {isOperationalReady ? "Ready for rota planning" : "Readiness blocked"}
              </span>
            </CardHeader>
            <CardContent>
              {isLoadingRota ? (
                <div className="mb-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  <Loader2 className="size-4 animate-spin" />
                  Loading weekly rota...
                </div>
              ) : null}

              {rotaError ? (
                <p className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {rotaError}
                </p>
              ) : null}

              <div className="overflow-x-auto rounded-2xl border border-slate-200">
                <div className="min-w-[760px]">
                  <div className="grid grid-cols-[160px_repeat(7,1fr)] bg-slate-50 text-xs font-medium uppercase tracking-[0.12em] text-slate-400">
                    <div className="border-r border-slate-200 px-4 py-3">Row</div>
                    {weekDays.map((day) => (
                      <div
                        key={day.label}
                        className="border-r border-slate-200 px-3 py-3 last:border-r-0"
                      >
                        <p>{day.label.slice(0, 3)}</p>
                        <p className="mt-1 normal-case tracking-normal text-slate-500">
                          {formatDisplayDate(day.date).replace(
                            ` ${day.date.getFullYear()}`,
                            "",
                          )}
                        </p>
                      </div>
                    ))}
                  </div>
                  {["Open shifts", "Staff rota"].map((row) => (
                    <div
                      key={row}
                      className="grid grid-cols-[160px_repeat(7,1fr)] border-t border-slate-200 text-sm"
                    >
                      <div className="border-r border-slate-200 px-4 py-10 font-medium text-slate-700">
                        {row}
                      </div>
                      {weekDays.map((day, index) => (
                        <div
                          key={`${row}-${day.label}`}
                          className="min-h-28 space-y-2 border-r border-slate-200 bg-white px-3 py-3 last:border-r-0"
                        >
                          {(row === "Open shifts"
                            ? shiftsByDay[index].open
                            : shiftsByDay[index].assigned
                          ).map((shift) => {
                            const assignedStaff = shift.assigned_employee_account_id
                              ? staffByUserId.get(shift.assigned_employee_account_id)
                              : null;
                            const employeeName = assignedStaff?.display_name ?? "Unassigned";

                            return (
                              <div
                                key={shift.id}
                                className={cn(
                                  "rounded-xl border px-3 py-2 text-xs shadow-sm",
                                  shift.assigned_employee_account_id
                                    ? "border-blue-100 bg-blue-50 text-blue-950"
                                    : "border-amber-100 bg-amber-50 text-amber-950",
                                )}
                              >
                                <p className="font-semibold">{employeeName}</p>
                                <p className="mt-1 text-slate-600">
                                  {formatTimeRange(shift.start_time, shift.end_time)}
                                </p>
                                {shift.role_required ? (
                                  <span className="mt-2 inline-flex rounded-full bg-white/80 px-2 py-0.5 font-medium text-slate-600">
                                    {shift.role_required}
                                  </span>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
              <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center">
                <p className="text-sm font-medium text-slate-700">
                  {weeklyShifts.length === 0
                    ? "No shifts created for this week"
                    : `${weeklyShifts.length} shift${
                        weeklyShifts.length === 1 ? "" : "s"
                      } loaded for this week.`}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  Manual shift creation will be added in the next phase.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Staff summary</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoadingStaffSummary ? (
                <div className="flex items-center gap-3 text-sm text-slate-600">
                  <Loader2 className="size-4 animate-spin" />
                  Loading staff summary...
                </div>
              ) : staffSummaryError ? (
                <p className="text-sm text-slate-500">{staffSummaryError}</p>
              ) : (
                <div>
                  <p className="text-3xl font-semibold text-slate-950">
                    {activeStaffCount ?? 0}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Active staff at selected site
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Pending requests</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-500">
                Request review will be connected in a later rota phase.
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {createShiftSuccess ? (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  {createShiftSuccess}
                </p>
              ) : null}
              <Button
                type="button"
                variant="outline"
                disabled={!canCreateShift}
                className="w-full justify-start"
                onClick={openCreateShiftModal}
              >
                Create shift
              </Button>
              {!canCreateShift ? (
                <p className="text-xs leading-5 text-slate-500">
                  Create shift unlocks when the selected site is operationally ready.
                </p>
              ) : null}
              {[
                "Publish rota - Coming later",
                "Generate week - Coming later",
                "AI recommendations - Coming later",
                "Export rota - Coming later",
              ].map((label) => (
                <Button
                  key={label}
                  type="button"
                  variant="outline"
                  disabled
                  className="w-full justify-start"
                >
                  {label}
                </Button>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      {isCreateShiftOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/40 px-4 py-6 sm:items-center">
          <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-950">Create shift</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Draft a shift for {formatDisplayDate(weekStart)} -{" "}
                  {formatDisplayDate(weekEnd)}. Backend wiring comes in Phase I.3.
                </p>
              </div>
              <button
                type="button"
                onClick={closeCreateShiftModal}
                className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Close create shift modal"
              >
                <X className="size-5" />
              </button>
            </div>

            <form
              className="space-y-5 px-5 py-5"
              onSubmit={(event) => {
                event.preventDefault();
                submitCreateShift();
              }}
            >
              {createShiftError ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {createShiftError}
                </p>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">Day</span>
                  <select
                    value={createShiftDraft.dayIndex}
                    onChange={(event) =>
                      updateCreateShiftField("dayIndex", event.target.value)
                    }
                    className={cn(
                      "flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                      touchedCreateShiftFields.dayIndex && createShiftErrors.dayIndex
                        ? "border-red-300"
                        : null,
                    )}
                  >
                    <option value="">Select day</option>
                    {weekDayLabels.map((day, index) => (
                      <option key={day} value={String(index)}>
                        {day}
                      </option>
                    ))}
                  </select>
                  {touchedCreateShiftFields.dayIndex && createShiftErrors.dayIndex ? (
                    <p className="text-sm text-red-600">
                      {createShiftErrors.dayIndex}
                    </p>
                  ) : null}
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    Assigned staff
                  </span>
                  <select
                    value={createShiftDraft.assignedStaffUserId}
                    onChange={(event) =>
                      updateCreateShiftField(
                        "assignedStaffUserId",
                        event.target.value,
                      )
                    }
                    className="flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <option value="">Unassigned / Open shift</option>
                    {activeStaffOptions.map((staff) => (
                      <option key={staff.id} value={staff.user_id}>
                        {staff.display_name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    Start time
                  </span>
                  <input
                    type="time"
                    value={createShiftDraft.startTime}
                    onChange={(event) =>
                      updateCreateShiftField("startTime", event.target.value)
                    }
                    className={cn(
                      "flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                      touchedCreateShiftFields.startTime && createShiftErrors.startTime
                        ? "border-red-300"
                        : null,
                    )}
                  />
                  {touchedCreateShiftFields.startTime && createShiftErrors.startTime ? (
                    <p className="text-sm text-red-600">
                      {createShiftErrors.startTime}
                    </p>
                  ) : null}
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">End time</span>
                  <input
                    type="time"
                    value={createShiftDraft.endTime}
                    onChange={(event) =>
                      updateCreateShiftField("endTime", event.target.value)
                    }
                    className={cn(
                      "flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                      touchedCreateShiftFields.endTime && createShiftErrors.endTime
                        ? "border-red-300"
                        : null,
                    )}
                  />
                  {touchedCreateShiftFields.endTime && createShiftErrors.endTime ? (
                    <p className="text-sm text-red-600">
                      {createShiftErrors.endTime}
                    </p>
                  ) : null}
                </label>
              </div>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">
                  Required role
                </span>
                <input
                  type="text"
                  value={createShiftDraft.roleRequired}
                  onChange={(event) =>
                    updateCreateShiftField("roleRequired", event.target.value)
                  }
                  className="flex h-11 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  placeholder="Optional role, e.g. Cashier"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">Notes</span>
                <textarea
                  value={createShiftDraft.notes}
                  onChange={(event) =>
                    updateCreateShiftField("notes", event.target.value)
                  }
                  className="min-h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 transition placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  placeholder="Optional internal note"
                />
              </label>

              <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-end">
                <Button type="button" variant="outline" onClick={closeCreateShiftModal}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={!isCreateShiftValid || isSubmittingShift}
                  className="h-auto min-h-10 whitespace-normal text-center"
                >
                  {isSubmittingShift ? "Creating draft..." : "Create draft shift"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StaffProfileContent({ staffId }: { staffId: string }) {
  return (
    <div className="mx-auto max-w-5xl">
      <StaffProfileDetail staffId={staffId} />
    </div>
  );
}
