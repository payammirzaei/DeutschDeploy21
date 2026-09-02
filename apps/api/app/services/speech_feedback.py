import re

from app.models.speech import SpeechAttempt, SpeechFeedback, SpeechTranscript

FILLER_PATTERN = re.compile(r"\b(äh|ähm|also|sozusagen|eigentlich|halt)\b", re.IGNORECASE)
STRUCTURE_MARKERS = (
    "zuerst",
    "dann",
    "danach",
    "zum schluss",
    "deshalb",
    "dadurch",
    "erstens",
    "zweitens",
    "am ende",
)


def build_speech_feedback(
    attempt: SpeechAttempt,
    transcript: SpeechTranscript,
    *,
    duration_ms: int | None,
) -> SpeechFeedback:
    words = re.findall(r"\b[\wÄÖÜäöüß'-]+\b", transcript.text, flags=re.UNICODE)
    word_count = len(words)
    unique_ratio = round(len({word.casefold() for word in words}) / max(1, word_count), 2)
    filler_count = len(FILLER_PATTERN.findall(transcript.text))
    lowered = transcript.text.casefold()
    marker_count = sum(1 for marker in STRUCTURE_MARKERS if marker in lowered)
    duration_seconds = round(duration_ms / 1000, 1) if duration_ms else None
    words_per_minute = (
        round(word_count / (duration_ms / 60_000))
        if duration_ms and duration_ms >= 1000
        else None
    )

    target = attempt.target_duration_seconds
    duration_ratio = duration_seconds / target if duration_seconds and target else None
    concision_score = 70
    if duration_ratio is not None:
        if 0.6 <= duration_ratio <= 1.5:
            concision_score = 100
        elif 0.4 <= duration_ratio <= 1.8:
            concision_score = 80
        else:
            concision_score = 55

    structure_score = min(100, 45 + marker_count * 18)
    fluency_proxy_score = max(45, 100 - filler_count * 10)
    output_score = 100 if word_count >= 25 else 80 if word_count >= 12 else 55
    overall = round(
        (concision_score + structure_score + fluency_proxy_score + output_score) / 4
    )

    corrections: list[dict[str, str]] = []
    if word_count < 12:
        corrections.append(
            {
                "code": "answer_too_short",
                "message": "Add one concrete detail: responsibility, action, or result.",
            }
        )
    if marker_count == 0:
        corrections.append(
            {
                "code": "missing_structure_signal",
                "message": "Use one connector such as „zuerst“, „dann“ or „deshalb“.",
            }
        )
    if filler_count >= 3:
        corrections.append(
            {
                "code": "many_fillers",
                "message": "Replace filler words with a short silent pause.",
            }
        )

    if corrections:
        next_action = corrections[0]["message"]
    else:
        next_action = "Repeat once and make the same answer 10–15% more concise."

    summary = (
        "Text-level speaking feedback is ready. Pronunciation and accent are not scored "
        "in this version; the metrics below use the saved transcript and duration only."
    )
    return SpeechFeedback(
        speech_attempt_id=attempt.id,
        transcript_id=transcript.id,
        evaluator_type="speech_text_heuristic",
        evaluator_version=1,
        overall_score=overall,
        summary=summary,
        dimensions={
            "word_count": word_count,
            "unique_word_ratio": unique_ratio,
            "duration_seconds": duration_seconds,
            "target_duration_seconds": target,
            "words_per_minute": words_per_minute,
            "filler_count": filler_count,
            "structure_marker_count": marker_count,
            "concision_score": concision_score,
            "structure_signal_score": structure_score,
            "fluency_proxy_score": fluency_proxy_score,
            "output_score": output_score,
            "pronunciation_assessed": False,
        },
        corrections=corrections,
        next_action=next_action,
    )
