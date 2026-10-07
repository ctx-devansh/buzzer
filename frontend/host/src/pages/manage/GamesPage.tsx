import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, List, Upload, Trash2, Pencil, Link2 } from 'lucide-react';
import { api } from '../../lib/api';
import { getRole } from '../../lib/auth';
import { useShellCourses, type ShellCourse } from '../../components/HostShell';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader } from '../../components/ui/card';
import { Input } from '../../components/ui/input';

interface Game {
  id: number;
  title: string;
  description: string;
  max_players: number;
  course_id: number | null;
  course_name: string | null;
  created_at: string;
}

const selectClass =
  'w-full border-2 border-line bg-surface px-3 py-2 text-ink';

function CourseSelect({ courses, value, onChange, placeholder }: {
  courses: ShellCourse[];
  value: number | '';
  onChange: (v: number | '') => void;
  placeholder: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : '')}
      className={selectClass}
    >
      <option value="">{placeholder}</option>
      {courses.map((c) => (
        <option key={c.id} value={c.id}>{c.name} — {c.semester}</option>
      ))}
    </select>
  );
}

export default function GamesPage() {
  const courses = useShellCourses();
  const isAdmin = getRole() === 'ADMIN';
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // '' = "All courses": the only request shape that returns unattached games to an ADMIN.
  const [filterCourseId, setFilterCourseId] = useState<number | ''>('');
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [maxPlayers, setMaxPlayers] = useState('150');
  const [formCourseId, setFormCourseId] = useState<number | ''>('');
  const [saving, setSaving] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importCourseId, setImportCourseId] = useState<number | ''>('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [editingGame, setEditingGame] = useState<Game | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editMaxPlayers, setEditMaxPlayers] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [attachCourse, setAttachCourse] = useState<Record<number, number | ''>>({});
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);
  // Bumped per list request so a slow response for an earlier filter can't overwrite
  // the list for the filter now selected.
  const loadSeq = useRef(0);
  const navigate = useNavigate();

  async function load(courseId: number | '' = filterCourseId) {
    const seq = ++loadSeq.current;
    setError('');
    try {
      // With a course this is gated, not merely filtered: a course the user cannot
      // host is a 403 (unreachable from the select, which only lists HOST courses).
      const path = courseId === '' ? '/host/games' : `/host/games?course_id=${courseId}`;
      const data = await api.get<Game[]>(path);
      if (seq === loadSeq.current) setGames(data);
    } catch (err) {
      if (seq !== loadSeq.current) return;
      setGames([]);
      setError(err instanceof Error ? err.message : 'Failed to load games');
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }

  useEffect(() => { void load(filterCourseId); }, [filterCourseId]);

  // The forms' course selects start from the filter when opened, then are independent:
  // changing the filter never overwrites or clears a course picked in an open form.
  function openCreate() {
    if (!showForm) setFormCourseId(filterCourseId);
    setShowForm(!showForm);
  }

  function openImport() {
    if (!showImport) {
      setImportCourseId(filterCourseId);
      setImportFile(null);
    }
    setShowImport(!showImport);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (formCourseId === '') return;
    setSaving(true);
    setError('');
    try {
      await api.post('/host/games', {
        title,
        description,
        max_players: Number(maxPlayers),
        course_id: formCourseId,
      });
      setTitle(''); setDescription(''); setMaxPlayers('150'); setFormCourseId('');
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create game');
    } finally {
      setSaving(false);
    }
  }

  function startEdit(g: Game) {
    setEditingGame(g);
    setEditTitle(g.title);
    setEditDescription(g.description);
    setEditMaxPlayers(String(g.max_players));
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingGame) return;
    setEditSaving(true);
    setError('');
    try {
      // HostGameUpdate: never carries course_id (a 422 if it did).
      await api.put(`/host/games/${editingGame.id}`, {
        title: editTitle,
        description: editDescription,
        max_players: Number(editMaxPlayers),
      });
      setEditingGame(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update game');
    } finally {
      setEditSaving(false);
    }
  }

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    if (!importFile || importCourseId === '') return;
    setImporting(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', importFile);
      form.append('course_id', String(importCourseId));
      const result = await api.postForm<{ game_id: number }>('/host/games/import', form);
      navigate(`/games/${result.game_id}/questions`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
      // Clear both together, or Import stays enabled with an empty-looking picker.
      setImportFile(null);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function attachGame(id: number) {
    const courseId = attachCourse[id];
    if (!courseId) return;
    setRowErrors((prev) => ({ ...prev, [id]: '' }));
    try {
      // Admin-only route; re-render the row from the response body's course fields.
      const updated = await api.put<Game>(`/admin/games/${id}`, { course_id: courseId });
      setGames((prev) => prev.map((g) => (g.id === id ? updated : g)));
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [id]: err instanceof Error ? err.message : 'Attach failed' }));
    }
  }

  async function deleteGame(id: number) {
    if (!confirm('Delete this game and all its sessions? This cannot be undone.')) return;
    try {
      await api.delete(`/admin/games/${id}`);
      setGames((prev) => prev.filter((g) => g.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete game');
    }
  }

  return (
    <div className="nb-page max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="nb-h1 text-ink">Games</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={openImport}>
            <Upload size={14} className="mr-1" /> Import JSON
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus size={16} className="mr-1" /> New Game
          </Button>
        </div>
      </div>

      <div className="mb-6 max-w-xs">
        <label className="block text-xs text-ink-muted mb-1">Course</label>
        <select
          value={filterCourseId}
          onChange={(e) => setFilterCourseId(e.target.value ? Number(e.target.value) : '')}
          className={selectClass}
        >
          <option value="">All courses</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.name} — {c.semester}</option>
          ))}
        </select>
      </div>

      {error && <p className="text-danger-text mb-4 text-sm">{error}</p>}

      {showImport && (
        <Card className="mb-6">
          <CardHeader><h2 className="nb-h3 text-ink">Import Game JSON</h2></CardHeader>
          <CardContent>
            <form onSubmit={handleImport} className="space-y-3">
              <div>
                <label className="block text-xs text-ink-muted mb-1">Course (required)</label>
                <CourseSelect courses={courses} value={importCourseId} onChange={setImportCourseId} placeholder="Select a course…" />
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".json"
                onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
                className="block text-sm text-ink-muted"
              />
              <div className="flex gap-3">
                <Button type="submit" disabled={importing || !importFile || importCourseId === ''}>
                  {importing ? 'Importing…' : 'Import'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setShowImport(false)}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card className="mb-6">
          <CardHeader><h2 className="nb-h3 text-ink">Create Game</h2></CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-3">
              <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
              <textarea
                placeholder="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full border-2 border-line bg-surface px-3 py-2 text-ink resize-none"
                rows={3}
              />
              <div>
                <label className="block text-xs text-ink-muted mb-1">Max players</label>
                <Input
                  type="number"
                  value={maxPlayers}
                  onChange={(e) => setMaxPlayers(e.target.value)}
                  min="1"
                  max="500"
                />
              </div>
              <div>
                <label className="block text-xs text-ink-muted mb-1">Course (required)</label>
                <CourseSelect courses={courses} value={formCourseId} onChange={setFormCourseId} placeholder="Select a course…" />
              </div>
              <div className="flex gap-3">
                <Button type="submit" disabled={saving || formCourseId === ''}>{saving ? 'Creating…' : 'Create'}</Button>
                <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {editingGame && (
        <Card className="mb-6">
          <CardHeader><h2 className="nb-h3 text-ink">Edit Game</h2></CardHeader>
          <CardContent>
            <form onSubmit={handleEdit} className="space-y-3">
              <Input placeholder="Title" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} required />
              <textarea
                placeholder="Description (optional)"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="w-full border-2 border-line bg-surface px-3 py-2 text-ink resize-none"
                rows={3}
              />
              <div>
                <label className="block text-xs text-ink-muted mb-1">Max players</label>
                <Input
                  type="number"
                  value={editMaxPlayers}
                  onChange={(e) => setEditMaxPlayers(e.target.value)}
                  min="1"
                  max="500"
                />
              </div>
              <div className="flex gap-3">
                <Button type="submit" disabled={editSaving}>{editSaving ? 'Saving…' : 'Save'}</Button>
                <Button type="button" variant="ghost" onClick={() => setEditingGame(null)}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <p className="text-ink-muted">Loading…</p>
      ) : games.length === 0 ? (
        <p className="text-ink-muted">No games yet.</p>
      ) : (
        <div className="space-y-3">
          {games.map((g) => (
            <Card key={g.id} className="px-6 py-4">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-semibold text-ink">{g.title}</p>
                  {g.course_id === null ? (
                    <p className="text-warning-text text-sm mt-0.5">Unattached (admin only)</p>
                  ) : (
                    <p className="text-ink text-sm font-semibold mt-0.5">{g.course_name}</p>
                  )}
                  {g.description && <p className="text-ink-muted text-sm mt-0.5 line-clamp-1">{g.description}</p>}
                  <p className="text-ink-muted text-xs mt-0.5">Max {g.max_players} players</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => startEdit(g)}
                  >
                    <Pencil size={14} />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate(`/games/${g.id}/questions`)}
                  >
                    <List size={14} className="mr-1" /> Questions
                  </Button>
                  {isAdmin && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => void deleteGame(g.id)}
                    >
                      <Trash2 size={14} />
                    </Button>
                  )}
                </div>
              </div>
              {isAdmin && g.course_id === null && (
                <div className="flex items-center gap-2 mt-3">
                  <div className="flex-1 max-w-xs">
                    <CourseSelect
                      courses={courses}
                      value={attachCourse[g.id] ?? ''}
                      onChange={(v) => setAttachCourse((prev) => ({ ...prev, [g.id]: v }))}
                      placeholder="Attach to course…"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!attachCourse[g.id]}
                    onClick={() => void attachGame(g.id)}
                  >
                    <Link2 size={14} className="mr-1" /> Attach
                  </Button>
                </div>
              )}
              {rowErrors[g.id] && <p className="text-danger-text text-sm mt-2">{rowErrors[g.id]}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
