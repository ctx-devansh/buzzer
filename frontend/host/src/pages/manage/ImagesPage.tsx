import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Upload } from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import { prepareUpload } from '../../lib/imageFile';
import {
  formatBytes,
  imageUrl,
  questionLabel,
  type ImageReplaceResult,
  type LibraryImage,
} from '../../lib/images';
import { useShellCourses } from '../../components/HostShell';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';

/** A played Pin the Spot canvas can't be replaced: its taps are positions on it. */
function isPlayedCanvas(img: LibraryImage): boolean {
  return img.used_by.some((u) => u.played && u.roles.includes('canvas'));
}

/** Replacing a played prompt or option image changes what past results show (decision 7). */
function changesHistory(img: LibraryImage): boolean {
  return img.used_by.some((u) => u.played && (u.roles.includes('prompt') || u.roles.includes('option')));
}

interface CardNotice { kind: 'error' | 'warning'; text: string }

function replaceNotice(before: LibraryImage, after: ImageReplaceResult): CardNotice | null {
  if (!after.size_changed || after.resized_question_ids.length === 0) return null;
  const label = (qid: number) => {
    const use = before.used_by.find((u) => u.question_id === qid);
    return use ? questionLabel(use) : `question ${qid}`;
  };
  let text =
    `The image size changed. Check the target of ${after.resized_question_ids.map(label).join('; ')}.`;
  if (after.clamped_question_ids.length) {
    text += ` Radius reduced to fit the new image: ${after.clamped_question_ids.map(label).join('; ')}.`;
  }
  return { kind: 'warning', text };
}

/**
 * The course image library (docs/design-image-support.md §5.1): upload, view, replace and
 * delete. Course-wide: every HOST of the course (and ADMIN) manages every image.
 */
export default function ImagesPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const courses = useShellCourses();
  const course = courses.find((c) => String(c.id) === courseId);

  const [images, setImages] = useState<LibraryImage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [viewing, setViewing] = useState<LibraryImage | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; action: 'delete' | 'replace' } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notices, setNotices] = useState<Record<string, CardNotice>>({});
  // A local cache-buster per image, bumped on each successful replace: within one
  // document the browser may reuse the old bytes for the same URL, and updated_at has
  // one-second resolution, so it can't serve (design §5.1). Other viewers rely on ETag.
  const [replaceCount, setReplaceCount] = useState<Record<string, number>>({});
  const src = (img: LibraryImage) => imageUrl(img.id, replaceCount[img.id]);
  const replaceInputs = useRef<Record<string, HTMLInputElement | null>>({});

  async function load() {
    try {
      setImages(await api.get<LibraryImage[]>(`/host/courses/${courseId}/images`));
      setLoaded(true);
    } catch (err) {
      setLoadError(
        err instanceof ApiError && err.status === 403
          ? "You don't have HOST access to this course"
          : err instanceof Error ? err.message : 'Failed to load images',
      );
    }
  }

  useEffect(() => { void load(); }, [courseId]);

  function setNotice(id: string, notice: CardNotice | null) {
    setNotices((prev) => {
      const next = { ...prev };
      if (notice) next[id] = notice;
      else delete next[id];
      return next;
    });
  }

  async function uploadFiles(files: File[]) {
    setUploading(true);
    setUploadErrors([]);
    const errors: string[] = [];
    for (const file of files) {
      try {
        const form = new FormData();
        form.append('file', await prepareUpload(file));
        await api.postForm(`/host/courses/${courseId}/images`, form);
      } catch (err) {
        errors.push(`${file.name}: ${err instanceof Error ? err.message : 'upload failed'}`);
      }
    }
    setUploadErrors(errors);
    setUploading(false);
    await load();
  }

  async function replaceImage(img: LibraryImage, file: File) {
    setBusy(img.id);
    setNotice(img.id, null);
    try {
      const form = new FormData();
      form.append('file', await prepareUpload(file));
      const result = await api.putForm<ImageReplaceResult>(`/host/courses/${courseId}/images/${img.id}`, form);
      setNotice(img.id, replaceNotice(img, result));
      setReplaceCount((prev) => ({ ...prev, [img.id]: (prev[img.id] ?? 0) + 1 }));
      await load();
    } catch (err) {
      setNotice(img.id, { kind: 'error', text: err instanceof Error ? err.message : 'Replace failed' });
    } finally {
      setBusy(null);
    }
  }

  async function deleteImage(img: LibraryImage) {
    setBusy(img.id);
    setConfirm(null);
    try {
      await api.delete(`/host/courses/${courseId}/images/${img.id}`);
      setImages((prev) => prev.filter((i) => i.id !== img.id));
    } catch (err) {
      // A 409 race (someone used it meanwhile) shows the server's message.
      setNotice(img.id, { kind: 'error', text: err instanceof Error ? err.message : 'Delete failed' });
      await load();
    } finally {
      setBusy(null);
    }
  }

  function startReplace(img: LibraryImage) {
    if (changesHistory(img) && confirm?.id !== img.id) {
      setConfirm({ id: img.id, action: 'replace' });
      return;
    }
    setConfirm(null);
    replaceInputs.current[img.id]?.click();
  }

  const backLink = (
    <button
      onClick={() => navigate('/courses')}
      className="flex items-center gap-2 text-ink-muted hover:text-ink text-sm mb-2"
    >
      <ArrowLeft size={14} /> Back to Courses
    </button>
  );

  if (!loaded) {
    return (
      <div className="nb-page nb-stack max-w-5xl mx-auto">
        {backLink}
        {loadError ? <p className="text-danger-text text-sm">{loadError}</p> : <p className="text-ink-muted">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="nb-page nb-stack max-w-5xl mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          {backLink}
          <h1 className="nb-h1 text-ink">Images</h1>
          {course && <p className="text-ink text-sm font-semibold mt-0.5">{course.name} · {course.semester}</p>}
          <p className="text-ink-muted text-sm mt-0.5">
            Shared by every host of this course. Use them as question prompts, answer options and Pin the Spot maps.
          </p>
        </div>
        <label className="nb-box nb-press inline-flex shrink-0 items-center bg-accent px-3 py-1.5 text-sm font-display font-bold text-on-fill cursor-pointer">
          <Upload size={14} className="mr-1" /> {uploading ? 'Uploading…' : 'Upload images'}
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/gif,image/webp"
            className="hidden"
            data-testid="library-upload"
            disabled={uploading}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = '';
              if (files.length) void uploadFiles(files);
            }}
          />
        </label>
      </div>

      {uploadErrors.length > 0 && (
        <ul className="text-danger-text text-sm space-y-1">
          {uploadErrors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}

      {images.length === 0 ? (
        <p className="text-ink-muted">No images yet. Upload PNG, JPEG, GIF or WebP files up to 5 MB.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {images.map((img) => {
            const uses = img.used_by;
            const playedCanvas = isPlayedCanvas(img);
            const notice = notices[img.id];
            const confirming = confirm?.id === img.id ? confirm.action : null;
            return (
              <Card key={img.id} className="p-3 space-y-2" data-testid="library-image">
                <button
                  type="button"
                  onClick={() => setViewing(img)}
                  className="block w-full bg-canvas"
                  aria-label={`View ${img.filename} at full size`}
                >
                  {/* Full images scaled by CSS; lazy, in a fixed box so the grid doesn't jump. */}
                  <img
                    src={src(img)}
                    alt={img.filename}
                    loading="lazy"
                    decoding="async"
                    className="h-40 w-full bg-image-bg object-contain"
                  />
                </button>
                <div className="flex items-center gap-2">
                  <p className="flex-1 truncate text-sm font-medium text-ink" title={img.filename}>{img.filename}</p>
                  {playedCanvas && (
                    <span className="nb-chip bg-warning text-on-fill">Played</span>
                  )}
                </div>
                <p className="text-xs text-ink-muted">
                  {img.width} × {img.height} · {formatBytes(img.byte_size)}
                  {img.uploaded_by_name && ` · ${img.uploaded_by_name}`}
                </p>
                {uses.length > 0 ? (
                  <div className="text-xs">
                    <button
                      type="button"
                      className="text-ink underline decoration-line decoration-2 underline-offset-2 hover:decoration-accent"
                      onClick={() => setExpanded(expanded === img.id ? null : img.id)}
                    >
                      Used in {uses.length} question{uses.length !== 1 ? 's' : ''}
                    </button>
                    {expanded === img.id && (
                      <ul className="mt-1 space-y-0.5 text-ink-muted">
                        {uses.map((u) => (
                          <li key={u.question_id}>
                            <Link to={`/games/${u.game_id}/questions`} className="hover:text-ink hover:underline">
                              {questionLabel(u)}
                            </Link>{' '}
                            ({u.roles.join(', ')}){u.played && ' · played'}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-ink-muted">Used in 0 questions</p>
                )}

                {notice && (
                  <p className={`text-xs ${notice.kind === 'error' ? 'text-danger-text' : 'text-warning-text'}`}>{notice.text}</p>
                )}

                {confirming === 'delete' && (
                  <div className="flex items-center gap-2 text-xs text-ink-muted">
                    Delete this image?
                    <Button size="sm" variant="destructive" onClick={() => void deleteImage(img)} data-testid="library-confirm-delete">Delete</Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
                  </div>
                )}
                {confirming === 'replace' && (
                  <div className="space-y-1 text-xs text-warning-text">
                    <p>Past results of played questions will show the new image.</p>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => startReplace(img)}>Choose new file</Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <span
                    title={
                      playedCanvas
                        ? 'This image is the canvas of a Pin the Spot question that has been played. Upload a new image instead.'
                        : undefined
                    }
                  >
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={playedCanvas || busy === img.id}
                      onClick={() => startReplace(img)}
                    >
                      Replace
                    </Button>
                  </span>
                  <input
                    ref={(el) => { replaceInputs.current[img.id] = el; }}
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    className="hidden"
                    data-testid="library-replace"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = '';
                      if (file) void replaceImage(img, file);
                    }}
                  />
                  <span title={uses.length ? `Used in ${uses.length} question${uses.length !== 1 ? 's' : ''}` : undefined}>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={uses.length > 0 || busy === img.id}
                      onClick={() => setConfirm({ id: img.id, action: 'delete' })}
                    >
                      Delete
                    </Button>
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {viewing && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/80 p-6"
          role="dialog"
          aria-modal="true"
          aria-label={viewing.filename}
          onClick={() => setViewing(null)}
        >
          <img
            src={src(viewing)}
            alt={viewing.filename}
            className="max-h-full max-w-full border-2 border-line bg-image-bg object-contain"
          />
        </div>
      )}
    </div>
  );
}
