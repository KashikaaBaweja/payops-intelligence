export type SpeechErrorCode =
  | "not-supported"
  | "not-allowed"
  | "unavailable"
  | "no-speech"
  | "audio-capture"
  | "network"
  | "aborted"
  | string;

export type SpeechSessionHandlers = {
  onListening: () => void;
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (code: SpeechErrorCode) => void;
  onEnded: (finalText: string) => void;
};

export type SpeechSession = {
  start: () => Promise<void>;
  stop: () => void;
  abort: () => void;
};

export function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognitionCtor() !== null;
}

const SPEECH_UI_MESSAGES: Record<string, string> = {
  "not-supported": "This browser does not support tap-to-speak. Type the question instead.",
  "not-allowed":
    "Microphone permission was denied. Allow access in the browser, then tap to speak again.",
  "service-not-allowed":
    "Microphone permission was denied. Allow access in the browser, then tap to speak again.",
  "audio-capture":
    "No microphone is available. Connect a microphone and try again, or type the question.",
  unavailable:
    "No microphone is available. Connect a microphone and try again, or type the question.",
  "no-speech": "No speech was detected. Tap to speak and try again.",
  network: "Speech recognition lost its connection. Check the network and try again.",
};

export function messageForSpeechError(code: SpeechErrorCode): string {
  return (
    SPEECH_UI_MESSAGES[code] ||
    "Speech recognition failed. You can type the question or tap to speak again."
  );
}

/** Ask for the mic, then release the stream immediately. No audio is kept. */
export async function requestMicrophoneAccess(): Promise<
  "granted" | "denied" | "unavailable"
> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    return "granted";
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    for (const track of stream.getTracks()) {
      track.stop();
    }
    return "granted";
  } catch (error) {
    const name = error instanceof DOMException ? error.name : "";
    if (name === "NotAllowedError" || name === "SecurityError") {
      return "denied";
    }
    return "unavailable";
  }
}

function transcriptFrom(event: SpeechRecognitionEvent): { live: string; finalText: string } {
  let finalized = "";
  let interim = "";
  for (let index = 0; index < event.results.length; index += 1) {
    const piece = event.results[index][0]?.transcript ?? "";
    if (event.results[index].isFinal) {
      finalized += `${piece} `;
    } else {
      interim += piece;
    }
  }
  return {
    live: `${finalized}${interim}`.trim(),
    finalText: finalized.trim(),
  };
}

export function createSpeechSession(
  handlers: SpeechSessionHandlers,
  options?: { lang?: string },
): SpeechSession {
  let recognition: SpeechRecognition | null = null;
  let finalText = "";
  let lastLive = "";
  let failed = false;
  let closed = false;

  function finish(code?: SpeechErrorCode) {
    if (closed) {
      return;
    }
    if (code && code !== "aborted") {
      failed = true;
      handlers.onError(code);
    }
  }

  return {
    async start() {
      const Ctor = getSpeechRecognitionCtor();
      if (!Ctor) {
        finish("not-supported");
        handlers.onEnded("");
        return;
      }
      const permission = await requestMicrophoneAccess();
      if (closed) {
        return;
      }
      if (permission === "denied") {
        finish("not-allowed");
        handlers.onEnded("");
        return;
      }
      if (permission === "unavailable") {
        finish("unavailable");
        handlers.onEnded("");
        return;
      }
      recognition = new Ctor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = options?.lang || "en-IN";
      recognition.onstart = () => {
        if (!closed) {
          handlers.onListening();
        }
      };
      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const { live, finalText: nextFinal } = transcriptFrom(event);
        if (nextFinal) {
          finalText = nextFinal;
          handlers.onFinal(finalText);
        }
        if (live) {
          lastLive = live;
          handlers.onInterim(live);
        }
      };
      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        if (event.error === "aborted") {
          return;
        }
        finish(event.error);
      };
      recognition.onend = () => {
        if (closed) {
          return;
        }
        const spoken = finalText || lastLive;
        if (!failed && !spoken) {
          handlers.onError("no-speech");
        }
        handlers.onEnded(spoken);
      };
      try {
        recognition.start();
      } catch {
        finish("unavailable");
        handlers.onEnded("");
      }
    },
    stop() {
      recognition?.stop();
    },
    abort() {
      closed = true;
      recognition?.abort();
    },
  };
}
