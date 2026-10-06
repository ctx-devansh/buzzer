import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api } from '../lib/api';
import { prepareUpload } from '../lib/imageFile';
import { imageUrl, type LibraryImage } from '../lib/images';
import { Button } from './ui/button';

/** Upload one file to a course library; shared by the picker and the editor's Pin "Choose file". */
export async function uploadToLibrary(courseId: number, file: File): Promise<LibraryImage> {
  const form = new FormData();
  form.append('file', await prepareUpload(file));
  return api.postForm<LibraryImage>(`/host/courses/${courseId}/images`, form);
}

/**
 * Modal over a course's image library (docs/design-image-support.md §5.2): pick an
 * existing image or upload a new one. Returns the whole ImageResponse so callers have
 * the size too (Pin the Spot needs it for the target picker and slider bounds).
 */
export function ImagePicker({
  courseId,
  onPick,
  onClose,
}: {
  courseId: number;
  onPick: (image: LibraryImage) => void;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<'library' | 'upload'>('library');
  const [images, setImages] = useState<LibraryImage[] | null>(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api
      .get<LibraryImage[]>(`/host/courses/${courseId}/images`)
      .then((list) => {
        setImages(list);
        if (list.length === 0) setTab('upload');
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load images'));
  }, [courseId]);

  async function upload(file: File) {
    setUploading(true);
    setError('');
    try {
      onPick(await uploadToLibrary(courseId, file));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  const tabClass = (active: boolean) =>
    `px-3 py-1.5 text-sm rounded-lg ${active ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-200'}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Choose an image"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[85vh] overflow-auto rounded-xl border border-slate-700 bg-slate-900 p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <button type="button" className={tabClass(tab === 'library')} onClick={() => setTab('library')}>
              Course library
            </button>
            <button type="button" className={tabClass(tab === 'upload')} onClick={() => setTab('upload')}>
              Upload new
            </button>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-100">
            <X size={18} />
          </button>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        {tab === 'library' &&
          (images === null ? (
            !error && <p className="text-slate-400 text-sm">Loading…</p>
          ) : images.length === 0 ? (
            <p className="text-slate-400 text-sm">This course has no images yet.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="picker-grid">
              {images.map((img) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => onPick(img)}
                  className="rounded-lg border border-slate-700 bg-slate-800 p-2 text-left hover:border-indigo-500"
                  data-testid="picker-image"
                >
                  {/* Full images scaled by CSS; lazy, in a fixed box so the grid doesn't jump. */}
                  <img
                    src={imageUrl(img.id)}
                    alt={img.filename}
                    loading="lazy"
                    decoding="async"
                    className="h-24 w-full object-contain"
                  />
                  <p className="mt-1 truncate text-xs text-slate-300">{img.filename}</p>
                  <p className="text-xs text-slate-500">
                    {img.width} × {img.height}
                  </p>
                </button>
              ))}
            </div>
          ))}

        {tab === 'upload' && (
          <div className="space-y-2">
            <label className="inline-flex items-center rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 cursor-pointer">
              {uploading ? 'Uploading…' : 'Choose a file…'}
              <input
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                className="hidden"
                data-testid="picker-file"
                disabled={uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = '';
                  if (file) void upload(file);
                }}
              />
            </label>
            <p className="text-slate-500 text-xs">
              PNG, JPEG, GIF or WebP up to 5 MB. Photos are scaled down to 1280 px. The image joins the
              course library, where every host of the course can use it. Anyone with an image's link can
              see it, so don't upload anything private.
            </p>
          </div>
        )}

        <div className="flex justify-end">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
