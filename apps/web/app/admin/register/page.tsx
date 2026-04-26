import { AdminRegisterForm } from "@/components/admin/admin-register-form";

export default function AdminRegisterPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 pb-12 pt-12 sm:px-6 lg:pt-16">
      <div className="mx-auto max-w-md">
        <AdminRegisterForm />
      </div>
    </main>
  );
}
