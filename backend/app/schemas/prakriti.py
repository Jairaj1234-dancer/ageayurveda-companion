from pydantic import BaseModel, Field


class PrakritiQuestion(BaseModel):
    id: int
    question_en: str
    question_hi: str
    category: str  # physical, physiological, psychological
    options: list["PrakritiOption"]


class PrakritiOption(BaseModel):
    label_en: str
    label_hi: str
    dosha: str  # vata, pitta, kapha


class PrakritiSubmission(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    answers: dict[str, str]  # {question_id: dosha}
    language: str = Field(default="en", max_length=5)


class DoshaScore(BaseModel):
    vata: int
    pitta: int
    kapha: int


class PrakritiResultOut(BaseModel):
    constitution: str
    scores: DoshaScore
    description_en: str
    description_hi: str
    diet: list[str]
    lifestyle: list[str]
    products: list[str]  # product slugs
