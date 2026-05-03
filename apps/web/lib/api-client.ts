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

export type OpeningHoursDay = {
  day_of_week: number;
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
};

export type OpeningHoursBulkUpdate = {
  opening_hours: OpeningHoursDay[];
};

export type OpeningHoursResponse = {
  store_id: string;
  opening_hours: OpeningHoursDay[];
};

export type StoreSettingsResponse = {
  store_id: string;
  business_week_start_day: number;
};

export type StoreSettingsUpdate = {
  business_week_start_day?: number;
};

export type StoreReadinessResponse = {
  store_id: string;
  opening_hours_configured: boolean;
  staff_configured: boolean;
  operational_ready: boolean;
};

export type WeeklyRotaShift = {
  id: string;
  assigned_employee_account_id: string | null;
  role_required: string | null;
  start_time: string;
  end_time: string;
};

export type WeeklyRotaResponse = {
  site_id: string;
  week_start: string;
  is_published: boolean;
  published_shift_count: number;
  draft_shift_count: number;
  shifts: WeeklyRotaShift[];
};

export type CreateShiftPayload = {
  assigned_employee_account_id: string | null;
  role_required?: string | null;
  start_time: string;
  end_time: string;
};

export type UpdateShiftPayload = CreateShiftPayload;

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
  employee_username?: string | null;
  employee_password?: string | null;
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
  employee_account_id?: string | null;
  display_name: string;
  job_title?: string | null;
  hourly_rate?: string | null;
  pay_type?: string | null;
  phone?: string | null;
  is_active?: boolean;
  created_at?: string;
};

export type StaffListParams = {
  store_id?: string;
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

export type StaffDirectoryItem = {
  id: string;
  user_id: string;
  display_name: string;
  email: string | null;
  job_title: string | null;
  phone: string | null;
  store_id: string | null;
  store_name: string | null;
  roles: string[];
  is_active: boolean;
  created_at: string;
};

export type StaffDirectoryParams = {
  store_id?: string;
  is_active?: boolean;
};

export type EmployeeLoginInput = {
  site_id: string;
  username: string;
  password: string;
};

export type PublicSiteLookupResponse = {
  site_id: string;
  site_code: string;
  site_name: string;
};

export type EmployeeAccountSummary = {
  id: string;
  display_name: string;
  tenant_id: string;
  site_id: string;
};

export type EmployeeLoginResponse = {
  access_token: string;
  token_type: string;
  employee_account: EmployeeAccountSummary;
};

export type EmployeeMeResponse = {
  portal: "employee";
  employee_account_id: string;
  tenant_id: string;
  site_id: string;
  display_name: string;
};

export type EmployeeMyRotaShift = {
  id: string;
  start_time: string;
  end_time: string;
  role_required: string | null;
  status: string;
};

export type EmployeeMyRotaResponse = {
  week_start: string;
  site_id: string;
  employee_account_id: string;
  shifts: EmployeeMyRotaShift[];
};

export type EmployeeAvailabilityType =
  | "available"
  | "unavailable"
  | "available_extra";

export type EmployeeAvailabilityItem = {
  id: string;
  store_id: string | null;
  site_id: string | null;
  employee_account_id: string | null;
  week_start: string;
  date: string;
  start_time: string | null;
  end_time: string | null;
  type: EmployeeAvailabilityType;
  notes: string | null;
  created_at: string;
};

export type EmployeeAvailabilityResponse = {
  week_start: string;
  available_stores: Store[];
  selected_store: Store;
  items: EmployeeAvailabilityItem[];
};

export type EmployeeAvailabilityCreate = {
  week_start: string;
  date: string;
  start_time?: string | null;
  end_time?: string | null;
  type: EmployeeAvailabilityType;
  notes?: string | null;
};

export type EmployeeRequestType = "leave" | "swap" | "cover";

export type EmployeeRequestStatus =
  | "pending"
  | "cancelled"
  | "target_accepted"
  | "target_declined"
  | "approved"
  | "rejected";

export type EmployeeRequestItem = {
  id: string;
  request_type: EmployeeRequestType;
  status: EmployeeRequestStatus;
  site_id: string | null;
  shift_id: string | null;
  requester_employee_account_id: string | null;
  target_employee_account_id: string | null;
  start_date: string | null;
  end_date: string | null;
  reason: string | null;
  created_at: string;
  updated_at: string | null;
  cancelled_at: string | null;
};

export type EmployeeRequestResponse = {
  available_stores: Store[];
  selected_store: Store;
  items: EmployeeRequestItem[];
};

export type EmployeeRequestTargetItem = {
  employee_account_id: string;
  display_name: string;
  role_labels: string[];
  is_active: boolean;
};

export type EmployeeRequestTargetResponse = {
  available_stores: Store[];
  selected_store: Store;
  items: EmployeeRequestTargetItem[];
};

export type EmployeeInboundRequestShift = {
  id: string;
  start_time: string;
  end_time: string;
  role_required: string | null;
};

export type EmployeeInboundRequestItem = {
  id: string;
  request_type: "swap" | "cover";
  status: EmployeeRequestStatus;
  requester_display_name: string | null;
  reason: string | null;
  shift: EmployeeInboundRequestShift | null;
  created_at: string;
  target_decided_at: string | null;
};

export type EmployeeInboundRequestResponse = {
  available_stores: Store[];
  selected_store: Store;
  items: EmployeeInboundRequestItem[];
};

export type EmployeeInboundRequestDecisionResponse = {
  id: string;
  status: "target_accepted" | "target_declined";
  rota_updated: boolean;
  message: string;
};

export type EmployeeRequestCreate = {
  request_type: EmployeeRequestType;
  shift_id?: string | null;
  target_employee_account_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  reason: string;
};

export type SiteRequestItem = {
  id: string;
  request_type: EmployeeRequestType;
  status: EmployeeRequestStatus;
  requester_employee_account_id: string | null;
  requester_display_name: string | null;
  target_employee_account_id: string | null;
  target_display_name: string | null;
  shift_id: string | null;
  start_date: string | null;
  end_date: string | null;
  reason: string | null;
  created_at: string;
  decided_at: string | null;
  approver_user_id: string | null;
  approval_reason: string | null;
  rejection_reason: string | null;
};

export type SiteRequestListResponse = {
  site_id: string;
  items: SiteRequestItem[];
};

export type SiteRequestDecisionResponse = {
  id: string;
  status: "approved" | "rejected";
  rota_updated: boolean;
  affected_shift_count: number;
  message: string | null;
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

export function employeeLogin(input: EmployeeLoginInput) {
  return request<EmployeeLoginResponse>("/api/v1/auth/employee/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function lookupPublicSiteByCode(code: string) {
  return request<PublicSiteLookupResponse>(
    `/api/v1/public/sites/lookup?code=${encodeURIComponent(code)}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );
}

export function getCurrentEmployeeSession(token: string) {
  return request<EmployeeMeResponse>("/api/v1/auth/employee/me", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function getEmployeeMyRota(token: string, weekStart: string) {
  return request<EmployeeMyRotaResponse>(
    `/api/v1/employee/rota/my?week_start=${encodeURIComponent(weekStart)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function getEmployeeAvailability(token: string, weekStart: string) {
  return request<EmployeeAvailabilityResponse>(
    `/api/v1/employee/me/availability?week_start=${encodeURIComponent(weekStart)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function createEmployeeAvailability(
  token: string,
  payload: EmployeeAvailabilityCreate,
) {
  return request<EmployeeAvailabilityItem>("/api/v1/employee/me/availability", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export function deleteEmployeeAvailability(token: string, entryId: string) {
  return request<EmployeeAvailabilityItem>(
    `/api/v1/employee/me/availability/${entryId}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}

export function getEmployeeRequests(token: string, params?: {
  status?: EmployeeRequestStatus;
  request_type?: EmployeeRequestType;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) {
    searchParams.set("status", params.status);
  }
  if (params?.request_type) {
    searchParams.set("request_type", params.request_type);
  }
  const query = searchParams.toString();
  return request<EmployeeRequestResponse>(
    `/api/v1/employee/me/requests${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function createEmployeeRequest(token: string, payload: EmployeeRequestCreate) {
  return request<EmployeeRequestItem>("/api/v1/employee/me/requests", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export function cancelEmployeeRequest(token: string, requestId: string) {
  return request<EmployeeRequestItem>(
    `/api/v1/employee/me/requests/${requestId}/cancel`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}

export function getEmployeeRequestTargets(
  token: string,
  params?: {
    store_id?: string;
    shift_id?: string;
    request_type?: "swap" | "cover";
  },
) {
  const searchParams = new URLSearchParams();
  if (params?.store_id) {
    searchParams.set("store_id", params.store_id);
  }
  if (params?.shift_id) {
    searchParams.set("shift_id", params.shift_id);
  }
  if (params?.request_type) {
    searchParams.set("request_type", params.request_type);
  }
  const query = searchParams.toString();
  return request<EmployeeRequestTargetResponse>(
    `/api/v1/employee/me/request-targets${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function getEmployeeInboundRequests(
  token: string,
  params?: {
    status?: EmployeeRequestStatus;
    request_type?: "swap" | "cover";
  },
) {
  const searchParams = new URLSearchParams();
  if (params?.status) {
    searchParams.set("status", params.status);
  }
  if (params?.request_type) {
    searchParams.set("request_type", params.request_type);
  }
  const query = searchParams.toString();
  return request<EmployeeInboundRequestResponse>(
    `/api/v1/employee/me/inbound-requests${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function acceptEmployeeInboundRequest(token: string, requestId: string) {
  return request<EmployeeInboundRequestDecisionResponse>(
    `/api/v1/employee/me/inbound-requests/${requestId}/accept`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}

export function declineEmployeeInboundRequest(
  token: string,
  requestId: string,
  declineReason?: string,
) {
  return request<EmployeeInboundRequestDecisionResponse>(
    `/api/v1/employee/me/inbound-requests/${requestId}/decline`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ decline_reason: declineReason || null }),
    },
  );
}

export function listSiteRequests(
  token: string,
  siteId: string,
  params?: { status?: EmployeeRequestStatus; request_type?: EmployeeRequestType },
) {
  const searchParams = new URLSearchParams();
  if (params?.status) {
    searchParams.set("status", params.status);
  }
  if (params?.request_type) {
    searchParams.set("request_type", params.request_type);
  }
  const query = searchParams.toString();
  return request<SiteRequestListResponse>(
    `/api/v1/sites/${siteId}/requests${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function approveSiteRequest(
  token: string,
  siteId: string,
  requestId: string,
  approvalReason?: string,
) {
  return request<SiteRequestDecisionResponse>(
    `/api/v1/sites/${siteId}/requests/${requestId}/approve`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ approval_reason: approvalReason || null }),
    },
  );
}

export function rejectSiteRequest(
  token: string,
  siteId: string,
  requestId: string,
  rejectionReason?: string,
) {
  return request<SiteRequestDecisionResponse>(
    `/api/v1/sites/${siteId}/requests/${requestId}/reject`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ rejection_reason: rejectionReason || null }),
    },
  );
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

export function getStoreOpeningHours(token: string, storeId: string) {
  return request<OpeningHoursResponse>(`/api/v1/stores/${storeId}/opening-hours`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function updateStoreOpeningHours(
  token: string,
  storeId: string,
  input: OpeningHoursBulkUpdate,
) {
  return request<OpeningHoursResponse>(`/api/v1/stores/${storeId}/opening-hours`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function getStoreSettings(token: string, storeId: string) {
  return request<StoreSettingsResponse>(`/api/v1/stores/${storeId}/settings`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function updateStoreSettings(
  token: string,
  storeId: string,
  input: StoreSettingsUpdate,
) {
  return request<StoreSettingsResponse>(`/api/v1/stores/${storeId}/settings`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
}

export function getStoreReadiness(token: string, storeId: string) {
  return request<StoreReadinessResponse>(`/api/v1/stores/${storeId}/readiness`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function getSiteWeeklyRota(token: string, siteId: string, weekStart: string) {
  return request<WeeklyRotaResponse>(
    `/api/v1/sites/${siteId}/rota/week?week_start=${encodeURIComponent(weekStart)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );
}

export function createShift(
  token: string,
  siteId: string,
  payload: CreateShiftPayload,
) {
  return request<WeeklyRotaShift>(`/api/v1/sites/${siteId}/shifts`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export function updateShift(
  token: string,
  siteId: string,
  shiftId: string,
  payload: UpdateShiftPayload,
) {
  return request<WeeklyRotaShift>(`/api/v1/sites/${siteId}/shifts/${shiftId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export function cancelShift(token: string, siteId: string, shiftId: string) {
  return request<WeeklyRotaShift>(
    `/api/v1/sites/${siteId}/shifts/${shiftId}/cancel`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
}

export function publishRota(token: string, siteId: string, weekStart: string) {
  return request<WeeklyRotaResponse>(`/api/v1/sites/${siteId}/rota/publish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ week_start: weekStart }),
  });
}

export function unpublishRota(token: string, siteId: string, weekStart: string) {
  return request<WeeklyRotaResponse>(`/api/v1/sites/${siteId}/rota/unpublish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ week_start: weekStart }),
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

export function listStaff(token: string, params?: StaffListParams) {
  const searchParams = new URLSearchParams();

  if (params?.store_id) {
    searchParams.set("store_id", params.store_id);
  }

  const query = searchParams.toString();

  return request<StaffProfile[]>(`/api/v1/staff${query ? `?${query}` : ""}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export function listStaffRoles(token: string, staffId: string) {
  return request<StaffRole[]>(`/api/v1/staff/${staffId}/roles`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
}

export async function listStaffDirectory(token: string, params?: StaffDirectoryParams) {
  const searchParams = new URLSearchParams();

  if (params?.store_id) {
    searchParams.set("store_id", params.store_id);
  }

  if (params?.is_active !== undefined) {
    searchParams.set("is_active", String(params.is_active));
  }

  const query = searchParams.toString();
  const response = await request<StaffDirectoryItem[] | { items?: StaffDirectoryItem[] }>(
    `/api/v1/staff/directory${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
  );

  if (Array.isArray(response)) {
    return response;
  }

  return response.items ?? [];
}

export async function getStaffDirectoryItem(token: string, staffId: string) {
  const staff = await listStaffDirectory(token);
  return staff.find((item) => item.id === staffId) ?? null;
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
