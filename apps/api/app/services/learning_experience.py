import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentVersion, VersionExample, VersionLocalization
from app.models.learning import ActivityInstance, CourseDay, CourseRelease, ReleaseActivity

PROMPT_CONTRACT_VERSION = 2

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

    example = await session.scalar(
        select(VersionExample)
        .where(VersionExample.version_id == version.id)
        .order_by(VersionExample.sort_order, VersionExample.external_id)
        .limit(1)
    )
    translations = await _translations(session, version.id)
    prompt = dict(instance.prompt)
    exercise_type = instance.exercise_type

    question_i18n = QUESTION_I18N.get(exercise_type)
    if question_i18n:
        prompt["question_i18n"] = question_i18n
        prompt["question"] = question_i18n["en"]

    prompt["instruction_locale_default"] = "en"
    prompt["lesson"] = {
        "title_i18n": {
            "en": "Learn it in context",
            "fa": "یادگیری در متن",
        },
        "goal_i18n": GOAL_I18N.get(exercise_type, {}),
        "explanation_i18n": EXPLANATION_I18N.get(exercise_type, {}),
        "example_de": example.text_de if example else None,
        "example_i18n": {
            "en": example.text_en if example else None,
            "fa": example.text_fa if example else None,
        },
        "meaning_i18n": {
            "en": translations.get("en"),
            "fa": translations.get("fa"),
        },
        "grammar": {
            "cefr": version.cefr,
        },
    }

    if exercise_type in {"reverse_typing", "perfect_form_typing"}:
        prompt["clue_i18n"] = {
            "en": translations.get("en"),
            "fa": translations.get("fa"),
        }
        prompt["clue"] = translations.get("en") or prompt.get("clue")

    if exercise_type == "meaning_multiple_choice":
        prompt["choices"] = await _localize_meaning_choices(
            session,
            release.id,
            list(prompt.get("choices", [])),
        )

    if exercise_type == "meaning_matching":
        prompt["right_items"] = await _localize_matching_items(
            session,
            release.id,
            list(prompt.get("right_items", [])),
        )

    prompt["placeholder_i18n"] = _placeholder_i18n(exercise_type)
    prompt["tap_hint_i18n"] = _tap_hint_i18n(exercise_type)

    instance.prompt = prompt
    instance.contract_version = PROMPT_CONTRACT_VERSION
    instance.prompt_checksum = hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    await session.flush()
    return instance


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
