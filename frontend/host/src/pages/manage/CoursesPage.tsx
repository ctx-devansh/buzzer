import { useNavigate } from 'react-router-dom';
import { Image as ImageIcon, Users } from 'lucide-react';
import { useShellCourses } from '../../components/HostShell';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

/**
 * Read-only list of the user's HOST courses (from the shell), each with its roster and
 * image library. Course creation is admin-side.
 */
export default function CoursesPage() {
  const courses = useShellCourses();
  const navigate = useNavigate();

  return (
    <div className="nb-page max-w-4xl mx-auto">
      <h1 className="nb-h1 text-ink mb-6">Courses</h1>
      {courses.length === 0 ? (
        <p className="text-ink-muted">Loading…</p>
      ) : (
        <div className="space-y-3">
          {courses.map((c) => (
            <Card key={c.id} className="flex items-center justify-between px-6 py-4">
              <div>
                <p className="font-semibold text-ink">{c.name}</p>
                <p className="text-ink-muted text-sm">{c.semester}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => navigate(`/courses/${c.id}/roster`)}>
                  <Users size={14} className="mr-1" /> Manage roster
                </Button>
                <Button variant="outline" size="sm" onClick={() => navigate(`/courses/${c.id}/images`)}>
                  <ImageIcon size={14} className="mr-1" /> Images
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
