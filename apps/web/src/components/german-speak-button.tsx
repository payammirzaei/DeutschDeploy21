"use client";

import { useEffect, useRef, useState } from "react";

import styles from "./german-speak-button.module.css";

type Props = {
  text: string;
  className?: string;
};

function pickGermanVoice(voices: SpeechSynthesisVoice[]) {
  return (
    voices.find((voice) => voice.lang.toLowerCase() === "de-de") ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith("de")) ??
    null
  );
}

export function GermanSpeakButton({ text, className = "" }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    return () => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
      if (utteranceRef.current) window.speechSynthesis.cancel();
    };
  }, []);

  function toggleSpeech() {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    const synth = window.speechSynthesis;

    if (speaking) {
      synth.cancel();
      utteranceRef.current = null;
      setSpeaking(false);
      return;
    }

    synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "de-DE";
    utterance.rate = 0.92;
    utterance.pitch = 1;

    const germanVoice = pickGermanVoice(synth.getVoices());
    if (germanVoice) utterance.voice = germanVoice;

    utterance.onend = () => {
      utteranceRef.current = null;
      setSpeaking(false);
    };
    utterance.onerror = () => {
      utteranceRef.current = null;
      setSpeaking(false);
    };

    utteranceRef.current = utterance;
    setSpeaking(true);
    synth.speak(utterance);
  }

  return (
    <button
      type="button"
      className={`${styles.button} ${speaking ? styles.speaking : ""} ${className}`}
      onClick={toggleSpeech}
      aria-label={speaking ? "Stop German pronunciation" : "Play German pronunciation"}
      aria-pressed={speaking}
      title={speaking ? "Stop pronunciation" : "Hear German pronunciation"}
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M4 9v6h4l5 4V5L8 9H4Zm12.5-.8a5.5 5.5 0 0 1 0 7.6M18.8 5.9a9 9 0 0 1 0 12.2"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>{speaking ? "Stop" : "Listen"}</span>
    </button>
  );
}
