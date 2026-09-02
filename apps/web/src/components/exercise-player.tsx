"use client";

import { FormEvent, useMemo, useState } from "react";

import styles from "./exercise-player.module.css";

export type ExerciseAnswer = {
  choice_id?: string;
  text?: string;
  token_ids?: string[];
  pair_ids?: string[];
};

type Choice = { id: string; text: string };
type Token = { id: string; text: string };
type MatchItem = { id: string; text: string };

export type ExercisePrompt = {
  kind?: string;
  input?: string;
  question?: string;
  lemma?: string;
  category?: string;
  clue?: string;
  placeholder?: string;
  tap_hint?: string;
  time_limit_seconds?: number;
  choices?: Choice[];
  tokens?: Token[];
  left_items?: MatchItem[];
  right_items?: MatchItem[];
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
  "usage_error_spotting",
  "interview_best_answer",
]);

const textTypes = new Set([
  "reverse_typing",
  "example_cloze",
  "perfect_form_typing",
  "timed_quick_recall",
]);

const orderTypes = new Set([
  "sentence_order",
  "phrase_builder",
  "hr_answer_order",
  "star_builder",
  "technical_explanation_order",
  "architecture_sequence",
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
  const [activeLeftId, setActiveLeftId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});

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
        <div className={styles.choices} role="group" aria-label="Answer choices">
          {choices.map((choice, index) => (
            <button
              key={choice.id}
              className={`${styles.choice} ${selectedChoice === choice.id ? styles.selected : ""}`}
              type="button"
              aria-pressed={selectedChoice === choice.id}
              onClick={() => setSelectedChoice(choice.id)}
            >
              <span aria-hidden="true">{String.fromCharCode(65 + index)}</span>
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

  if (textTypes.has(exerciseType)) {
    return (
      <form className={styles.player} onSubmit={submitText}>
        <ExerciseHeading prompt={prompt} />
        {prompt.clue ? <div className={styles.clue} dir="auto">{prompt.clue}</div> : null}
        <label className={styles.inputLabel}>
          <span>German answer</span>
          <input
            lang="de"
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

  if (orderTypes.has(exerciseType)) {
    const complete = orderedTokenIds.length === tokens.length && tokens.length > 0;
    return (
      <div className={styles.player}>
        <ExerciseHeading prompt={prompt} />
        <div className={styles.sentenceBoard} role="group" aria-label="Your answer order">
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
            <span>Tap the chunks below to build the answer.</span>
          )}
        </div>
        <div className={styles.tokenBank} role="group" aria-label="Available answer chunks">
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

  if (exerciseType === "meaning_matching") {
    const leftItems = prompt.left_items ?? [];
    const rightItems = prompt.right_items ?? [];
    const usedRightIds = new Set(Object.values(matches));
    const complete = leftItems.length > 0 && Object.keys(matches).length === leftItems.length;

    function selectRight(rightId: string) {
      if (!activeLeftId || usedRightIds.has(rightId)) return;
      setMatches((current) => ({ ...current, [activeLeftId]: rightId }));
      setActiveLeftId(null);
    }

    function removeMatch(leftId: string) {
      setMatches((current) => {
        const next = { ...current };
        delete next[leftId];
        return next;
      });
      setActiveLeftId(leftId);
    }

    return (
      <div className={styles.player}>
        <ExerciseHeading prompt={prompt} />
        <div className={styles.matchGrid}>
          <div className={styles.matchColumn} role="group" aria-label="German verbs">
            {leftItems.map((item) => (
              <button
                key={item.id}
                type="button"
                lang="de"
                className={`${styles.matchItem} ${activeLeftId === item.id ? styles.matchActive : ""} ${matches[item.id] ? styles.matchDone : ""}`}
                aria-pressed={activeLeftId === item.id}
                onClick={() => (matches[item.id] ? removeMatch(item.id) : setActiveLeftId(item.id))}
              >
                <strong>{item.text}</strong>
                <span aria-hidden="true">{matches[item.id] ? "✓" : "DE"}</span>
              </button>
            ))}
          </div>
          <div className={styles.matchColumn} role="group" aria-label="Persian meanings">
            {rightItems.map((item) => (
              <button
                key={item.id}
                type="button"
                lang="fa"
                dir="rtl"
                className={`${styles.matchItem} ${usedRightIds.has(item.id) ? styles.matchDone : ""}`}
                disabled={usedRightIds.has(item.id)}
                onClick={() => selectRight(item.id)}
              >
                <strong>{item.text}</strong>
                <span aria-hidden="true">FA</span>
              </button>
            ))}
          </div>
        </div>
        <div className={styles.puzzleFooter}>
          <button
            className={styles.resetButton}
            type="button"
            disabled={!Object.keys(matches).length || submitting}
            onClick={() => {
              setMatches({});
              setActiveLeftId(null);
            }}
          >
            Reset
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!complete || submitting}
            onClick={() =>
              onSubmit({
                pair_ids: Object.entries(matches).map(([left, right]) => `${left}:${right}`),
              })
            }
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
  const badge = prompt.lemma ?? prompt.category;
  return (
    <div className={styles.heading}>
      {badge ? <code>{badge}</code> : null}
      <h2>{prompt.question ?? "Practice"}</h2>
    </div>
  );
}
