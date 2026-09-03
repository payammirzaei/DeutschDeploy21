"use client";

import { useMemo, useState } from "react";

import {
  ExerciseAnswer,
  ExercisePrompt,
} from "@/src/components/exercise-player";

import styles from "./learning-feedback.module.css";

type Locale = "en" | "fa";
type LocalizedText = { en?: string | null; fa?: string | null };

type Props = {
  exerciseType: string;
  prompt: ExercisePrompt;
  fallbackLemma: string;
  answer: ExerciseAnswer | null;
  correct: boolean;
  score: number;
  feedbackCode: string;
  dayComplete: boolean;
  nextDay: number;
  availableThroughDay: number;
  continueLabelI18n?: LocalizedText;
  onContinue: () => void | Promise<void>;
};

const COPY = {
  en: {
    correctKicker: "PATTERN LOCKED",
    incorrectKicker: "LEARN FROM THIS ONE",
    correctTitle: "Genau. Keep the pattern, not just the answer.",
    incorrectTitle: "Not yet. Compare, understand, then keep moving.",
    correctLead:
      "Your answer worked. Read the rule and anchor once more so the structure survives outside this exercise.",
    incorrectLead:
      "This miss is useful evidence. Use the rule below, compare it with the anchor, and let review bring it back later.",
    yourAnswer: "Your answer",
    rule: "Why / rule",
    anchor: "German anchor",
    meaning: "Meaning",
    reveal: "Correct target",
    evidenceCorrect: "Stored as positive mastery evidence",
    evidenceWrong: "Stored as focused review evidence",
    nextActivity: "Next activity",
    nextDay: "Continue to next day",
    finish: "Finish course",
    language: "Feedback language",
    score: "deterministic score",
  },
  fa: {
    correctKicker: "الگو تثبیت شد",
    incorrectKicker: "از همین اشتباه یاد بگیر",
    correctTitle: "درسته. الگو رو نگه دار، نه فقط جواب رو.",
    incorrectTitle: "هنوز نه. مقایسه کن، بفهم، بعد ادامه بده.",
    correctLead:
      "جوابت درست بود. قانون و جمله‌ی نمونه را یک بار دیگر بخوان تا ساختار بیرون از این تمرین هم یادت بماند.",
    incorrectLead:
      "این اشتباه برای یادگیری مفیده. قانون پایین را ببین، با جمله‌ی نمونه مقایسه کن و بگذار مرور دوباره برش گرداند.",
    yourAnswer: "جواب تو",
    rule: "چرا / قانون",
    anchor: "جمله‌ی مرجع آلمانی",
    meaning: "معنی",
    reveal: "هدف درست",
    evidenceCorrect: "به‌عنوان شواهد مثبت یادگیری ذخیره شد",
    evidenceWrong: "برای مرور هدفمند ذخیره شد",
    nextActivity: "تمرین بعدی",
    nextDay: "رفتن به روز بعد",
    finish: "پایان دوره",
    language: "زبان بازخورد",
    score: "امتیاز قطعی",
  },
} as const;

function localize(value: LocalizedText | null | undefined, locale: Locale) {
  if (!value) return null;
  return value[locale] ?? value.en ?? value.fa ?? null;
}

function localizedChoice(
  choice: { text: string; text_en?: string; text_fa?: string },
  locale: Locale,
) {
  if (locale === "fa") return choice.text_fa ?? choice.text;
  return choice.text_en ?? choice.text;
}

function joinGermanTokens(values: string[]) {
  return values
    .join(" ")
    .replace(/\s+([,.!?;:])/g, "$1")
    .replace(/([([])\s+/g, "$1")
    .replace(/\s+([)\]])/g, "$1");
}

function submittedAnswer(
  answer: ExerciseAnswer | null,
  prompt: ExercisePrompt,
  locale: Locale,
) {
  if (!answer) return null;
  if (answer.text) return answer.text;
  if (answer.choice_id) {
    const choice = (prompt.choices ?? []).find(
      (item) => item.id === answer.choice_id,
    );
    return choice ? localizedChoice(choice, locale) : null;
  }
  if (answer.token_ids?.length) {
    const byId = new Map((prompt.tokens ?? []).map((token) => [token.id, token.text]));
    const values = answer.token_ids
      .map((id) => byId.get(id))
      .filter((value): value is string => Boolean(value));
    return values.length ? joinGermanTokens(values) : null;
  }
  if (answer.pair_ids?.length) {
    const left = new Map((prompt.left_items ?? []).map((item) => [item.id, item]));
    const right = new Map((prompt.right_items ?? []).map((item) => [item.id, item]));
    const rows = answer.pair_ids
      .map((pair) => {
        const [leftId, rightId] = pair.split(":");
        const source = left.get(leftId);
        const target = right.get(rightId);
        if (!source || !target) return null;
        return `${source.text} → ${localizedChoice(target, locale)}`;
      })
      .filter((value): value is string => Boolean(value));
    return rows.length ? rows.join(" · ") : null;
  }
  return null;
}

function correctReveal(
  exerciseType: string,
  prompt: ExercisePrompt,
  fallbackLemma: string,
  locale: Locale,
) {
  const lesson = prompt.lesson;
  if (exerciseType === "meaning_multiple_choice") {
    return localize(lesson?.meaning_i18n, locale);
  }
  if (exerciseType === "example_cloze") {
    return prompt.lemma ?? (fallbackLemma !== "Interview" ? fallbackLemma : null);
  }
  if (
    exerciseType === "sentence_order" ||
    exerciseType === "phrase_builder" ||
    exerciseType === "usage_error_spotting"
  ) {
    return lesson?.example_de ?? null;
  }
  if (exerciseType === "reverse_typing" && fallbackLemma !== "Interview") {
    return fallbackLemma;
  }
  return null;
}

export function LearningFeedback({
  exerciseType,
  prompt,
  fallbackLemma,
  answer,
  correct,
  score,
  feedbackCode,
  dayComplete,
  nextDay,
  availableThroughDay,
  continueLabelI18n,
  onContinue,
}: Props) {
  const [locale, setLocale] = useState<Locale>("en");
  const copy = COPY[locale];
  const lesson = prompt.lesson;
  const rule = localize(lesson?.explanation_i18n, locale);
  const meaning = localize(lesson?.meaning_i18n, locale);
  const answerText = useMemo(
    () => submittedAnswer(answer, prompt, locale),
    [answer, locale, prompt],
  );
  const reveal = correctReveal(exerciseType, prompt, fallbackLemma, locale);
  const customNextLabel = localize(continueLabelI18n, locale);
  const nextLabel = customNextLabel ?? (
    dayComplete
      ? nextDay > availableThroughDay
        ? copy.finish
        : copy.nextDay
      : copy.nextActivity
  );

  return (
    <section
      className={`${styles.feedback} ${correct ? styles.correct : styles.incorrect}`}
      aria-live="polite"
      dir={locale === "fa" ? "rtl" : "ltr"}
    >
      <div className={styles.topRow}>
        <span className={styles.kicker}>
          {correct ? copy.correctKicker : copy.incorrectKicker}
        </span>
        <div className={styles.languageSwitch} role="group" aria-label={copy.language}>
          <button
            type="button"
            className={locale === "en" ? styles.languageActive : ""}
            aria-pressed={locale === "en"}
            onClick={() => setLocale("en")}
          >
            EN
          </button>
          <button
            type="button"
            className={locale === "fa" ? styles.languageActive : ""}
            aria-pressed={locale === "fa"}
            onClick={() => setLocale("fa")}
          >
            فارسی
          </button>
        </div>
      </div>

      <h2>{correct ? copy.correctTitle : copy.incorrectTitle}</h2>
      <p className={styles.lead}>{correct ? copy.correctLead : copy.incorrectLead}</p>

      <div className={styles.teachingGrid}>
        {answerText ? (
          <div className={styles.teachingCard}>
            <span>{copy.yourAnswer}</span>
            <strong dir={exerciseType === "meaning_multiple_choice" ? "auto" : "ltr"}>
              {answerText}
            </strong>
          </div>
        ) : null}

        {reveal ? (
          <div className={`${styles.teachingCard} ${styles.revealCard}`}>
            <span>{copy.reveal}</span>
            <strong dir={locale === "fa" && exerciseType === "meaning_multiple_choice" ? "rtl" : "ltr"}>
              {reveal}
            </strong>
          </div>
        ) : null}

        {rule ? (
          <div className={`${styles.teachingCard} ${styles.ruleCard}`}>
            <span>{copy.rule}</span>
            <p>{rule}</p>
          </div>
        ) : null}

        {lesson?.example_de ? (
          <div className={`${styles.teachingCard} ${styles.anchorCard}`}>
            <span>{copy.anchor}</span>
            <blockquote lang="de" dir="ltr">{lesson.example_de}</blockquote>
          </div>
        ) : null}

        {meaning && exerciseType !== "meaning_multiple_choice" ? (
          <div className={styles.teachingCard}>
            <span>{copy.meaning}</span>
            <strong>{meaning}</strong>
          </div>
        ) : null}
      </div>

      <div className={styles.bottomRow}>
        <div className={styles.scoreBlock}>
          <strong>{score}</strong>
          <span>{copy.score}</span>
          <code>{feedbackCode}</code>
        </div>
        <span className={styles.evidence}>
          {correct ? copy.evidenceCorrect : copy.evidenceWrong}
        </span>
      </div>

      <button className="button button-accent" type="button" onClick={onContinue}>
        {nextLabel}
      </button>
    </section>
  );
}
