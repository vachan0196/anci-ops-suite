import { AdminShell } from "@/components/admin/admin-shell";

export default async function AdminSiteEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <AdminShell activePage="siteEdit" siteId={id} />;
}
