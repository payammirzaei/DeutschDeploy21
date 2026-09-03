"use client";

import { FormEvent, useMemo, useState } from "react";

import styles from "./exercise-player.module.css";

export type ExerciseLocale = "en" | "fa";

export type ExerciseAnswer = {
  choice_id?: string;
  text?: string;
  token_ids?: string[];
  pair_ids?: string[];
};

type LocalizedText = { en?: string | null; fa?: string | null };
type Choice = {
  id: string;
  text: string;
  text_en?: string;
  text_fa?: string;
};
type Token = { id: string; text: string };
type MatchItem = {
  id: string;
  text: string;
  text_en?: string;
  text_fa?: string;
};
type Lesson = {
  title_i18n?: LocalizedText;
  goal_i18n?: LocalizedText;
  explanation_i18n?: LocalizedText;
  example_de?: string | null;
  example_i18n?: LocalizedText;
  meaning_i18n?: LocalizedText;
  grammar?: { cefr?: string | null };
};

export type ExercisePrompt = {
  kind?: string;
  input?: string;
  question?: string;
  question_i18n?: LocalizedText;
  lemma?: string;
  category?: string;
  clue?: string;
  clue_i18n?: LocalizedText;
  placeholder?: string;
  placeholder_i18n?: LocalizedText | null;
  tap_hint?: string;
  tap_hint_i18n?: LocalizedText | null;
  time_limit_seconds?: number;
  instruction_locale_default?: ExerciseLocale;
  lesson?: Lesson;
  choices?: Choice[];
  tokens?: Token[];
  left_items?: MatchItem[];
  right_items?: MatchItem[];
};

type Props = {
  exerciseType: string;
  prompt: ExercisePrompt;
  locale?: ExerciseLocale;
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

const COPY = {
  en: {
    check: "Check answer",
    saving: "Saving…",
    germanAnswer: "German answer",
    typeAnswer: "Type your answer…",
    build: "Tap the chunks below to build the answer.",
    reset: "Reset",
    germanVerbs: "German verbs",
    meanings: "Meanings",
    unsupported: "This exercise renderer is not available yet.",
    practice: "Practice",
    context: "German in context",
    meaning: "Meaning",
  },
  fa: {
    check: "بررسی جواب",
    saving: "در حال ذخیره…",
    germanAnswer: "پاسخ آلمانی",
    typeAnswer: "پاسخت را تایپ کن…",
    build: "تکه‌های پایین را لمس کن و جواب را بساز.",
    reset: "از نو",
    germanVerbs: "افعال آلمانی",
    meanings: "معنی‌ها",
    unsupported: "نمایش این نوع تمرین هنوز آماده نیست.",
    practice: "تمرین",
    context: "آلمانی در متن واقعی",
    meaning: "معنی",
  },
} as const;

function localize(value: LocalizedText | null | undefined, locale: ExerciseLocale) {
  if (!value) return null;
  return value[locale] ?? value.en ?? value.fa ?? null;
}

function choiceText(choice: Choice | MatchItem, locale: ExerciseLocale) {
  if (locale === "fa") return choice.text_fa ?? choice.text;
  return choice.text_en ?? choice.text;
}

export function ExercisePlayer({
  exerciseType,
  prompt,
  locale = "en",
  submitting = false,
  submitLabel,
  onSubmit,
}: Props) {
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [orderedTokenIds, setOrderedTokenIds] = useState<string[]>([]);
  const [activeLeftId, setActiveLeftId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});
  const copy = COPY[locale];
  const actionLabel = submitLabel ?? copy.check;

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

  const lesson = <LearningContext exerciseType={exerciseType} prompt={prompt} locale={locale} />;

  if (choiceTypes.has(exerciseType)) {
    const choices = prompt.choices ?? [];
    return (
      <div className={styles.player}>
        {lesson}
        <ExerciseHeading prompt={prompt} locale={locale} />
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
              <strong dir={locale === "fa" ? "rtl" : "auto"}>{choiceText(choice, locale)}</strong>
            </button>
          ))}
        </div>
        <button
          className="button button-primary"
          type="button"
          disabled={!selectedChoice || submitting}
          onClick={() => selectedChoice && onSubmit({ choice_id: selectedChoice })}
        >
          {submitting ? copy.saving : actionLabel}
        </button>
      </div>
    );
  }

  if (textTypes.has(exerciseType)) {
    const clue = localize(prompt.clue_i18n, locale) ?? prompt.clue;
    const placeholder = localize(prompt.placeholder_i18n, locale) ?? prompt.placeholder ?? copy.typeAnswer;
    return (
      <form className={styles.player} onSubmit={submitText}>
        {lesson}
        <ExerciseHeading prompt={prompt} locale={locale} />
        {clue ? <div className={styles.clue} dir={locale === "fa" ? "rtl" : "auto"}>{clue}</div> : null}
        <label className={styles.inputLabel}>
          <span>{copy.germanAnswer}</span>
          <input
            lang="de"
            dir="ltr"
            autoCapitalize="none"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={placeholder}
          />
        </label>
        <button className="button button-primary" disabled={!text.trim() || submitting}>
          {submitting ? copy.saving : actionLabel}
        </button>
      </form>
    );
  }

  if (orderTypes.has(exerciseType)) {
    const complete = orderedTokenIds.length === tokens.length && tokens.length > 0;
    const hint = localize(prompt.tap_hint_i18n, locale) ?? prompt.tap_hint;
    return (
      <div className={styles.player}>
        {lesson}
        <ExerciseHeading prompt={prompt} locale={locale} />
        <div className={styles.sentenceBoard} role="group" aria-label="Your answer order" lang="de" dir="ltr">
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
            <span dir={locale === "fa" ? "rtl" : "ltr"}>{copy.build}</span>
          )}
        </div>
        <div className={styles.tokenBank} role="group" aria-label="Available answer chunks" lang="de" dir="ltr">
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
            {copy.reset}
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!complete || submitting}
            onClick={() => onSubmit({ token_ids: orderedTokenIds })}
          >
            {submitting ? copy.saving : actionLabel}
          </button>
        </div>
        {hint ? <small className={styles.hint} dir={locale === "fa" ? "rtl" : "ltr"}>{hint}</small> : null}
      </div>
    );
  }

  if (exerciseType === "meaning_matching") {
    const leftItems = prompt.left_items ?? [];
    const rightItems = prompt.right_items ?? [];
    const usedRightIds = new Set(Object.values(matches));
    const complete = leftItems.length > 0 && Object.keys(matches).length === leftItems.length;
    const hint = localize(prompt.tap_hint_i18n, locale) ?? prompt.tap_hint;

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
        {lesson}
        <ExerciseHeading prompt={prompt} locale={locale} />
        <div className={styles.matchGrid}>
          <div className={styles.matchColumn} role="group" aria-label={copy.germanVerbs}>
            {leftItems.map((item) => (
              <button
                key={item.id}
                type="button"
                lang="de"
                dir="ltr"
                className={`${styles.matchItem} ${activeLeftId === item.id ? styles.matchActive : ""} ${matches[item.id] ? styles.matchDone : ""}`}
                aria-pressed={activeLeftId === item.id}
                onClick={() => (matches[item.id] ? removeMatch(item.id) : setActiveLeftId(item.id))}
              >
                <strong>{item.text}</strong>
                <span aria-hidden="true">{matches[item.id] ? "✓" : "DE"}</span>
              </button>
            ))}
          </div>
          <div className={styles.matchColumn} role="group" aria-label={copy.meanings}>
            {rightItems.map((item) => (
              <button
                key={item.id}
                type="button"
                dir={locale === "fa" ? "rtl" : "ltr"}
                className={`${styles.matchItem} ${usedRightIds.has(item.id) ? styles.matchDone : ""}`}
                disabled={usedRightIds.has(item.id)}
                onClick={() => selectRight(item.id)}
              >
                <strong>{choiceText(item, locale)}</strong>
                <span aria-hidden="true">{locale.toUpperCase()}</span>
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
            {copy.reset}
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
            {submitting ? copy.saving : actionLabel}
          </button>
        </div>
        {hint ? <small className={styles.hint} dir={locale === "fa" ? "rtl" : "ltr"}>{hint}</small> : null}
      </div>
    );
  }

  return (
    <div className={styles.player}>
      {lesson}
      <ExerciseHeading prompt={prompt} locale={locale} />
      <p className={styles.unsupported}>{copy.unsupported}</p>
    </div>
  );
}

function LearningContext({
  exerciseType,
  prompt,
  locale,
}: {
  exerciseType: string;
  prompt: ExercisePrompt;
  locale: ExerciseLocale;
}) {
  const lesson = prompt.lesson;
  if (!lesson) return null;

  const title = localize(lesson.title_i18n, locale) ?? COPY[locale].context;
  const goal = localize(lesson.goal_i18n, locale);
  const explanation = localize(lesson.explanation_i18n, locale);
  const exampleTranslation = localize(lesson.example_i18n, locale);
  const meaning = localize(lesson.meaning_i18n, locale);
  const canShowMeaning = !new Set(["meaning_multiple_choice", "meaning_matching"]).has(exerciseType);

  return (
    <section className={styles.lessonCard} dir={locale === "fa" ? "rtl" : "ltr"}>
      <div className={styles.lessonTop}>
        <span>{title}</span>
        {lesson.grammar?.cefr ? <code>{lesson.grammar.cefr}</code> : null}
      </div>
      {goal ? <strong className={styles.lessonGoal}>{goal}</strong> : null}
      {lesson.example_de ? (
        <blockquote lang="de" dir="ltr">{lesson.example_de}</blockquote>
      ) : null}
      {exampleTranslation ? <p className={styles.exampleTranslation}>{exampleTranslation}</p> : null}
      {explanation ? <p>{explanation}</p> : null}
      {canShowMeaning && meaning ? (
        <div className={styles.meaningLine}>
          <span>{COPY[locale].meaning}</span>
          <strong>{meaning}</strong>
        </div>
      ) : null}
    </section>
  );
}

function ExerciseHeading({
  prompt,
  locale,
}: {
  prompt: ExercisePrompt;
  locale: ExerciseLocale;
}) {
  const badge = prompt.lemma ?? prompt.category;
  const question = localize(prompt.question_i18n, locale) ?? prompt.question ?? COPY[locale].practice;
  return (
    <div className={styles.heading} dir={locale === "fa" ? "rtl" : "ltr"}>
      {badge ? <code dir="ltr">{badge}</code> : null}
      <h2>{question}</h2>
    </div>
  );
}
