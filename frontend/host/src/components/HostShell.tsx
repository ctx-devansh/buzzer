import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { Gamepad2, History, LogOut, Play, Shield, Users } from 'lucide-react';
import { clearToken, getRole, getToken } from '../lib/auth';
import { ADMIN_APP_URL } from '../lib/links';
import { Button } from './ui/button';

export interface ShellCourse {
  id: number;
  name: string;
  semester: string;
  role: string;
}

interface ShellContext {
  courses: ShellCourse[];
}

/** The HOST-course list the shell loaded. Pages must not fetch /game/my-courses themselves. */
export function useShellCourses(): ShellCourse[] {
  return useOutletContext<ShellContext>().courses;
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'forbidden' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; courses: ShellCourse[] };

// Pages that stay reachable when the user hosts no course: they show the user's own
// sessions/live rooms, which are filtered on host_user_id, not on course access.
// Exact match only — the deep management routes are not exempt.
const EXEMPT_PATHS = new Set(['/home', '/sessions']);

const NO_COURSES: ShellCourse[] = [];

export default function HostShell() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const isAdmin = getRole() === 'ADMIN';

  // The one caller of /game/my-courses in the host app. A raw fetch rather than
  // api.get because the shell must branch on the status (403 = guest account), and
  // api.ts discards it. Keep this the only such copy.
  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const token = getToken();
      const res = await fetch('/api/game/my-courses', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.status === 403) {
        setState({ kind: 'forbidden' });
        return;
      }
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: unknown; message?: unknown };
        const message =
          typeof err.detail === 'string' ? err.detail
          : typeof err.message === 'string' ? err.message
          : `HTTP ${res.status}`;
        setState({ kind: 'error', message });
        return;
      }
      setState({ kind: 'ready', courses: (await res.json()) as ShellCourse[] });
    } catch (err) {
      setState({ kind: 'error', message: err instanceof Error ? err.message : 'Failed to load your courses' });
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  function signOut() {
    clearToken();
    navigate('/login');
  }

  function renderContent() {
    switch (state.kind) {
      case 'loading':
        // Render the page with an empty list; pages show their own no-course placeholder.
        return <Outlet context={{ courses: NO_COURSES } satisfies ShellContext} />;
      case 'forbidden':
        return (
          <Notice>
            This is a guest account — sign in with your NetID or university account to host.
          </Notice>
        );
      case 'error':
        return (
          <Notice>
            <p className="text-red-400">{state.message}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={() => void load()}>
              Retry
            </Button>
          </Notice>
        );
      case 'ready':
        if (state.courses.length === 0 && !EXEMPT_PATHS.has(pathname)) {
          return (
            <Notice>
              {isAdmin
                ? 'No courses exist yet — create one in the admin console.'
                : "You don't have HOST access to any course. Ask an administrator to grant HOST access before creating games or managing a roster."}
            </Notice>
          );
        }
        return <Outlet context={{ courses: state.courses } satisfies ShellContext} />;
    }
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-700 hover:text-slate-100'
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-700 bg-slate-900">
        <nav className="max-w-6xl mx-auto flex items-center gap-1 px-4 py-3 flex-wrap">
          <span className="text-white font-bold mr-4">Buzzer Host</span>
          <NavLink to="/home" className={linkClass}><Play size={16} /> Play</NavLink>
          <NavLink to="/games" className={linkClass}><Gamepad2 size={16} /> Games</NavLink>
          <NavLink to="/courses" className={linkClass}><Users size={16} /> Rosters</NavLink>
          <NavLink to="/sessions" className={linkClass}><History size={16} /> Sessions</NavLink>
          <div className="ml-auto flex items-center gap-1">
            {isAdmin && (
              <a
                href={`${ADMIN_APP_URL}/`}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-slate-100"
              >
                <Shield size={16} /> Admin console
              </a>
            )}
            <button
              onClick={signOut}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-slate-100"
            >
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </nav>
      </header>
      <main className="flex-1">{renderContent()}</main>
    </div>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-w-xl mx-auto mt-16 px-4 text-center text-slate-300">
      {children}
    </div>
  );
}
