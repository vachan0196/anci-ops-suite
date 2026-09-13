import { ForgotPasswordForm } from "@/components/admin/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 pb-12 pt-20 sm:px-6 lg:pt-24">
      <div className="mx-auto max-w-md">
        <ForgotPasswordForm />
      </div>
    </main>
  );
}
