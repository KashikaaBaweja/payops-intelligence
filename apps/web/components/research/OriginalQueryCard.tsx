import { languageLabel } from "../../lib/queryLanguage";

export function OriginalQueryCard({
  transcript,
  queryLanguage,
  inputMethod,
}: {
  transcript: string;
  queryLanguage?: string | null;
  inputMethod?: "text" | "voice";
}) {
  return (
    <div className="voice-run" aria-live="polite">
      <div className="original-query-chips">
        <span className="chip idle">Original query</span>
        {inputMethod === "voice" ? <span className="chip idle">Voice</span> : null}
      </div>
      <p className="voice-run-transcript">“{transcript}”</p>
      <dl className="kv original-query-meta">
        <dt>Language</dt>
        <dd>{languageLabel(queryLanguage)}</dd>
      </dl>
    </div>
  );
}
