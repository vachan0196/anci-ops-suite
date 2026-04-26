export const FIRST_SITE_KEY = "forecourt_first_site";

export type OpeningHoursType = "24_7" | "custom";
export type SiteStatus = "active" | "inactive" | "draft";
export type StaffAccountStatus = "active" | "inactive";

export type StaffPreview = {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  weeklyHourCap: number | null;
  roles: string[];
  accountStatus: StaffAccountStatus;
};

export type FirstSiteProfile = {
  siteCode: string;
  locationName: string;
  fullAddress: string;
  sitePhone: string;
  siteEmail: string;
  openingHoursType: OpeningHoursType;
  openingTime: string | null;
  closingTime: string | null;
  timezone: string;
  status: SiteStatus;
  notes: string | null;
  manager: {
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    role: "manager";
    assignExistingEmployee: boolean;
  };
  staffMembers: StaffPreview[];
  createdAt: string;
  updatedAt: string;
};

// Temporary frontend-only site setup storage.
// Replace with backend site/staff endpoints later.
export function getFirstSiteProfile() {
  if (typeof window === "undefined") {
    return null;
  }

  const value = window.localStorage.getItem(FIRST_SITE_KEY);

  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as FirstSiteProfile;
  } catch {
    return null;
  }
}

export function saveFirstSiteProfile(site: FirstSiteProfile) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(FIRST_SITE_KEY, JSON.stringify(site));
}
