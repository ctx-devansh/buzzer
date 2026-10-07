import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate, NavLink } from 'react-router-dom';
import { BookOpen, Users, Gamepad2, UserX, LogOut, History, ExternalLink, Play, Smartphone } from 'lucide-react';
import LoginPage from './pages/LoginPage';
import CoursesPage from './pages/CoursesPage';
import UsersPage from './pages/UsersPage';
import UserDetailPage from './pages/UserDetailPage';
import GuestsPage from './pages/GuestsPage';
import SessionsPage from './pages/SessionsPage';
import { ExternalRedirect } from './components/ExternalRedirect';
import { HOST_APP_URL, PLAYER_APP_URL } from './lib/links';
import { ThemeToggle } from './components/ThemeToggle';

// Builders for the routes that moved to the host app (module-level so their identity
// is stable across renders). Param names match the host app's routes.
const toHostGames = () => `${HOST_APP_URL}/games`;
const toHostQuestions = (p: { gameId?: string }) => `${HOST_APP_URL}/games/${p.gameId}/questions`;
const toHostRoster = (p: { courseId?: string }) => `${HOST_APP_URL}/courses/${p.courseId}/roster`;

function RequireAdmin() {
  const token = localStorage.getItem('token');
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function AdminLayout() {
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem('token');
    navigate('/login');
  }

  // Same border width active or not, so items don't shift. The active item is an accent fill and
  // sets text-on-fill explicitly (docs/design-better-ui.md §4.2).
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-4 py-2 text-sm font-semibold border-2 transition-colors ${
      isActive
        ? 'border-line bg-accent text-on-fill'
        : 'border-transparent text-ink hover:border-line hover:bg-surface-muted'
    }`;

  const externalClass =
    'flex items-center gap-3 px-4 py-2 text-sm text-ink-muted border-2 border-transparent hover:border-line hover:bg-surface-muted hover:text-ink transition-colors';

  return (
    // Admin is the compact density: 2px outlines, 2px shadows (§4.3.1).
    <div data-density="compact" className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-surface border-r-2 border-line flex flex-col">
        <div className="px-6 py-5 border-b-2 border-line">
          <p className="nb-h2 text-ink">Buzzer Admin</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <p className="nb-caption px-4 pt-1 pb-2">Administration</p>
          <NavLink to="/users" className={linkClass}>
            <Users size={16} /> Users
          </NavLink>
          <NavLink to="/courses" className={linkClass}>
            <BookOpen size={16} /> Courses
          </NavLink>
          <NavLink to="/guests" className={linkClass}>
            <UserX size={16} /> Guests
          </NavLink>

          <div className="my-3 border-t-2 border-line" />

          <p className="nb-caption px-4 pt-1">Host tools</p>
          <p className="px-4 pb-2 text-xs text-ink-muted">open the host app</p>
          <NavLink to="/sessions" className={linkClass}>
            <History size={16} /> Sessions
          </NavLink>
          <a href={`${HOST_APP_URL}/games`} className={externalClass}>
            <Gamepad2 size={16} /> Games <ExternalLink size={12} className="ml-auto" />
          </a>
          <a href={`${HOST_APP_URL}/courses`} className={externalClass}>
            <BookOpen size={16} /> Rosters &amp; images <ExternalLink size={12} className="ml-auto" />
          </a>
          <a href={`${HOST_APP_URL}/home`} className={externalClass}>
            <Play size={16} /> Host a game <ExternalLink size={12} className="ml-auto" />
          </a>
          <a href={`${PLAYER_APP_URL}/join`} className={externalClass}>
            <Smartphone size={16} /> Join as player <ExternalLink size={12} className="ml-auto" />
          </a>
        </nav>
        <div className="p-3 border-t-2 border-line space-y-2">
          <ThemeToggle className="w-full" />
          <button
            onClick={logout}
            className="flex items-center gap-3 px-4 py-2 text-sm font-semibold text-ink border-2 border-transparent hover:border-line hover:bg-surface-muted w-full transition-colors"
          >
            <LogOut size={16} /> Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAdmin />}>
          <Route element={<AdminLayout />}>
            <Route path="/users" element={<UsersPage />} />
            <Route path="/users/:userId" element={<UserDetailPage />} />
            <Route path="/courses" element={<CoursesPage />} />
            <Route path="/guests" element={<GuestsPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
          </Route>
        </Route>
        {/* Moved to the host app — redirect old bookmarks to the same resource there. */}
        <Route path="/games" element={<ExternalRedirect to={toHostGames} />} />
        <Route path="/games/:gameId/questions" element={<ExternalRedirect to={toHostQuestions} />} />
        <Route path="/courses/:courseId/roster" element={<ExternalRedirect to={toHostRoster} />} />
        <Route path="*" element={<Navigate to="/users" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
