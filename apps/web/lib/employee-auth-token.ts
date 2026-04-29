const EMPLOYEE_ACCESS_TOKEN_KEY = "forecourt_employee_access_token";

export function getEmployeeAccessToken() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(EMPLOYEE_ACCESS_TOKEN_KEY);
}

export function setEmployeeAccessToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(EMPLOYEE_ACCESS_TOKEN_KEY, token);
}

export function clearEmployeeAccessToken() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(EMPLOYEE_ACCESS_TOKEN_KEY);
}
