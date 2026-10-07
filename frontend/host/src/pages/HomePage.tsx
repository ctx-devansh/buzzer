import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useShellCourses } from '../components/HostShell';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader } from '../components/ui/card';

interface Game { id: number; title: string }
interface ActiveSession {
  session_id: string;
  room_code: string;
  status: string;
  game_title: string;
  course_name: string;
  course_semester: string;
}

export default function HomePage() {
  // Course list comes from the shell (its sole /game/my-courses caller), after mount.
  const courses = useShellCourses();
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoaded, setGamesLoaded] = useState(false);
  const [gamesError, setGamesError] = useState('');
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [courseId, setCourseId] = useState<number | ''>('');
  const [gameId, setGameId] = useState<number | ''>('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<ActiveSession[]>('/game/my-active-sessions')
      .then(setActiveSessions)
      .catch(() => setError('Failed to load your active sessions.'));
  }, []);

  // Single-course auto-select, keyed on the shell's list (it arrives after mount, and
  // again if the shell's Retry refetch resolves).
  useEffect(() => {
    if (courses.length === 1) setCourseId(courses[0].id);
  }, [courses]);

  // Games are per course. Clear the selection first so a stale game can never
  // survive into a new course; no request until a course is chosen.
  useEffect(() => {
    setGameId('');
    setGames([]);
    setGamesLoaded(false);
    setGamesError('');
    if (courseId === '') return;
    let cancelled = false;
    api.get<Game[]>(`/game/my-games?course_id=${courseId}`)
      .then(g => {
        if (cancelled) return;
        setGames(g);
        setGamesLoaded(true);
        if (g.length === 1) setGameId(g[0].id);
      })
      .catch(err => {
        if (!cancelled) setGamesError(err instanceof Error ? err.message : 'Failed to load quizzes');
      });
    return () => { cancelled = true; };
  }, [courseId]);

  async function deleteSession(sessionId: string) {
    try {
      await api.delete(`/game/sessions/${sessionId}`);
      setActiveSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
    } finally {
      setConfirmDelete(null);
    }
  }

  async function createRoom() {
    if (!courseId || !gameId) return;
    setError('');
    setLoading(true);
    try {
      const data = await api.post<{ room_code: string }>('/game/rooms', {
        course_id: courseId,
        game_id: gameId,
      });
      navigate(`/game/${data.room_code}/lobby`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create room');
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center px-4 py-8 gap-4">
      {activeSessions.length > 0 && (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <h2 className="nb-h2 text-ink">Active Sessions</h2>
            <p className="text-ink-muted text-sm">You have running games — rejoin one or create a new room below.</p>
          </CardHeader>
          <CardContent className="space-y-2">
            {activeSessions.map(s => (
              <div
                key={s.session_id}
                className="flex items-center justify-between bg-surface-muted border-2 border-line px-4 py-3"
              >
                <div>
                  <p className="text-ink font-medium">{s.game_title}</p>
                  <p className="text-ink-muted text-sm">{s.course_name} · {s.course_semester}</p>
                  <p className="text-ink-muted text-xs mt-0.5">
                    Room <span className="font-mono text-ink-muted">{s.room_code}</span>
                    {' · '}
                    <span className={s.status === 'IN_PROGRESS' ? 'text-success-text' : 'text-warning-text'}>
                      {s.status === 'IN_PROGRESS' ? 'In Progress' : 'Lobby'}
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {confirmDelete === s.session_id ? (
                    <>
                      <span className="text-danger-text text-xs">Delete all data?</span>
                      <Button size="sm" variant="destructive" onClick={() => deleteSession(s.session_id)}>
                        Confirm
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={() => navigate(`/game/${s.room_code}/lobby`)}>
                        Rejoin
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => setConfirmDelete(s.session_id)}>
                        Delete
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card className="w-full max-w-lg">
        <CardHeader>
          <h1 className="nb-h1 text-ink">Create Game Room</h1>
          <p className="text-ink-muted text-sm mt-1">Select a course and quiz to begin</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink-muted mb-1">Course</label>
            <select
              value={courseId}
              onChange={e => setCourseId(e.target.value ? Number(e.target.value) : '')}
              className="w-full border-2 border-line bg-surface px-3 py-2 text-ink"
            >
              <option value="">Select a course…</option>
              {courses.map(c => (
                <option key={c.id} value={c.id}>{c.name} — {c.semester}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-muted mb-1">Quiz</label>
            <select
              value={gameId}
              onChange={e => setGameId(e.target.value ? Number(e.target.value) : '')}
              disabled={courseId === ''}
              className="w-full border-2 border-line bg-surface px-3 py-2 text-ink disabled:opacity-50"
            >
              <option value="">{courseId === '' ? 'Select a course first' : 'Select a quiz…'}</option>
              {games.map(g => (
                <option key={g.id} value={g.id}>{g.title}</option>
              ))}
            </select>
            {gamesLoaded && games.length === 0 && (
              <p className="text-ink-muted text-sm mt-1">No quizzes for this course yet — create one in Games.</p>
            )}
            {gamesError && <p className="text-danger-text text-sm mt-1">{gamesError}</p>}
          </div>
          {error && <p className="text-danger-text text-sm">{error}</p>}
          <Button
            className="w-full"
            size="lg"
            onClick={createRoom}
            disabled={!courseId || !gameId || loading}
          >
            {loading ? 'Creating room…' : 'Create Room'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
