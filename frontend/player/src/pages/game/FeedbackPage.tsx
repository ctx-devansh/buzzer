export default function FeedbackPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 gap-6 text-center">
      <div className="nb-hero" aria-hidden="true">🔒</div>
      <p className="nb-h2 text-ink">Answer locked in!</p>
      <div className="flex justify-center mt-2">
        <div className="w-8 h-8 border-4 border-shadow border-t-accent rounded-full animate-spin" />
      </div>
      <p className="text-ink-muted text-sm">Waiting for host to reveal results…</p>
    </div>
  );
}
