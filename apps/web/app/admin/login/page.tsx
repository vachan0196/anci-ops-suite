import { AdminLoginForm } from "@/components/admin/admin-login-form";

export default function AdminLoginPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 pb-12 pt-20 sm:px-6 lg:pt-24">
      <div className="mx-auto max-w-md">
        <AdminLoginForm />
      </div>
    </main>
  );
}
