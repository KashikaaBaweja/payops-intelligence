"use client";

import { useEffect, useRef, useState } from "react";
import {
  createSpeechSession,
  isSpeechRecognitionSupported,
  messageForSpeechError,
  type SpeechSession,
} from "./speech";
export type VoiceQueryState =
  | "idle"
  | "requesting_permission"
  | "recording"
  | "processing"
  | "success"
  | "error";

const HOLD_MS = 450;

export function useSpeechQuery({
  value,
  speechLang = "en-IN",
  disabled = false,
  onChange,
  onError,
  onClearError,
  onVoiceOrigin,
  onBusyChange,
}: {
  value: string;
  speechLang?: string;
  disabled?: boolean;
  onChange: (next: string) => void;
  onError: (message: string) => void;
  onClearError: () => void;
  onVoiceOrigin?: () => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const [state, setState] = useState<VoiceQueryState>("idle");
  const [supported, setSupported] = useState<boolean | null>(null);
  const valueRef = useRef(value);
  const previousRef = useRef(value);
  const sessionRef = useRef<SpeechSession | null>(null);
  const endedRef = useRef(false);
  const stateRef = useRef<VoiceQueryState>("idle");
  const holdTimer = useRef<number | null>(null);
  const holdActive = useRef(false);
  const skipClick = useRef(false);

  valueRef.current = value;
  stateRef.current = state;

  useEffect(() => {
    setSupported(isSpeechRecognitionSupported());
  }, []);

  useEffect(() => {
    return () => {
      if (holdTimer.current) {
        window.clearTimeout(holdTimer.current);
      }
      sessionRef.current?.abort();
    };
  }, []);

  async function startListening() {
    onClearError();
    endedRef.current = false;
    previousRef.current = valueRef.current;
    setState("requesting_permission");
    onBusyChange?.(true);
    const session = createSpeechSession(
      {
        onListening: () => setState("recording"),
        onInterim: (text) => onChange(text),
        onFinal: (text) => onChange(text),
        onError: (code) => {
          onChange(previousRef.current);
          onError(messageForSpeechError(code));
          onBusyChange?.(false);
          setState("error");
        },
        onEnded: (finalText) => {
          if (endedRef.current) {
            return;
          }
          endedRef.current = true;
          sessionRef.current = null;
          onBusyChange?.(false);
          if (finalText) {
            onChange(finalText);
            onClearError();
            onVoiceOrigin?.();
            setState("success");
            return;
          }
          onChange(previousRef.current);
          setState((current) => (current === "error" ? current : "error"));
        },
      },
      { lang: speechLang },
    );
    sessionRef.current = session;
    await session.start();
  }

  function stopListening() {
    setState("processing");
    sessionRef.current?.stop();
  }

  function toggle() {
    if (disabled) {
      return;
    }
    if (stateRef.current === "requesting_permission" || stateRef.current === "processing") {
      return;
    }
    if (stateRef.current === "recording") {
      stopListening();
      return;
    }
    if (supported === false) {
      onError(messageForSpeechError("not-supported"));
      setState("error");
      return;
    }
    void startListening();
  }

  function onMicClick() {
    if (skipClick.current) {
      skipClick.current = false;
      return;
    }
    toggle();
  }

  function onMicPointerDown() {
    if (disabled || supported === false) {
      return;
    }
    holdTimer.current = window.setTimeout(() => {
      holdActive.current = true;
      if (stateRef.current !== "recording") {
        void startListening();
      }
    }, HOLD_MS);
  }

  function onMicPointerUp() {
    if (holdTimer.current) {
      window.clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
    if (holdActive.current) {
      holdActive.current = false;
      skipClick.current = true;
      if (stateRef.current === "recording") {
        stopListening();
      }
    }
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || !event.shiftKey) {
        return;
      }
      if (event.key.toLowerCase() !== "v") {
        return;
      }
      event.preventDefault();
      toggle();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return {
    state,
    supported,
    busy: state === "requesting_permission" || state === "processing",
    recording: state === "recording",
    processing: state === "processing",
    startListening,
    stopListening,
    toggle,
    onMicClick,
    onMicPointerDown,
    onMicPointerUp,
  };
}
