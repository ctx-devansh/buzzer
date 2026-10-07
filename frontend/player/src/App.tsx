import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import JoinPage from './pages/JoinPage';
import LoginPage from './pages/LoginPage';
import NamePage from './pages/NamePage';
import GameLayout from './pages/game/GameLayout';
import LobbyPage from './pages/game/LobbyPage';
import QuestionPage from './pages/game/QuestionPage';
import FeedbackPage from './pages/game/FeedbackPage';
import ResultsPage from './pages/game/ResultsPage';
import GameOverPage from './pages/game/GameOverPage';
import { ThemeToggle } from './components/ThemeToggle';

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      {/* Layout contract (docs/design-better-ui.md §4.11): a flex chain, no percentage heights.
          Pages are direct flex children of <main> and size themselves with flex-1. */}
      <div className="flex h-[100dvh] flex-col">
        <header className="flex h-14 shrink-0 items-center justify-end px-3 pt-[env(safe-area-inset-top)]">
          <ThemeToggle showLabel={false} />
        </header>
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <Routes>
            <Route path="/join" element={<JoinPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/name/:code" element={<NamePage />} />
            <Route path="/game/:code" element={<GameLayout />}>
              <Route path="lobby" element={<LobbyPage />} />
              <Route path="question" element={<QuestionPage />} />
              <Route path="feedback" element={<FeedbackPage />} />
              <Route path="results" element={<ResultsPage />} />
              <Route path="gameover" element={<GameOverPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/join" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
