"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { buildLandingAnalyzeHref } from "../../lib/queryInput";
import { useSpeechQuery } from "../../lib/useSpeechQuery";

function MicGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
      <path
        d="M12 14.5a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v4.5a3 3 0 0 0 3 3Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M8 11.2a4 4 0 0 0 8 0M12 15.2V18"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function LandingAsk() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [inputMethod, setInputMethod] = useState<"text" | "voice">("text");
  const [error, setError] = useState<string | null>(null);

  const speech = useSpeechQuery({
    value: query,
    onChange: setQuery,
    onError: setError,
    onClearError: () => setError(null),
    onVoiceOrigin: () => setInputMethod("voice"),
  });

  const href = buildLandingAnalyzeHref(query, inputMethod);

  function analyze() {
    if (!href) {
      setError("Enter a question (at least 3 characters), or tap the microphone.");
      return;
    }
    router.push(href);
  }

  if (speech.recording) {
    return (
      <div className="landing-ask is-listening">
        <p className="landing-listen-label" aria-live="polite">
          <span className="voice-rec-dot" /> Listening...
        </p>
        <p className="landing-listen-transcript">
          {query ? `“${query}”` : "Speak your payment question."}
        </p>
        <button type="button" className="btn btn-primary landing-ask-submit" onClick={speech.stopListening}>
          Stop
        </button>
      </div>
    );
  }

  return (
    <div className={`landing-ask ${speech.processing ? "is-processing" : ""}`}>
      <div className="landing-ask-row">
        <input
          className="landing-ask-input"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            if (inputMethod === "voice") {
              return;
            }
            setInputMethod("text");
          }}
          placeholder="Ask anything about your payment data..."
          aria-label="Payment research question"
          disabled={speech.busy}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              analyze();
            }
          }}
        />
        <button
          type="button"
          className={`voice-query-btn landing-mic ${speech.processing ? "is-processing" : ""} ${speech.state === "error" ? "is-error" : ""} ${speech.state === "success" ? "is-ready" : ""}`}
          onClick={speech.onMicClick}
          onPointerDown={speech.onMicPointerDown}
          onPointerUp={speech.onMicPointerUp}
          onPointerCancel={speech.onMicPointerUp}
          disabled={speech.busy}
          aria-label={speech.recording ? "Listening. Tap to stop" : "Tap to speak"}
          title="Tap to speak. Hold to speak. ⌘/Ctrl+Shift+V"
        >
          <span className="voice-query-icon" aria-hidden>
            {speech.processing ? <span className="voice-spinner" /> : <MicGlyph />}
          </span>
        </button>
      </div>
      {error ? (
        <p className="landing-ask-error" role="alert">
          {error}
        </p>
      ) : (
        <p className="landing-ask-hint">
          Tap the mic to speak. Hold is optional. Shortcut ⌘/Ctrl + Shift + V.
        </p>
      )}
      <button
        type="button"
        className="btn btn-primary landing-ask-submit"
        onClick={analyze}
        disabled={speech.busy || !href}
      >
        {inputMethod === "voice" && query.trim() ? "Analyze with PayIntel →" : "Analyze"}
      </button>
    </div>
  );
}
