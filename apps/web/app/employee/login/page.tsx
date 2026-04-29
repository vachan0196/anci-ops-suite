"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { employeeLogin, lookupPublicSiteByCode } from "@/lib/api-client";
import { setEmployeeAccessToken } from "@/lib/employee-auth-token";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function EmployeeLoginPage() {
  const router = useRouter();
  const [siteCode, setSiteCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!siteCode.trim() || !username.trim() || !password) {
      setError("Site code, username, and password are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      let site;
      try {
        site = await lookupPublicSiteByCode(siteCode.trim());
      } catch {
        setError("We could not find that site. Please check your site code.");
        return;
      }

      const response = await employeeLogin({
        site_id: site.site_id,
        username: username.trim(),
        password,
      });
      setEmployeeAccessToken(response.access_token);
      router.push("/employee");
    } catch {
      setError("Invalid site, username, or password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-md items-center">
        <Card className="w-full border-slate-200 shadow-sm">
          <CardContent className="space-y-6 p-6">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-400">
                Employee Portal
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                Sign in
              </h1>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Use your site code, username, and password from your manager.
              </p>
            </div>

            <form className="space-y-4" onSubmit={submitLogin}>
              <label className="block space-y-2 text-sm font-medium text-slate-700">
                <span>Site code</span>
                <Input
                  value={siteCode}
                  onChange={(event) => setSiteCode(event.target.value)}
                  autoComplete="organization"
                />
                <span className="block text-xs font-normal text-slate-500">
                  Ask your manager for your site code.
                </span>
              </label>
              <label className="block space-y-2 text-sm font-medium text-slate-700">
                <span>Username</span>
                <Input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                />
              </label>
              <label className="block space-y-2 text-sm font-medium text-slate-700">
                <span>Password</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
              </label>

              {error ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </p>
              ) : null}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
            </form>

            <Link
              href="/admin/login"
              className="block text-center text-sm font-medium text-blue-700 hover:text-blue-800"
            >
              Admin Portal login
            </Link>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
