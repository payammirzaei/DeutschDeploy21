"use client";

import { FormEvent, useMemo, useState } from "react";

import styles from "./exercise-player.module.css";

export type ExerciseAnswer = {
  choice_id?: string;
  text?: string;
  token_ids?: string[];
};

type Choice = { id: string; text: string };
type Token = { id: string; text: string };

export type ExercisePrompt = {
  kind?: string;
  input?: string;
  question?: string;
  lemma?: string;
  clue?: string;
  placeholder?: string;
  tap_hint?: string;
  choices?: Choice[];
  tokens?: Token[];
};

type Props = {
  exerciseType: string;
  prompt: ExercisePrompt;
  submitting?: boolean;
  submitLabel?: string;
  onSubmit: (answer: ExerciseAnswer) => void | Promise<void>;
};

const choiceTypes = new Set([
  "meaning_multiple_choice",
  "perfect_participle_choice",
  "auxiliary_choice",
]);

export function ExercisePlayer({
  exerciseType,
  prompt,
  submitting = false,
  submitLabel = "Check answer",
  onSubmit,
}: Props) {
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [orderedTokenIds, setOrderedTokenIds] = useState<string[]>([]);

  const tokens = useMemo(() => prompt.tokens ?? [], [prompt.tokens]);
  const tokenById = useMemo(
    () => new Map(tokens.map((token) => [token.id, token])),
    [tokens],
  );
  const availableTokens = tokens.filter((token) => !orderedTokenIds.includes(token.id));
  const orderedTokens = orderedTokenIds
    .map((tokenId) => tokenById.get(tokenId))
    .filter((token): token is Token => Boolean(token));

  async function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = text.trim();
    if (!value || submitting) return;
    await onSubmit({ text: value });
  }

  if (choiceTypes.has(exerciseType)) {
    const choices = prompt.choices ?? [];
    return (
      <div className={styles.player}>
        <ExerciseHeading prompt={prompt} />
        <div className={styles.choices} role="radiogroup" aria-label="Answer choices">
          {choices.map((choice, index) => (
            <button
              key={choice.id}
              className={`${styles.choice} ${selectedChoice === choice.id ? styles.selected : ""}`}
              type="button"
              role="radio"
              aria-checked={selectedChoice === choice.id}
              onClick={() => setSelectedChoice(choice.id)}
            >
              <span>{String.fromCharCode(65 + index)}</span>
              <strong dir="auto">{choice.text}</strong>
            </button>
          ))}
        </div>
        <button
          className="button button-primary"
          type="button"
          disabled={!selectedChoice || submitting}
          onClick={() => selectedChoice && onSubmit({ choice_id: selectedChoice })}
        >
          {submitting ? "Saving…" : submitLabel}
        </button>
      </div>
    );
  }

  if (exerciseType === "reverse_typing") {
    return (
      <form className={styles.player} onSubmit={submitText}>
        <ExerciseHeading prompt={prompt} />
        {prompt.clue ? <div className={styles.clue} dir="rtl">{prompt.clue}</div> : null}
        <label className={styles.inputLabel}>
          <span>German answer</span>
          <input
            autoCapitalize="none"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={prompt.placeholder ?? "Type your answer…"}
          />
        </label>
        <button className="button button-primary" disabled={!text.trim() || submitting}>
          {submitting ? "Saving…" : submitLabel}
        </button>
      </form>
    );
  }

  if (exerciseType === "sentence_order") {
    const complete = orderedTokenIds.length === tokens.length && tokens.length > 0;
    return (
      <div className={styles.player}>
        <ExerciseHeading prompt={prompt} />
        <div className={styles.sentenceBoard} aria-label="Your sentence">
          {orderedTokens.length ? (
            orderedTokens.map((token) => (
              <button
                key={token.id}
                className={styles.orderedToken}
                type="button"
                onClick={() =>
                  setOrderedTokenIds((current) => current.filter((id) => id !== token.id))
                }
                aria-label={`Remove ${token.text}`}
              >
                {token.text}
              </button>
            ))
          ) : (
            <span>Tap the chunks below to build the sentence.</span>
          )}
        </div>
        <div className={styles.tokenBank} aria-label="Available sentence chunks">
          {availableTokens.map((token) => (
            <button
              key={token.id}
              type="button"
              onClick={() => setOrderedTokenIds((current) => [...current, token.id])}
            >
              {token.text}
            </button>
          ))}
        </div>
        <div className={styles.puzzleFooter}>
          <button
            className={styles.resetButton}
            type="button"
            disabled={!orderedTokenIds.length || submitting}
            onClick={() => setOrderedTokenIds([])}
          >
            Reset
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!complete || submitting}
            onClick={() => onSubmit({ token_ids: orderedTokenIds })}
          >
            {submitting ? "Saving…" : submitLabel}
          </button>
        </div>
        {prompt.tap_hint ? <small className={styles.hint}>{prompt.tap_hint}</small> : null}
      </div>
    );
  }

  return (
    <div className={styles.player}>
      <ExerciseHeading prompt={prompt} />
      <p className={styles.unsupported}>This exercise renderer is not available yet.</p>
    </div>
  );
}

function ExerciseHeading({ prompt }: { prompt: ExercisePrompt }) {
  return (
    <div className={styles.heading}>
      {prompt.lemma ? <code>{prompt.lemma}</code> : null}
      <h2>{prompt.question ?? "Practice"}</h2>
    </div>
  );
}
