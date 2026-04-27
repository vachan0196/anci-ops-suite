import { AdminShell } from "@/components/admin/admin-shell";

export default async function AdminStaffProfilePage({
  params,
}: {
  params: Promise<{ staffId: string }>;
}) {
  const { staffId } = await params;

  return <AdminShell activePage="staffProfile" staffId={staffId} />;
}
