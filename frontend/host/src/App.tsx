import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import GameLayout from './pages/game/GameLayout';
import LobbyPage from './pages/game/LobbyPage';
import QuestionPage from './pages/game/QuestionPage';
import ResultsPage from './pages/game/ResultsPage';
import GameOverPage from './pages/game/GameOverPage';
import GamesPage from './pages/manage/GamesPage';
import QuestionEditorPage from './pages/manage/QuestionEditorPage';
import RosterPage from './pages/manage/RosterPage';
import ImagesPage from './pages/manage/ImagesPage';
import CoursesPage from './pages/manage/CoursesPage';
import SessionsPage from './pages/manage/SessionsPage';
import HostShell from './components/HostShell';
import { getToken } from './lib/auth';

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {/* Management routes share the top-nav shell; the game screens below stay full-screen (projector). */}
        <Route element={<RequireAuth><HostShell /></RequireAuth>}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/games" element={<GamesPage />} />
          <Route path="/games/:gameId/questions" element={<QuestionEditorPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:courseId/roster" element={<RosterPage />} />
          <Route path="/courses/:courseId/images" element={<ImagesPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
        </Route>
        <Route path="/game/:code" element={<RequireAuth><GameLayout /></RequireAuth>}>
          <Route path="lobby" element={<LobbyPage />} />
          <Route path="question" element={<QuestionPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="gameover" element={<GameOverPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
