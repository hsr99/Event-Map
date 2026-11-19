// Base URL of the FastAPI backend (poster extraction + submissions).
// Set VITE_API_URL in the repo-root .env; defaults to the local dev server.
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

// Pull a readable message out of a FastAPI error response.
export async function errorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('; ');
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}
