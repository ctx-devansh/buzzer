import { useEffect, useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

// Shape of AdminSessionItem (backend/app/schemas/admin.py). The id is `session_id`, a str.
interface SessionItem {
  session_id: string;
  room_code: string;
  status: string;
  game_title: string;
  course_name: string;
  course_semester: string;
  created_at: string;
  player_count: number;
}

// No "Active" option: session_status has no ACTIVE member, and live sessions are
// already listed (with Rejoin) on /home. '' = All (omits the param).
const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'ABANDONED', label: 'Abandoned' },
];

const statusClass: Record<string, string> = {
  COMPLETED: 'text-success-text',
  ABANDONED: 'text-ink-muted',
  IN_PROGRESS: 'text-warning-text',
  LOBBY: 'text-warning-text',
};

/** My sessions (all hosts' for ADMIN) with HTML summary and CSV score downloads. */
export default function SessionsPage() {
  const [status, setStatus] = useState('COMPLETED');
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    // Ignore a response for a filter that is no longer selected, and never leave the
    // previous filter's rows (with live download buttons) under the new filter.
    let cancelled = false;
    setLoading(true);
    setError('');
    setSessions([]);
    setRowErrors({});
    api.get<SessionItem[]>(status ? `/host/sessions?status=${status}` : '/host/sessions')
      .then((data) => { if (!cancelled) setSessions(data); })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load sessions');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [status]);

  async function download(sessionId: string, path: string, key: string) {
    setDownloading(key);
    setRowErrors((prev) => ({ ...prev, [sessionId]: '' }));
    try {
      await api.download(path);
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [sessionId]: err instanceof Error ? err.message : 'Download failed' }));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="nb-page max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="nb-h1 text-ink">Sessions</h1>
        <div className="flex gap-1">
          {STATUS_OPTIONS.map((o) => (
            <Button
              key={o.label}
              size="sm"
              variant={status === o.value ? 'default' : 'ghost'}
              onClick={() => setStatus(o.value)}
            >
              {o.label}
            </Button>
          ))}
        </div>
      </div>

      {error && <p className="text-danger-text mb-4 text-sm">{error}</p>}

      {loading ? (
        <p className="text-ink-muted">Loading…</p>
      ) : sessions.length === 0 ? (
        <p className="text-ink-muted">No sessions.</p>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => {
            const completed = s.status === 'COMPLETED';
            return (
              <Card key={s.session_id} className="px-6 py-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{s.game_title}</p>
                    <p className="text-ink-muted text-sm">{s.course_name} · {s.course_semester}</p>
                    <p className="text-ink-muted text-xs mt-0.5">
                      Room <span className="font-mono text-ink-muted">{s.room_code}</span>
                      {' · '}{new Date(s.created_at).toLocaleString()}
                      {' · '}{s.player_count} player{s.player_count !== 1 ? 's' : ''}
                      {' · '}<span className={statusClass[s.status] ?? 'text-ink-muted'}>{s.status}</span>
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!completed || downloading !== null}
                      onClick={() => void download(s.session_id, `/host/sessions/${s.session_id}/report`, `${s.session_id}:html`)}
                    >
                      <FileText size={14} className="mr-1" />
                      {downloading === `${s.session_id}:html` ? 'Downloading…' : 'Summary (HTML)'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!completed || downloading !== null}
                      onClick={() => void download(s.session_id, `/game/sessions/${s.session_id}/export`, `${s.session_id}:csv`)}
                    >
                      <Download size={14} className="mr-1" />
                      {downloading === `${s.session_id}:csv` ? 'Downloading…' : 'Scores (CSV)'}
                    </Button>
                  </div>
                </div>
                {rowErrors[s.session_id] && <p className="text-danger-text text-sm mt-2">{rowErrors[s.session_id]}</p>}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
