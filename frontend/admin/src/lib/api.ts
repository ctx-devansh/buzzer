const BASE = '/api';

/** Error from a non-2xx response. The message is FastAPI's `detail` or a BuzzerError's `message`. */
async function toError(res: Response): Promise<Error> {
  const err = (await res.json().catch(() => ({}))) as { detail?: unknown; message?: unknown };
  return new Error(
    typeof err.detail === 'string' ? err.detail
    : typeof err.message === 'string' ? err.message
    : `HTTP ${res.status}`,
  );
}

/**
 * A stored token the server rejects (expired, or left over from an earlier session —
 * RequireAdmin only checks that one exists) sends the user back to login instead of
 * leaving every page showing a 401. /auth/* is excluded so a wrong password still
 * shows its error on the login page.
 */
function handleUnauthorized(path: string, res: Response, token: string | null): void {
  if (res.status !== 401 || !token || path.startsWith('/auth/')) return;
  localStorage.removeItem('token');
  window.location.replace(`${import.meta.env.BASE_URL}login`);
}

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers as Record<string, string> ?? {}),
    },
  });
  if (!res.ok) {
    handleUnauthorized(path, res, token);
    throw await toError(res);
  }
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

/** Trigger a file download from a fetch response */
async function downloadFetch(path: string): Promise<void> {
  const token = localStorage.getItem('token');
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    handleUnauthorized(path, res, token);
    throw await toError(res);
  }
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

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
  /** POST multipart/form-data (for file uploads) */
  postForm: <T>(path: string, form: FormData) => {
    const token = localStorage.getItem('token');
    return fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        handleUnauthorized(path, res, token);
        throw await toError(res);
      }
      const text = await res.text();
      return (text ? JSON.parse(text) : {}) as T;
    });
  },
  download: downloadFetch,
};
