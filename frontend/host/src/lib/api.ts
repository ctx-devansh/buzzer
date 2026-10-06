import { getToken } from './auth';

const BASE = '/api';

/** Thrown for any non-2xx response; `status` lets a caller branch on e.g. 403. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/**
 * FastAPI's 422 `detail` is a list of `{loc, msg}`; turn it into one readable line,
 * e.g. "max_players: Input should be greater than or equal to 1".
 */
function validationMessage(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const parts = detail.map((d) => {
    const item = d as { loc?: unknown; msg?: unknown };
    const msg = typeof item.msg === 'string' ? item.msg.replace(/^Value error, /, '') : 'Invalid value';
    const loc = Array.isArray(item.loc) ? item.loc.filter((l) => l !== 'body') : [];
    return loc.length ? `${loc.join('.')}: ${msg}` : msg;
  });
  return parts.join('; ');
}

/** Error from a non-2xx response: FastAPI's string `detail`, a BuzzerError's `message`, or a 422's field errors. */
async function toError(res: Response): Promise<ApiError> {
  const err = (await res.json().catch(() => ({}))) as { detail?: unknown; message?: unknown };
  const message =
    typeof err.detail === 'string' ? err.detail
    : typeof err.message === 'string' ? err.message
    : validationMessage(err.detail) ?? `HTTP ${res.status}`;
  return new ApiError(message, res.status);
}

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers as Record<string, string> ?? {}),
    },
  });
  if (!res.ok) throw await toError(res);
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

/**
 * Trigger a file download. Bypasses apiFetch on purpose: it needs the raw response
 * for Content-Disposition and the blob.
 */
async function downloadFetch(path: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw await toError(res);
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : 'download';
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Multipart body, with no Content-Type of our own: the browser sets the boundary. */
function sendForm<T>(method: 'POST' | 'PUT', path: string, form: FormData): Promise<T> {
  const token = getToken();
  return fetch(`${BASE}${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  }).then(async (res) => {
    if (!res.ok) throw await toError(res);
    const text = await res.text();
    return (text ? JSON.parse(text) : {}) as T;
  });
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
  /**
   * POST multipart/form-data (file uploads). Bypasses apiFetch on purpose: apiFetch
   * always sets Content-Type: application/json, which would break the multipart boundary.
   */
  postForm: <T>(path: string, form: FormData) => sendForm<T>('POST', path, form),
  /** PUT multipart/form-data (replacing a library image). */
  putForm: <T>(path: string, form: FormData) => sendForm<T>('PUT', path, form),
  download: downloadFetch,
};
