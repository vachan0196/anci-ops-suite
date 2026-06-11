export const staffRoleOptions = [
  "Cashier",
  "Hot Food",
  "Stock",
  "Cleaner",
  "Supervisor",
  "Manager",
];

export function normalizeStaffRole(role: string) {
  return role.trim().toLowerCase();
}
