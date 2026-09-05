"use client";

import { useSpeechQuery, type VoiceQueryState } from "../../lib/useSpeechQuery";

export type { VoiceQueryState };

type VoiceQueryButtonProps = {
  disabled?: boolean;
  value: string;
  speechLang?: string;
  onChange: (next: string) => void;
  onError: (message: string) => void;
  onClearError: () => void;
  onVoiceOrigin?: () => void;
  onBusyChange?: (busy: boolean) => void;
};

function statusCopy(state: VoiceQueryState, supported: boolean | null): string | null {
  if (supported === false) {
    return "Voice input is unavailable in this browser.";
  }
  switch (state) {
    case "requesting_permission":
      return "Allow microphone access…";
    case "recording":
      return "Listening...";
    case "processing":
      return "Transcribing...";
    case "success":
      return "Voice input • Edit before analyzing";
    case "error":
      return "Voice input failed. Type or tap the microphone again.";
    default:
      return null;
  }
}

function ariaLabel(state: VoiceQueryState): string {
  switch (state) {
    case "requesting_permission":
      return "Allow microphone access";
    case "recording":
      return "Listening. Tap to stop";
    case "processing":
      return "Transcribing";
    case "success":
      return "Tap to speak again";
    case "error":
      return "Tap to speak again";
    default:
      return "Tap to speak";
  }
}

function MicGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
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

export function VoiceQueryButton({
  disabled = false,
  value,
  speechLang = "en-IN",
  onChange,
  onError,
  onClearError,
  onVoiceOrigin,
  onBusyChange,
}: VoiceQueryButtonProps) {
  const speech = useSpeechQuery({
    value,
    speechLang,
    disabled,
    onChange,
    onError,
    onClearError,
    onVoiceOrigin,
    onBusyChange,
  });

  const status = statusCopy(speech.state, speech.supported);
  const showTip = speech.state === "idle" && speech.supported !== false;

  return (
    <>
      <button
        type="button"
        className={`voice-query-btn ${speech.recording ? "is-recording" : ""} ${speech.processing ? "is-processing" : ""} ${speech.state === "error" ? "is-error" : ""} ${speech.state === "success" ? "is-ready" : ""}`}
        onClick={speech.onMicClick}
        onPointerDown={speech.onMicPointerDown}
        onPointerUp={speech.onMicPointerUp}
        onPointerCancel={speech.onMicPointerUp}
        disabled={disabled || speech.busy}
        aria-label={ariaLabel(speech.state)}
        aria-pressed={speech.recording}
        aria-describedby={status ? "voice-query-status" : undefined}
        title={showTip ? "Tap to speak. Hold to speak. ⌘/Ctrl+Shift+V" : undefined}
      >
        <span className="voice-query-icon" aria-hidden>
          {speech.processing ? <span className="voice-spinner" /> : null}
          {speech.recording ? <span className="voice-rec-dot" /> : null}
          {speech.processing ? null : <MicGlyph />}
        </span>
        {showTip ? (
          <span className="voice-tip" role="tooltip">
            Tap to speak
          </span>
        ) : null}
      </button>
      {status ? (
        <p id="voice-query-status" className={`voice-query-status hint ${speech.state}`} aria-live="polite">
          {status}
        </p>
      ) : null}
    </>
  );
}
