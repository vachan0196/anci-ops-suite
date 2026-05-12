const ACCESS_TOKEN_KEY = "forecourt_access_token";
const EMPLOYEE_ACCESS_TOKEN_KEY = "forecourt_employee_access_token";

let accessToken: string | null = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string) {
  accessToken = token;
  clearLegacyAccessToken();
}

export function clearAccessToken() {
  accessToken = null;
  clearLegacyAccessToken();
}

export function clearLegacyAccessToken() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(EMPLOYEE_ACCESS_TOKEN_KEY);
}
