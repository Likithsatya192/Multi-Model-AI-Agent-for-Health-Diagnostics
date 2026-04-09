import DOMPurify from "dompurify";

/**
 * Sanitizes an HTML string using DOMPurify.
 * SSR-safe: returns the original string on the server since
 * this app only renders this content client-side.
 */
export function sanitizeHtml(dirty: string): string {
  if (typeof window === "undefined") return dirty;
  return DOMPurify.sanitize(dirty, { USE_PROFILES: { html: true } });
}
