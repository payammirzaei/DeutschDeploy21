from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class VerbGrammarIn(BaseModel):
    perfect_auxiliary: Literal["haben", "sein"]
    participle_ii: str = Field(min_length=2, max_length=120)
    preterite: str | None = Field(default=None, max_length=120)
    separable: bool = False
    separable_prefix: str | None = Field(default=None, max_length=40)
    reflexive: bool = False
    regularity: Literal["regular", "irregular", "mixed"] = "regular"
    governed_case: str | None = Field(default=None, max_length=24)
    governed_preposition: str | None = Field(default=None, max_length=80)


class VerbClassificationIn(BaseModel):
    cefr: CefrLevel
    domains: list[str] = Field(default_factory=list, max_length=12)
    register: Literal["neutral", "formal", "informal", "technical"] = "neutral"


class VerbExampleIn(BaseModel):
    external_id: str = Field(min_length=4, max_length=180)
    de: str = Field(min_length=4, max_length=600)
    fa: str | None = Field(default=None, max_length=900)
    en: str | None = Field(default=None, max_length=900)
    skill: str | None = Field(default=None, max_length=120)


class LocalizedNote(BaseModel):
    en: str = Field(min_length=1, max_length=1200)
    fa: str = Field(min_length=1, max_length=1200)


class VerbStructureIn(BaseModel):
    pattern_de: str = Field(min_length=2, max_length=240)
    note: LocalizedNote


class VerbMistakeIn(BaseModel):
    wrong_de: str = Field(min_length=2, max_length=600)
    correct_de: str = Field(min_length=2, max_length=600)
    why: LocalizedNote


class VerbContrastIn(BaseModel):
    lemma: str = Field(min_length=2, max_length=120)
    difference: LocalizedNote


class VerbInterviewUseIn(BaseModel):
    model_answer_de: str = Field(min_length=4, max_length=900)
    note: LocalizedNote


class VerbPraesensIn(BaseModel):
    ich: str = Field(min_length=1, max_length=80)
    du: str = Field(min_length=1, max_length=80)
    er_sie_es: str = Field(min_length=1, max_length=80)
    wir: str = Field(min_length=1, max_length=80)
    ihr: str = Field(min_length=1, max_length=80)
    sie_Sie: str = Field(min_length=1, max_length=80)


class VerbPedagogyIn(BaseModel):
    """Optional deep-teaching metadata layered onto a verb version."""

    pronunciation_hint: str | None = Field(default=None, max_length=120)
    usage_notes: LocalizedNote | None = None
    praesens: VerbPraesensIn | None = None
    structures: list[VerbStructureIn] = Field(default_factory=list, max_length=8)
    mistakes: list[VerbMistakeIn] = Field(default_factory=list, max_length=6)
    contrasts: list[VerbContrastIn] = Field(default_factory=list, max_length=6)
    collocations: list[str] = Field(default_factory=list, max_length=12)
    related: list[str] = Field(default_factory=list, max_length=12)
    interview_uses: list[VerbInterviewUseIn] = Field(default_factory=list, max_length=6)
    grammar_tags: list[str] = Field(default_factory=list, max_length=16)


class VerbImportIn(BaseModel):
    external_id: str = Field(pattern=r"^verb\.[a-z0-9._-]+$", max_length=180)
    type: Literal["verb"] = "verb"
    canonical_language: Literal["de"] = "de"
    lemma: str = Field(min_length=2, max_length=120)
    display_infinitive: str | None = Field(default=None, max_length=120)
    translations: dict[str, list[str]]
    grammar: VerbGrammarIn
    classification: VerbClassificationIn
    examples: list[VerbExampleIn] = Field(min_length=1, max_length=12)
    pedagogy: VerbPedagogyIn | None = None

    @model_validator(mode="after")
    def validate_learning_contract(self) -> "VerbImportIn":
        if "fa" not in self.translations or not self.translations["fa"]:
            raise ValueError("translations.fa requires at least one value")
        if "en" not in self.translations or not self.translations["en"]:
            raise ValueError("translations.en requires at least one value")
        if self.grammar.separable and not self.grammar.separable_prefix:
            raise ValueError("separable verbs require separable_prefix")
        if not self.grammar.separable and self.grammar.separable_prefix:
            raise ValueError("separable_prefix is only valid for separable verbs")
        return self


class ImportRowResult(BaseModel):
    external_id: str
    action: Literal["create", "update", "unchanged"]
    checksum: str


class VerbImportReport(BaseModel):
    total: int
    creates: int
    updates: int
    unchanged: int
    rows: list[ImportRowResult]


class ImportApplyResult(BaseModel):
    imported: int
    created: int
    updated: int
    unchanged: int


class PublishResult(BaseModel):
    item_id: UUID
    external_id: str
    version_id: UUID
    version_number: int
    checksum: str
    reused_existing_version: bool = False


class ExampleView(BaseModel):
    external_id: str
    de: str
    fa: str | None = None
    en: str | None = None
    skill: str | None = None


class VerbView(BaseModel):
    item_id: UUID
    external_id: str
    version_id: UUID
    version_number: int
    lemma: str
    infinitive: str
    perfect_auxiliary: str
    participle_ii: str
    preterite: str | None
    separable: bool
    separable_prefix: str | None
    reflexive: bool
    regularity: str
    cefr: str
    register: str
    translations: dict[str, list[str]]
    examples: list[ExampleView]
    pedagogy: VerbPedagogyIn | None = None


class DraftVerbView(BaseModel):
    item_id: UUID
    external_id: str
    status: str
    lemma: str
    cefr: str
    source_checksum: str


class VersionSummary(BaseModel):
    version_id: UUID
    version_number: int
    checksum: str
    published_at: str
