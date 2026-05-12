const EMPLOYEE_ACCESS_TOKEN_KEY = "forecourt_employee_access_token";
const ACCESS_TOKEN_KEY = "forecourt_access_token";

let employeeAccessToken: string | null = null;

export function getEmployeeAccessToken() {
  return employeeAccessToken;
}

export function setEmployeeAccessToken(token: string) {
  employeeAccessToken = token;
  clearLegacyEmployeeAccessToken();
}

export function clearEmployeeAccessToken() {
  employeeAccessToken = null;
  clearLegacyEmployeeAccessToken();
}

export function clearLegacyEmployeeAccessToken() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(EMPLOYEE_ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}
