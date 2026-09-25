export const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidPhoneNumber(value: string) {
  const trimmed = value.trim();

  if (!/^\+?[0-9\s()-]+$/.test(trimmed)) {
    return false;
  }

  const digitCount = trimmed.replace(/\D/g, "").length;
  return digitCount >= 7 && digitCount <= 15;
}
