import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    ContentVersion,
    VerbVersion,
    VersionExample,
    VersionLocalization,
)
from app.models.learning import ActivityInstance, CourseDay, CourseRelease, ReleaseActivity
from app.schemas.content import VerbPedagogyIn
from app.services.content import PEDAGOGY_FIELD, PEDAGOGY_LOCALE
from app.services.lesson_overlay import (
    apply_prompt_override,
    overlay_contract_from_instance,
    overlay_identity_for_release,
    prompt_override_for_position,
    teaching_block_as_prompt,
    teaching_block_for_position,
)

PROMPT_CONTRACT_VERSION = 2
PROMPT_CONTRACT_VERSION_V4 = 3

QUESTION_I18N: dict[str, dict[str, str]] = {
    "meaning_multiple_choice": {
        "en": "What does this verb mean in this context?",
        "fa": "این فعل در این جمله چه معنایی می‌دهد؟",
    },
    "reverse_typing": {
        "en": "Recall the German verb from the meaning and context.",
        "fa": "با کمک معنی و جمله، فعل آلمانی را به یاد بیاور.",
    },
    "perfect_participle_choice": {
        "en": "Choose the correct Partizip II for this verb.",
        "fa": "Partizip II درست این فعل را انتخاب کن.",
    },
    "auxiliary_choice": {
        "en": "Which auxiliary does this verb use in Perfekt?",
        "fa": "این فعل در Perfekt با کدام فعل کمکی می‌آید؟",
    },
    "sentence_order": {
        "en": "Build the interview sentence in natural German word order.",
        "fa": "جمله‌ی مصاحبه را با ترتیب طبیعی آلمانی بساز.",
    },
    "meaning_matching": {
        "en": "Match each German verb with its meaning.",
        "fa": "هر فعل آلمانی را به معنی درست وصل کن.",
    },
    "example_cloze": {
        "en": "Complete the real interview sentence with the missing verb.",
        "fa": "جای خالی جمله‌ی واقعی مصاحبه را با فعل درست کامل کن.",
    },
    "usage_error_spotting": {
        "en": "Which sentence uses the verb structure correctly?",
        "fa": "کدام جمله ساختار فعل را درست استفاده می‌کند؟",
    },
    "perfect_form_typing": {
        "en": "Build the complete Perfekt form: auxiliary + Partizip II.",
        "fa": "فرم کامل Perfekt را بساز: فعل کمکی + Partizip II.",
    },
    "phrase_builder": {
        "en": "Put the answer chunks into a natural interview sentence.",
        "fa": "تکه‌های جواب را به یک جمله‌ی طبیعی مصاحبه تبدیل کن.",
    },
}

GOAL_I18N: dict[str, dict[str, str]] = {
    "meaning_multiple_choice": {
        "en": "Infer meaning from a real sentence, not from an isolated flashcard.",
        "fa": "معنی را از یک جمله‌ی واقعی حدس بزن، نه از یک فلش‌کارت جدا.",
    },
    "reverse_typing": {
        "en": "Move from recognition to active recall.",
        "fa": "از شناختن معنی به یادآوری فعال فعل برس.",
    },
    "perfect_participle_choice": {
        "en": "Recognize the form you need when talking about past work.",
        "fa": "فرمی را بشناس که برای صحبت درباره‌ی کارهای گذشته لازم داری.",
    },
    "auxiliary_choice": {
        "en": "Learn the haben/sein pattern as part of the verb, not as trivia.",
        "fa": "الگوی haben/sein را بخشی از خود فعل یاد بگیر، نه یک نکته‌ی حفظی.",
    },
    "sentence_order": {
        "en": "Build German word order with a sentence you could actually say.",
        "fa": "ترتیب کلمات آلمانی را با جمله‌ای تمرین کن که واقعاً می‌توانی بگویی.",
    },
    "meaning_matching": {
        "en": "Strengthen fast associations between German and meaning.",
        "fa": "ارتباط سریع بین فعل آلمانی و معنی را قوی کن.",
    },
    "example_cloze": {
        "en": "Retrieve the verb inside a meaningful sentence.",
        "fa": "فعل را داخل یک جمله‌ی معنی‌دار به یاد بیاور.",
    },
    "usage_error_spotting": {
        "en": "Notice how the verb behaves in a sentence, not only what it means.",
        "fa": "ببین فعل داخل جمله چطور رفتار می‌کند، نه فقط اینکه چه معنی دارد.",
    },
    "perfect_form_typing": {
        "en": "Produce the complete past-tense building block yourself.",
        "fa": "ساختار کامل گذشته را خودت تولید کن.",
    },
    "phrase_builder": {
        "en": "Practice reusable chunks instead of translating word by word.",
        "fa": "به‌جای ترجمه‌ی کلمه‌به‌کلمه، تکه‌های قابل استفاده‌ی جمله را تمرین کن.",
    },
}

EXPLANATION_I18N: dict[str, dict[str, str]] = {
    "meaning_multiple_choice": {
        "en": (
            "Read the German example first. Use the situation and surrounding "
            "words before looking at the answer choices."
        ),
        "fa": (
            "اول مثال آلمانی را بخوان. قبل از نگاه‌کردن به گزینه‌ها از موقعیت "
            "و کلمات اطراف کمک بگیر."
        ),
    },
    "reverse_typing": {
        "en": (
            "Try to say the German verb in your head before typing. Active recall "
            "is harder than recognition and builds stronger memory."
        ),
        "fa": (
            "قبل از تایپ، فعل آلمانی را در ذهنت بگو. یادآوری فعال سخت‌تر از "
            "شناختن است و حافظه را قوی‌تر می‌کند."
        ),
    },
    "perfect_participle_choice": {
        "en": (
            "Perfekt normally combines haben or sein with Partizip II. Learn the "
            "participle together with the infinitive."
        ),
        "fa": (
            "Perfekt معمولاً از haben یا sein همراه Partizip II ساخته می‌شود. "
            "Partizip II را همراه خود فعل یاد بگیر."
        ),
    },
    "auxiliary_choice": {
        "en": (
            "Treat the auxiliary as part of the verb's past-tense pattern. Most "
            "verbs use haben; movement/change-of-state verbs often use sein."
        ),
        "fa": (
            "فعل کمکی را بخشی از الگوی گذشته‌ی فعل بدان. بیشتر فعل‌ها haben "
            "می‌گیرند و بسیاری از فعل‌های حرکت/تغییر حالت sein."
        ),
    },
    "sentence_order": {
        "en": (
            "Build meaning first, then notice verb position. With modal verbs such "
            "as können, the infinitive commonly moves to the end."
        ),
        "fa": (
            "اول معنی جمله را بساز و بعد جای فعل را ببین. با افعال مدال مثل "
            "können، مصدر معمولاً به انتهای جمله می‌رود."
        ),
    },
    "meaning_matching": {
        "en": (
            "Match quickly, then read each German verb once more without the "
            "translation. The second pass is the memory step."
        ),
        "fa": (
            "سریع وصل کن، بعد هر فعل آلمانی را یک بار دیگر بدون نگاه به ترجمه "
            "بخوان. مرور دوم بخش حافظه‌سازی است."
        ),
    },
    "example_cloze": {
        "en": (
            "Use the whole sentence as a retrieval cue. Ask yourself what action "
            "makes the sentence logical before recalling the exact German word."
        ),
        "fa": (
            "از کل جمله به‌عنوان سرنخ استفاده کن. اول ببین چه عملی جمله را منطقی "
            "می‌کند، بعد کلمه‌ی دقیق آلمانی را به یاد بیاور."
        ),
    },
    "usage_error_spotting": {
        "en": (
            "Compare structure, not just vocabulary. Look at where the infinitive "
            "or participle belongs and whether an extra zu changes the construction."
        ),
        "fa": (
            "ساختار را مقایسه کن، نه فقط لغت را. جای مصدر یا Partizip را ببین و "
            "دقت کن اضافه‌شدن zu ساختار را عوض می‌کند یا نه."
        ),
    },
    "perfect_form_typing": {
        "en": (
            "Produce both pieces together. This makes the form easier to retrieve "
            "later when you describe completed work in an interview."
        ),
        "fa": (
            "هر دو بخش را با هم تولید کن. این کار کمک می‌کند بعداً هنگام توضیح "
            "کارهای انجام‌شده در مصاحبه فرم را سریع‌تر به یاد بیاوری."
        ),
    },
    "phrase_builder": {
        "en": (
            "Think in chunks such as subject + modal, object, and action. Chunking "
            "is closer to fluent speech than translating each word separately."
        ),
        "fa": (
            "جمله را به تکه‌هایی مثل فاعل + فعل مدال، مفعول و عمل تقسیم کن. "
            "یادگیری تکه‌ای به گفتار روان نزدیک‌تر از ترجمه‌ی تک‌تک کلمات است."
        ),
    },
}


async def enrich_learning_instance(
    session: AsyncSession,
    instance: ActivityInstance,
    activity: ReleaseActivity,
) -> ActivityInstance:
    day = await session.get(CourseDay, activity.day_id)
    if day is None:
        return instance
    release = await session.get(CourseRelease, day.release_id)
    if release is None or release.version_number < 3:
        return instance
    if activity.source_kind != "content" or activity.content_version_id is None:
        return instance

    version = await session.get(ContentVersion, activity.content_version_id)
    if version is None:
        return instance

    examples = list(
        (
            await session.execute(
                select(VersionExample)
                .where(VersionExample.version_id == version.id)
                .order_by(VersionExample.sort_order, VersionExample.external_id)
            )
        ).scalars()
    )
    example = examples[0] if examples else None
    translations = await _translations(session, version.id)
    verb = await session.get(VerbVersion, version.id)
    pedagogy = await _pedagogy(session, version.id)
    prompt = dict(instance.prompt)
    exercise_type = instance.exercise_type
    deep = release.version_number >= 4 and pedagogy is not None

    question_i18n = QUESTION_I18N.get(exercise_type)
    if question_i18n:
        prompt["question_i18n"] = question_i18n
        prompt["question"] = question_i18n["en"]

    prompt["instruction_locale_default"] = "en"
    interview_example = next(
        (row for row in examples if row.skill == "interview"),
        example,
    )
    software_example = next(
        (row for row in examples if row.skill == "software"),
        None,
    )
    anchor = interview_example or example

    explanation = EXPLANATION_I18N.get(exercise_type, {})
    if deep and pedagogy and pedagogy.usage_notes is not None:
        explanation = {
            "en": pedagogy.usage_notes.en,
            "fa": pedagogy.usage_notes.fa,
        }
    if deep and pedagogy and pedagogy.mistakes and exercise_type == "usage_error_spotting":
        mistake = pedagogy.mistakes[0]
        explanation = {
            "en": mistake.why.en,
            "fa": mistake.why.fa,
        }

    lesson = {
        "title_i18n": {
            "en": "Learn it like a teacher would",
            "fa": "مثل یک معلم واقعی یاد بگیر",
        }
        if deep
        else {
            "en": "Learn it in context",
            "fa": "یادگیری در متن",
        },
        "goal_i18n": GOAL_I18N.get(exercise_type, {}),
        "explanation_i18n": explanation,
        "example_de": anchor.text_de if anchor else None,
        "example_i18n": {
            "en": anchor.text_en if anchor else None,
            "fa": anchor.text_fa if anchor else None,
        },
        "meaning_i18n": {
            "en": translations.get("en"),
            "fa": translations.get("fa"),
        },
        "grammar": {
            "cefr": version.cefr,
        },
    }

    if verb is not None:
        lesson["grammar"].update(
            {
                "perfect_auxiliary": verb.perfect_auxiliary,
                "participle_ii": verb.participle_ii,
                "separable": verb.separable,
                "separable_prefix": verb.separable_prefix,
                "regularity": verb.regularity,
                "governed_case": verb.governed_case,
                "governed_preposition": verb.governed_preposition,
            }
        )

    if deep and pedagogy is not None:
        lesson["pronunciation_hint"] = pedagogy.pronunciation_hint
        lesson["usage_notes_i18n"] = (
            pedagogy.usage_notes.model_dump() if pedagogy.usage_notes else None
        )
        lesson["praesens"] = (
            pedagogy.praesens.model_dump() if pedagogy.praesens else None
        )
        lesson["structures"] = [
            {
                "pattern_de": item.pattern_de,
                "note_i18n": item.note.model_dump(),
            }
            for item in pedagogy.structures
        ]
        lesson["mistakes"] = [
            {
                "wrong_de": item.wrong_de,
                "correct_de": item.correct_de,
                "why_i18n": item.why.model_dump(),
            }
            for item in pedagogy.mistakes
        ]
        lesson["contrasts"] = [
            {
                "lemma": item.lemma,
                "difference_i18n": item.difference.model_dump(),
            }
            for item in pedagogy.contrasts
        ]
        lesson["collocations"] = list(pedagogy.collocations)
        lesson["related"] = list(pedagogy.related)
        lesson["interview_uses"] = [
            {
                "model_answer_de": item.model_answer_de,
                "note_i18n": item.note.model_dump(),
            }
            for item in pedagogy.interview_uses
        ]
        lesson["grammar_tags"] = list(pedagogy.grammar_tags)
        lesson["examples"] = [
            {
                "de": row.text_de,
                "en": row.text_en,
                "fa": row.text_fa,
                "skill": row.skill,
            }
            for row in examples
        ]
        if software_example is not None:
            lesson["software_example_de"] = software_example.text_de
        if pedagogy.mistakes:
            primary = pedagogy.mistakes[0]
            lesson["teaching_feedback"] = {
                "why_i18n": primary.why.model_dump(),
                "rule_i18n": explanation,
                "correct_example_de": primary.correct_de,
            }

    block = (
        teaching_block_for_position(
            day.day_number,
            activity.position,
            release.version_number,
        )
        if release.version_number >= 4
        else None
    )
    if block is not None:
        lesson["teaching_block"] = teaching_block_as_prompt(block)
        lesson["title_i18n"] = block.title_i18n.model_dump()
        lesson["goal_i18n"] = block.explanation_i18n.model_dump()
        lesson["explanation_i18n"] = block.rule_i18n.model_dump()
        lesson["example_de"] = block.example_de
        lesson["example_i18n"] = (
            block.example_i18n.model_dump() if block.example_i18n else lesson.get("example_i18n")
        )
        lesson["teaching_feedback"] = {
            "why_i18n": block.explanation_i18n.model_dump(),
            "rule_i18n": block.rule_i18n.model_dump(),
            "correct_example_de": block.corrected_example_de or block.example_de,
        }

    prompt["lesson"] = lesson

    existing_contract = overlay_contract_from_instance(
        instance.prompt if isinstance(instance.prompt, dict) else None
    )
    if existing_contract is not None:
        # Historical graded contract is frozen on the instance. Never silently
        # re-bind to a newer teaching overlay for answer keys. Teaching metadata
        # above may refresh; token order / answer_key must not.
        prompt["overlay_contract"] = existing_contract
        if existing_contract.get("graded_as") == "phrase_builder":
            instance.exercise_type = "phrase_builder"
        # Preserve the originally pinned answer_key verbatim.
        if isinstance(instance.answer_key, dict):
            key = dict(instance.answer_key)
            key["overlay_contract"] = dict(existing_contract)
            instance.answer_key = key
    elif release.version_number >= 4:
        identity = overlay_identity_for_release(release.version_number)
        override = prompt_override_for_position(
            day.day_number,
            activity.position,
            release.version_number,
        )
        if identity is not None and override is not None:
            prompt, answer_key = apply_prompt_override(
                prompt,
                dict(instance.answer_key or {}),
                override,
                overlay_identity=identity,
            )
            instance.answer_key = answer_key
            instance.exercise_type = str(
                answer_key.get("overlay_contract", {}).get("graded_as")
                or "phrase_builder"
            )

    active_exercise_type = instance.exercise_type
    if active_exercise_type in {"reverse_typing", "perfect_form_typing"}:
        prompt["clue_i18n"] = {
            "en": translations.get("en"),
            "fa": translations.get("fa"),
        }
        prompt["clue"] = translations.get("en") or prompt.get("clue")

    if active_exercise_type == "meaning_multiple_choice":
        prompt["choices"] = await _localize_meaning_choices(
            session,
            release.id,
            list(prompt.get("choices", [])),
        )

    if active_exercise_type == "meaning_matching":
        prompt["right_items"] = await _localize_matching_items(
            session,
            release.id,
            list(prompt.get("right_items", [])),
        )

    prompt["placeholder_i18n"] = _placeholder_i18n(active_exercise_type)
    prompt["tap_hint_i18n"] = _tap_hint_i18n(active_exercise_type)

    instance.prompt = prompt
    instance.contract_version = (
        PROMPT_CONTRACT_VERSION_V4 if deep else PROMPT_CONTRACT_VERSION
    )
    instance.prompt_checksum = hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    await session.flush()
    return instance


async def _pedagogy(session: AsyncSession, version_id: UUID) -> VerbPedagogyIn | None:
    row = await session.scalar(
        select(VersionLocalization).where(
            VersionLocalization.version_id == version_id,
            VersionLocalization.field == PEDAGOGY_FIELD,
            VersionLocalization.locale == PEDAGOGY_LOCALE,
            VersionLocalization.position == 0,
        )
    )
    if row is None:
        return None
    return VerbPedagogyIn.model_validate_json(row.value)


def teaching_feedback_from_prompt(prompt: dict, *, correct: bool) -> dict | None:
    if correct:
        return None
    lesson = prompt.get("lesson") if isinstance(prompt, dict) else None
    if not isinstance(lesson, dict):
        return None
    block = lesson.get("teaching_block")
    if isinstance(block, dict):
        return {
            "why_i18n": block.get("explanation_i18n"),
            "rule_i18n": block.get("rule_i18n"),
            "correct_example_de": block.get("corrected_example_de")
            or block.get("example_de"),
        }
    teaching = lesson.get("teaching_feedback")
    if isinstance(teaching, dict):
        return teaching
    mistakes = lesson.get("mistakes")
    if isinstance(mistakes, list) and mistakes:
        first = mistakes[0]
        if isinstance(first, dict):
            return {
                "why_i18n": first.get("why_i18n"),
                "rule_i18n": lesson.get("explanation_i18n"),
                "correct_example_de": first.get("correct_de"),
            }
    explanation = lesson.get("explanation_i18n")
    example_de = lesson.get("example_de")
    if explanation or example_de:
        return {
            "why_i18n": explanation if isinstance(explanation, dict) else None,
            "rule_i18n": explanation if isinstance(explanation, dict) else None,
            "correct_example_de": example_de if isinstance(example_de, str) else None,
        }
    return None


async def _translations(session: AsyncSession, version_id: UUID) -> dict[str, str]:
    rows = (
        await session.execute(
            select(VersionLocalization.locale, VersionLocalization.value).where(
                VersionLocalization.version_id == version_id,
                VersionLocalization.field == "translation",
                VersionLocalization.position == 0,
                VersionLocalization.locale.in_(["en", "fa"]),
            )
        )
    ).all()
    return {str(locale): str(value) for locale, value in rows}


async def _release_translation_rows(
    session: AsyncSession,
    release_id: UUID,
) -> list[tuple[UUID, str, str]]:
    return list(
        (
            await session.execute(
                select(
                    VersionLocalization.version_id,
                    VersionLocalization.locale,
                    VersionLocalization.value,
                )
                .join(
                    ReleaseActivity,
                    ReleaseActivity.content_version_id == VersionLocalization.version_id,
                )
                .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
                .where(
                    CourseDay.release_id == release_id,
                    VersionLocalization.field == "translation",
                    VersionLocalization.position == 0,
                    VersionLocalization.locale.in_(["en", "fa"]),
                )
            )
        ).all()
    )


async def _localize_meaning_choices(
    session: AsyncSession,
    release_id: UUID,
    choices: list[dict],
) -> list[dict]:
    rows = await _release_translation_rows(session, release_id)
    by_version: dict[UUID, dict[str, str]] = {}
    for version_id, locale, value in rows:
        by_version.setdefault(version_id, {})[str(locale)] = str(value)
    by_fa = {
        values["fa"]: values
        for values in by_version.values()
        if values.get("fa")
    }
    result: list[dict] = []
    for choice in choices:
        localized = dict(choice)
        fa = str(choice.get("text", ""))
        pair = by_fa.get(fa, {"fa": fa})
        localized["text_fa"] = pair.get("fa", fa)
        localized["text_en"] = pair.get("en", fa)
        localized["text"] = localized["text_en"]
        result.append(localized)
    return result


async def _localize_matching_items(
    session: AsyncSession,
    release_id: UUID,
    items: list[dict],
) -> list[dict]:
    rows = await _release_translation_rows(session, release_id)
    by_fa: dict[str, str] = {}
    grouped: dict[UUID, dict[str, str]] = {}
    for version_id, locale, value in rows:
        grouped.setdefault(version_id, {})[str(locale)] = str(value)
    for values in grouped.values():
        if values.get("fa") and values.get("en"):
            by_fa[values["fa"]] = values["en"]

    result: list[dict] = []
    for item in items:
        localized = dict(item)
        fa = str(item.get("text", ""))
        localized["text_fa"] = fa
        localized["text_en"] = by_fa.get(fa, fa)
        localized["text"] = localized["text_en"]
        result.append(localized)
    return result


def _placeholder_i18n(exercise_type: str) -> dict[str, str] | None:
    if exercise_type in {"reverse_typing", "example_cloze"}:
        return {
            "en": "Type the German verb…",
            "fa": "فعل آلمانی را تایپ کن…",
        }
    if exercise_type == "perfect_form_typing":
        return {
            "en": "e.g. haben entwickelt",
            "fa": "مثلاً haben entwickelt",
        }
    return None


def _tap_hint_i18n(exercise_type: str) -> dict[str, str] | None:
    if exercise_type in {"sentence_order", "phrase_builder"}:
        return {
            "en": (
                "Tap the chunks in order. Tap an answer chunk again to remove it."
            ),
            "fa": (
                "تکه‌ها را به‌ترتیب لمس کن؛ برای حذف، دوباره روی تکه‌ی انتخاب‌شده بزن."
            ),
        }
    if exercise_type == "meaning_matching":
        return {
            "en": "Choose a German verb, then tap its matching meaning.",
            "fa": "اول فعل آلمانی را انتخاب کن، بعد معنی متناظر را لمس کن.",
        }
    return None
