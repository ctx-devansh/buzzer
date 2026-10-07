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

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-indigo-600 text-white'
        : 'text-slate-300 hover:bg-slate-700 hover:text-slate-100'
    }`;

  const externalClass =
    'flex items-center gap-3 px-4 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-700 hover:text-slate-100 transition-colors';

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-slate-900 border-r border-slate-700 flex flex-col">
        <div className="px-6 py-5 border-b border-slate-700">
          <h1 className="text-lg font-bold text-white">Buzzer Admin</h1>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <p className="px-4 pt-1 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Administration
          </p>
          <NavLink to="/users" className={linkClass}>
            <Users size={16} /> Users
          </NavLink>
          <NavLink to="/courses" className={linkClass}>
            <BookOpen size={16} /> Courses
          </NavLink>
          <NavLink to="/guests" className={linkClass}>
            <UserX size={16} /> Guests
          </NavLink>

          <div className="my-3 border-t border-slate-700" />

          <p className="px-4 pt-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Host tools
          </p>
          <p className="px-4 pb-2 text-xs text-slate-500">open the host app</p>
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
        <div className="p-3 border-t border-slate-700 space-y-2">
          <ThemeToggle className="w-full" />
          <button
            onClick={logout}
            className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-slate-100 w-full transition-colors"
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
