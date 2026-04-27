const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
  detail?: string;
  message?: string;
};

type AdminLoginInput = {
  email: string;
  password: string;
};

type AdminRegisterInput = {
  full_name: string;
  email: string;
  password: string;
};

export type AdminLoginResponse = {
  access_token: string;
  token_type: string;
};

export type AuthMeResponse = {
  id: string;
  email: string;
  is_active: boolean;
  active_tenant_id: string;
  active_tenant_role: "owner" | "admin" | "manager";
  created_at: string;
};

export type AdminRegisterResponse = {
  id: string;
  email: string;
  is_active: boolean;
  active_tenant_id: string;
  active_tenant_role: "admin";
  created_at: string;
};

export type CompanyProfileResponse = {
  tenant_id: string;
  company_name: string | null;
  owner_name: string | null;
  business_email: string | null;
  phone_number: string | null;
  registered_address: string | null;
  company_setup_completed: boolean;
  company_setup_completed_at: string | null;
};

export type CompanyProfileUpdate = {
  company_name?: string | null;
  owner_name?: string | null;
  business_email?: string | null;
  phone_number?: string | null;
  registered_address?: string | null;
};

export type Store = {
  id: string;
  tenant_id?: string;
  code: string | null;
  name: string;
  timezone: string | null;
  address_line1: string | null;
  city: string | null;
  postcode: string | null;
  phone: string | null;
  manager_user_id?: string | null;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string | null;
};

export type StoreCreate = {
  code?: string | null;
  name: string;
  timezone?: string | null;
  address_line1?: string | null;
  city?: string | null;
  postcode?: string | null;
  phone?: string | null;
  manager_user_id?: string | null;
};

export type AdminUserCreate = {
  email: string;
  password: string;
  full_name?: string | null;
  role?: "admin" | "member";
};

export type AdminUser = {
  id: string;
  email: string;
  active_tenant_id: string;
  role: "admin" | "member";
};

export type StaffCreate = {
  user_id: string;
  store_id?: string | null;
  display_name: string;
  job_title?: string | null;
  hourly_rate?: string | number | null;
  pay_type?: "hourly" | "salary" | null;
  phone?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  contract_type?: "full_time" | "part_time" | "zero_hours" | null;
  rtw_status?: "pending" | "verified" | "expired" | null;
  notes?: string | null;
  is_active?: boolean;
};

export type StaffProfile = {
  id: string;
  tenant_id: string;
  user_id: string;
  store_id: string | null;
  display_name: string;
  job_title?: string | null;
  hourly_rate?: string | null;
  pay_type?: string | null;
  phone?: string | null;
  is_active?: boolean;
  created_at?: string;
};

export type StaffRoleCreate = {
  role: string;
};

export type StaffRole = {
  id: string;
  tenant_id: string;
  staff_id: string;
  role: string;
  created_at: string;
};

export class ApiError extends Error {
  code?: string;
  details?: unknown;
  status: number;

  constructor({
    message,
    status,
    code,
    details,
  }: {
    message: string;
    status: number;
    code?: string;
    details?: unknown;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ApiErrorPayload | null = null;

  try {
    payload = (await response.json()) as ApiErrorPayload;
  } catch {
    payload = null;
  }

  const message =
    payload?.error?.message ||
    payload?.message ||
    payload?.detail ||
    "Something went wrong. Please try again.";

  return new ApiError({
    status: response.status,
    code: payload?.error?.code,
    details: payload?.error?.details,
    message,
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("NETWORK_ERROR");
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

export function adminLogin(input: AdminLoginInput) {
  const body = new URLSearchParams({
    username: input.email,
    password: input.password,
  });

  // Current backend login accepts form-encoded username/password at /auth/login.
  // This differs from the newer API Contracts PRD, which expects /auth/admin/login.
  return request<AdminLoginResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
}

export function adminRegister(input: AdminRegisterInput) {
  // Current backend accepts only full_name, email, and password here. Reconcile this
  // with the API Contracts PRD later before sending confirm_password or accepted_terms.
  return request<AdminRegisterResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getCurrentAdminSession(token: string) {
  return request<AuthMeResponse>("/api/v1/auth/me", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function getCompanyProfile(token: string) {
  return request<CompanyProfileResponse>("/api/v1/company/profile", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function updateCompanyProfile(token: string, input: CompanyProfileUpdate) {
  return request<CompanyProfileResponse>("/api/v1/company/profile", {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export async function listStores(token: string) {
  const response = await request<Store[] | { items?: Store[] }>("/api/v1/stores", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (Array.isArray(response)) {
    return response;
  }

  return response.items ?? [];
}

export function createStore(token: string, input: StoreCreate) {
  return request<Store>("/api/v1/stores", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function createAdminUser(token: string, input: AdminUserCreate) {
  return request<AdminUser>("/api/v1/admin/users", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function createStaffProfile(token: string, input: StaffCreate) {
  return request<StaffProfile>("/api/v1/staff", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function addStaffRole(token: string, staffId: string, input: StaffRoleCreate) {
  return request<StaffRole>(`/api/v1/staff/${staffId}/roles`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}
