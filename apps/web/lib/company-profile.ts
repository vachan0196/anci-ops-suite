import type { CompanyProfileResponse } from "@/lib/api-client";

export type BusinessType =
  | "limited_company"
  | "sole_trader"
  | "partnership"
  | "llp"
  | "other";

export type CompanyFormProfile = {
  companyName: string;
  businessType: BusinessType;
  companyRegistrationNumber: string | null;
  vatRegistered: boolean;
  vatNumber: string | null;
  primaryContactName: string;
  businessEmail: string;
  businessPhone: string;
  addressLine1: string;
  addressLine2: string | null;
  city: string;
  postcode: string;
  country: string;
  timezone: string;
  currency: string;
};

export function toCompanyFormProfile(
  profile: CompanyProfileResponse,
): CompanyFormProfile {
  return {
    companyName: profile.company_name ?? "",
    businessType: "limited_company",
    companyRegistrationNumber: null,
    vatRegistered: false,
    vatNumber: null,
    primaryContactName: profile.owner_name ?? "",
    businessEmail: profile.business_email ?? "",
    businessPhone: profile.phone_number ?? "",
    addressLine1: profile.registered_address ?? "",
    addressLine2: null,
    city: "",
    postcode: "",
    country: "United Kingdom",
    timezone: "Europe/London",
    currency: "GBP",
  };
}
