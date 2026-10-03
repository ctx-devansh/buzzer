import { useNavigate } from 'react-router-dom';
import { Users } from 'lucide-react';
import { useShellCourses } from '../../components/HostShell';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

/** Read-only list of the user's HOST courses (from the shell). Course creation is admin-side. */
export default function CoursesPage() {
  const courses = useShellCourses();
  const navigate = useNavigate();

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-100 mb-6">Rosters</h2>
      {courses.length === 0 ? (
        <p className="text-slate-400">Loading…</p>
      ) : (
        <div className="space-y-3">
          {courses.map((c) => (
            <Card key={c.id} className="flex items-center justify-between px-6 py-4">
              <div>
                <p className="font-semibold text-slate-100">{c.name}</p>
                <p className="text-slate-400 text-sm">{c.semester}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate(`/courses/${c.id}/roster`)}>
                <Users size={14} className="mr-1" /> Manage roster
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
