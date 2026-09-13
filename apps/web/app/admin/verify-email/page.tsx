import { VerifyEmailForm } from "@/components/admin/verify-email-form";

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const { token } = await searchParams;

  return (
    <main className="min-h-screen bg-slate-100 px-4 pb-12 pt-20 sm:px-6 lg:pt-24">
      <div className="mx-auto max-w-md">
        <VerifyEmailForm initialToken={typeof token === "string" ? token : null} />
      </div>
    </main>
  );
}
