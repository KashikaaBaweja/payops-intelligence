export function VoiceQueryBanner({ transcript }: { transcript: string }) {
  return (
    <div className="voice-run" aria-live="polite">
      <span className="chip idle">Voice Query</span>
      <p className="voice-run-transcript">“{transcript}”</p>
    </div>
  );
}
