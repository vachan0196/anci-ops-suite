"use client";

import {
  BarChart3,
  Building2,
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
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getCompanyProfile,
  getCurrentAdminSession,
  listStores,
} from "@/lib/api-client";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CompanySetupForm } from "@/components/admin/company-setup-form";
import { SiteSetupForm } from "@/components/admin/site-setup-form";
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

type SetupKey = "hasCompany" | "hasSite";

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

type AdminShellProps = {
  activePage?: "dashboard" | "company" | "site";
};

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

const operationNavItems = [
  { label: "Dashboard / Rota Home", icon: Home },
  { label: "Hot Food", icon: Utensils },
  { label: "Reports", icon: BarChart3 },
  { label: "Payroll & Compensation", icon: WalletCards },
  { label: "Employee Profile", icon: UserRound },
  { label: "Settings", icon: Settings },
];

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

function getNextSetupHref(setupState: Record<SetupKey, boolean>) {
  if (!setupState.hasCompany) {
    return "/admin/company";
  }

  if (!setupState.hasSite) {
    return "/admin/sites/new";
  }

  return "/admin/sites/new";
}

export function AdminShell({ activePage = "dashboard" }: AdminShellProps) {
  const router = useRouter();
  const [session, setSession] = useState<SessionState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [gateMessage, setGateMessage] = useState(false);
  const [comingNextMessage, setComingNextMessage] = useState<string | null>(null);
  const [hasCompanyProfile, setHasCompanyProfile] = useState(false);
  const [hasFirstSiteProfile, setHasFirstSiteProfile] = useState(false);

  // Setup readiness currently combines backend company profile completion and
  // backend stores existence. Staff readiness remains a later phase.
  const setupState = {
    hasCompany: hasCompanyProfile,
    hasSite: hasFirstSiteProfile,
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
  const setupProgress = (completedSetupCount / 2) * 100;
  const nextSetupHref = getNextSetupHref(setupState);

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

          if (isMounted) {
            setHasCompanyProfile(companyProfile.company_setup_completed);
            setHasFirstSiteProfile(stores.some((store) => store.is_active !== false));
          }
        } catch {
          if (isMounted) {
            setHasCompanyProfile(false);
            setHasFirstSiteProfile(false);
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

    if (setupState.hasCompany && setupState.hasSite) {
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

    setComingNextMessage("Staff directory will be available after site setup is complete.");
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
                {operationNavItems.map(({ label, icon: Icon }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={showOperationGate}
                    className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-slate-500 transition hover:bg-white/5 hover:text-slate-300"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <Icon className="size-4 shrink-0" />
                      <span className="truncate">{label}</span>
                    </span>
                    <Lock className="size-3.5 shrink-0" />
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
                      this module.
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
            ) : (
              <SiteContent />
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
  onContinueSetup,
  onOpenCompany,
  onOpenSite,
  onShowSiteGate,
  onShowComingNext,
}: {
  completedSetupCount: number;
  setupProgress: number;
  setupCards: SetupCard[];
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
                      {completedSetupCount} of 2 completed
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
                <div className="mt-4 grid gap-2 text-sm text-slate-500 sm:grid-cols-2">
                  <span>Company details</span>
                  <span>First site</span>
                </div>
              </CardContent>
            </Card>

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
