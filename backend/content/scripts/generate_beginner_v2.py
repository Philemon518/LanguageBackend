"""Generate the deterministic, curated beginner v2 curriculum seed."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "content" / "seeds" / "beginner_v2.json"


class WordTarget(NamedTuple):
    traditional: str
    jyutping: str
    english: str
    focus_token: str | None = None


class SentenceTarget(NamedTuple):
    traditional: str
    jyutping: str
    english: str
    tokens: tuple[str, ...]
    cloze_answer: str


class LessonBundle(NamedTuple):
    title: str
    words: tuple[WordTarget, ...]
    sentences: tuple[SentenceTarget, ...]
    review_words: tuple[WordTarget, ...] = ()


UNITS = (
    ("v2-unit-sound", "Sound and Tone Foundations", "sound"),
    ("v2-unit-components", "Character Components", "components"),
    ("v2-unit-vocabulary", "Cantonese in Context", "vocabulary"),
    ("v2-unit-grammar", "Building Useful Sentences", "grammar"),
)

TONE_LABELS = {
    1: "Tone 1 · high level",
    2: "Tone 2 · rising",
    3: "Tone 3 · mid level",
    4: "Tone 4 · low falling",
    5: "Tone 5 · low rising",
    6: "Tone 6 · low level",
}

SOUND_BUNDLES = (
    LessonBundle(
        "I, water, and drinks",
        (
            WordTarget("我", "ngo5", "I; me"),
            WordTarget("水", "seoi2", "water"),
            WordTarget("飲", "jam2", "drink"),
            WordTarget("茶", "caa4", "tea"),
        ),
        (
            SentenceTarget(
                "我飲水。",
                "ngo5 jam2 seoi2",
                "I drink water.",
                ("我", "飲", "水"),
                "飲",
            ),
            SentenceTarget(
                "我飲茶。",
                "ngo5 jam2 caa4",
                "I drink tea.",
                ("我", "飲", "茶"),
                "茶",
            ),
        ),
    ),
    LessonBundle(
        "Eating and trying",
        (
            WordTarget("食", "sik6", "eat"),
            WordTarget("飯", "faan6", "rice; meal"),
            WordTarget("試", "si3", "try"),
            WordTarget("有", "jau5", "have"),
        ),
        (
            SentenceTarget(
                "我食飯。",
                "ngo5 sik6 faan6",
                "I eat a meal.",
                ("我", "食", "飯"),
                "食",
            ),
            SentenceTarget(
                "我有飯。",
                "ngo5 jau5 faan6",
                "I have a meal.",
                ("我", "有", "飯"),
                "有",
            ),
        ),
        (WordTarget("我", "ngo5", "I; me"),),
    ),
    LessonBundle(
        "Books, people, and going",
        (
            WordTarget("書", "syu1", "book"),
            WordTarget("去", "heoi3", "go"),
            WordTarget("人", "jan4", "person"),
            WordTarget("衫", "saam1", "shirt"),
        ),
        (
            SentenceTarget(
                "我有書。",
                "ngo5 jau5 syu1",
                "I have a book.",
                ("我", "有", "書"),
                "書",
            ),
            SentenceTarget(
                "我去。",
                "ngo5 heoi3",
                "I go.",
                ("我", "去"),
                "去",
            ),
        ),
        (
            WordTarget("我", "ngo5", "I; me"),
            WordTarget("有", "jau5", "have"),
        ),
    ),
)

COMPONENT_BUNDLES = (
    LessonBundle(
        "People, good, and understanding",
        (
            WordTarget("休", "jau1", "rest"),
            WordTarget("好", "hou2", "good"),
            WordTarget("明", "ming4", "understand; bright"),
            WordTarget("問", "man6", "ask"),
        ),
        (
            SentenceTarget(
                "我明白。",
                "ngo5 ming4 baak6",
                "I understand.",
                ("我", "明白"),
                "明",
            ),
            SentenceTarget(
                "今日好熱。",
                "gam1 jat6 hou2 jit6",
                "It is hot today.",
                ("今日", "好熱"),
                "好",
            ),
        ),
        (WordTarget("我", "ngo5", "I; me"),),
    ),
    LessonBundle(
        "Language, meals, and wanting",
        (
            WordTarget("語", "jyu5", "language"),
            WordTarget("飯", "faan6", "rice; meal"),
            WordTarget("時", "si4", "time"),
            WordTarget("想", "soeng2", "want; think"),
        ),
        (
            SentenceTarget(
                "我食飯。",
                "ngo5 sik6 faan6",
                "I eat a meal.",
                ("我", "食", "飯"),
                "飯",
            ),
            SentenceTarget(
                "我想飲茶。",
                "ngo5 soeng2 jam2 caa4",
                "I want to drink tea.",
                ("我", "想", "飲茶"),
                "想",
            ),
        ),
        (
            WordTarget("我", "ngo5", "I; me"),
            WordTarget("食", "sik6", "eat"),
            WordTarget("茶", "caa4", "tea"),
        ),
    ),
)

COMPONENTS = (
    (("亻", "semantic"), ("木", "semantic")),
    (("女", "semantic"), ("子", "semantic")),
    (("日", "semantic"), ("月", "semantic")),
    (("門", "semantic"), ("口", "semantic")),
    (("言", "semantic"), ("吾", "phonetic")),
    (("飠", "semantic"), ("反", "phonetic")),
    (("日", "semantic"), ("寺", "phonetic")),
    (("相", "phonetic"), ("心", "semantic")),
)

VOCAB_BUNDLES = (
    LessonBundle(
        "Greetings and thanks",
        (
            WordTarget("你好", "nei5 hou2", "hello"),
            WordTarget("唔該", "m4 goi1", "please; thanks for a service"),
            WordTarget("多謝", "do1 ze6", "thank you for a gift or favor"),
            WordTarget("早晨", "zou2 san4", "good morning"),
        ),
        (
            SentenceTarget(
                "你好，我叫阿明。",
                "nei5 hou2 ngo5 giu3 aa3 ming4",
                "Hello, my name is Ah Ming.",
                ("你好", "我叫", "阿明"),
                "你好",
            ),
            SentenceTarget(
                "多謝你幫我。",
                "do1 ze6 nei5 bong1 ngo5",
                "Thank you for helping me.",
                ("多謝", "你幫我"),
                "多謝",
            ),
        ),
    ),
    LessonBundle(
        "Daily places and travel",
        (
            WordTarget("再見", "zoi3 gin3", "goodbye"),
            WordTarget("屋企", "uk1 kei2", "home"),
            WordTarget("學校", "hok6 haau6", "school"),
            WordTarget("巴士", "baa1 si2", "bus"),
        ),
        (
            SentenceTarget(
                "我而家返屋企。",
                "ngo5 ji4 gaa1 faan1 uk1 kei2",
                "I am going home now.",
                ("我", "而家", "返屋企"),
                "屋企",
            ),
            SentenceTarget(
                "我搭巴士去學校。",
                "ngo5 daap3 baa1 si2 heoi3 hok6 haau6",
                "I take the bus to school.",
                ("我", "搭巴士", "去學校"),
                "巴士",
            ),
        ),
        (WordTarget("我", "ngo5", "I; me"),),
    ),
    LessonBundle(
        "Food, water, and essentials",
        (
            WordTarget("茶餐廳", "caa4 caan1 teng1", "Hong Kong-style café"),
            WordTarget("飯", "faan6", "rice; meal"),
            WordTarget("水", "seoi2", "water"),
            WordTarget("廁所", "ci3 so2", "toilet; restroom"),
        ),
        (
            SentenceTarget(
                "唔該，我想要杯水。",
                "m4 goi1 ngo5 soeng2 jiu3 bui1 seoi2",
                "Please, I would like a glass of water.",
                ("唔該", "我想要", "杯水"),
                "水",
            ),
            SentenceTarget(
                "請問廁所喺邊度？",
                "cing2 man6 ci3 so2 hai2 bin1 dou6",
                "Excuse me, where is the restroom?",
                ("請問", "廁所", "喺邊度"),
                "廁所",
            ),
        ),
        (WordTarget("唔該", "m4 goi1", "please; thanks for a service"),),
    ),
)

GRAMMAR_BUNDLES = (
    LessonBundle(
        "Who I am and what I have",
        (
            WordTarget("我係學生", "ngo5 hai6 hok6 saang1", "I am a student", "係"),
            WordTarget("我唔係老師", "ngo5 m4 hai6 lou5 si1", "I am not a teacher", "唔"),
            WordTarget("我有一本書", "ngo5 jau5 jat1 bun2 syu1", "I have a book", "有"),
            WordTarget("我冇時間", "ngo5 mou5 si4 gaan3", "I do not have time", "冇"),
        ),
        (
            SentenceTarget(
                "我係學生。",
                "ngo5 hai6 hok6 saang1",
                "I am a student.",
                ("我", "係", "學生"),
                "係",
            ),
            SentenceTarget(
                "我有一本書。",
                "ngo5 jau5 jat1 bun2 syu1",
                "I have a book.",
                ("我", "有", "一本書"),
                "有",
            ),
        ),
    ),
    LessonBundle(
        "Asking, wanting, and everyday actions",
        (
            WordTarget("你去邊度呀", "nei5 heoi3 bin1 dou6 aa3", "Where are you going?", "邊度"),
            WordTarget("我想飲茶", "ngo5 soeng2 jam2 caa4", "I want to drink tea", "想"),
            WordTarget(
                "唔該畀杯水我",
                "m4 goi1 bei2 bui1 seoi2 ngo5",
                "Please give me a glass of water",
                "唔該",
            ),
            WordTarget("我食咗飯", "ngo5 sik6 zo2 faan6", "I have eaten", "咗"),
        ),
        (
            SentenceTarget(
                "我想飲茶。",
                "ngo5 soeng2 jam2 caa4",
                "I want to drink tea.",
                ("我", "想", "飲茶"),
                "想",
            ),
            SentenceTarget(
                "唔該畀杯水我。",
                "m4 goi1 bei2 bui1 seoi2 ngo5",
                "Please give me a glass of water.",
                ("唔該", "畀杯水", "我"),
                "唔該",
            ),
        ),
    ),
)

BUNDLE_GROUPS = (
    ("sound", SOUND_BUNDLES),
    ("component", COMPONENT_BUNDLES),
    ("vocabulary", VOCAB_BUNDLES),
    ("grammar", GRAMMAR_BUNDLES),
)


def tones(jyutping: str) -> list[int]:
    return [int(syllable[-1]) for syllable in jyutping.split()]


def changed_final_tone(jyutping: str, tone: int) -> str:
    syllables = jyutping.split()
    syllables[-1] = f"{syllables[-1][:-1]}{tone}"
    return " ".join(syllables)


def pronunciation_without_tones(jyutping: str) -> str:
    return " ".join(syllable[:-1] for syllable in jyutping.split())


def format_components(component_data: tuple[tuple[str, str], ...]) -> str:
    return " · ".join(f"{glyph} ({role})" for glyph, role in component_data)


def intro_prompt(lesson_type: str, *, first_lesson: bool, first_word: bool) -> str:
    if lesson_type == "sound" and first_lesson and first_word:
        return "Meet your first Cantonese word"
    if lesson_type == "sound":
        return "Meet this Cantonese word"
    if lesson_type == "component":
        return "Meet this character and its parts"
    if lesson_type == "vocabulary":
        return "Meet this phrase"
    return "Meet this sentence pattern"


def build_intro_step(
    step_id: str,
    objective_id: str,
    word: WordTarget,
    lesson_type: str,
    *,
    first_lesson: bool,
    first_word: bool,
    component_data: tuple[tuple[str, str], ...] | None = None,
    focus_token: str | None = None,
) -> dict:
    tone = tones(word.jyutping)[-1]
    metadata: dict[str, str] = {
        "objective_id": objective_id,
        "character": word.traditional,
        "pronunciation": pronunciation_without_tones(word.jyutping),
        "jyutping": word.jyutping,
        "tone_label": TONE_LABELS.get(tone, f"Tone {tone}"),
        "meaning": word.english,
        "representation_pair": "word-overview",
    }
    if lesson_type == "sound":
        metadata["word_type"] = "word"
    elif lesson_type == "component":
        metadata["word_type"] = "character"
        if component_data:
            metadata["components_label"] = format_components(component_data)
    elif lesson_type == "vocabulary":
        metadata["word_type"] = "phrase"
    elif lesson_type == "grammar":
        metadata["word_type"] = "pattern"
        if focus_token:
            metadata["focus_token"] = focus_token

    return {
        "id": step_id,
        "type": "word_intro",
        "skill": "reading",
        "prompt": intro_prompt(
            lesson_type,
            first_lesson=first_lesson,
            first_word=first_word,
        ),
        "audio": {"text": word.traditional},
        "options": [{"id": "intro-ready", "label": "I know this word now"}],
        "correct_option_id": "intro-ready",
        "reveal_jyutping": word.jyutping,
        "reveal_character": word.traditional,
        "reveal_english": word.english,
        "metadata": metadata,
    }


def make_word_drills(
    *,
    step_prefix: str,
    objective_id: str,
    word: WordTarget,
    lesson_type: str,
    include_tone: bool,
) -> list[dict]:
    tone = tones(word.jyutping)[-1]
    other_tones = [candidate for candidate in range(1, 7) if candidate != tone][:2]
    choice_tones = [tone, *other_tones]
    steps = [
        {
            "id": f"{step_prefix}-meaning",
            "type": "select_meaning",
            "skill": "listening",
            "prompt": f"Listen. What does {word.traditional} mean?",
            "audio": {"text": word.traditional},
            "options": [
                {"id": "meaning-correct", "label": word.english},
                {"id": "meaning-distractor-1", "label": "a different place"},
                {"id": "meaning-distractor-2", "label": "a different action"},
            ],
            "correct_option_id": "meaning-correct",
            "reveal_jyutping": word.jyutping,
            "reveal_character": word.traditional,
            "reveal_english": word.english,
            "metadata": {
                "objective_id": objective_id,
                "representation_pair": "traditional-jyutping",
            },
        },
        {
            "id": f"{step_prefix}-jyutping",
            "type": "select_jyutping",
            "skill": "listening",
            "prompt": f"Listen again. Choose the Jyutping for {word.traditional}.",
            "audio": {"text": word.traditional},
            "options": [
                {
                    "id": "jyutping-correct",
                    "label": word.jyutping,
                    "jyutping": word.jyutping,
                },
                {
                    "id": "jyutping-distractor-1",
                    "label": changed_final_tone(word.jyutping, other_tones[0]),
                    "jyutping": changed_final_tone(word.jyutping, other_tones[0]),
                },
                {
                    "id": "jyutping-distractor-2",
                    "label": changed_final_tone(word.jyutping, other_tones[1]),
                    "jyutping": changed_final_tone(word.jyutping, other_tones[1]),
                },
            ],
            "correct_option_id": "jyutping-correct",
            "reveal_jyutping": word.jyutping,
            "reveal_character": word.traditional,
            "metadata": {"objective_id": objective_id, "tones": tones(word.jyutping)},
        },
        {
            "id": f"{step_prefix}-speak",
            "type": "speak",
            "skill": "speaking",
            "prompt": f"Say {word.traditional} after listening.",
            "audio": {"text": word.traditional},
            "reveal_jyutping": word.jyutping,
            "reveal_character": word.traditional,
            "metadata": {
                "expected": word.jyutping,
                "expected_text": word.traditional,
                "objective_id": objective_id,
            },
        },
        {
            "id": f"{step_prefix}-character",
            "type": "select_character",
            "skill": "reading",
            "prompt": f"Choose the Traditional Chinese for {word.jyutping}.",
            "options": [
                {
                    "id": "character-correct",
                    "label": word.traditional,
                    "audio": {"text": word.traditional},
                },
                {"id": "character-distractor-1", "label": "山", "audio": {"text": "山"}},
                {"id": "character-distractor-2", "label": "火", "audio": {"text": "火"}},
            ],
            "correct_option_id": "character-correct",
            "reveal_jyutping": word.jyutping,
            "reveal_english": word.english,
            "metadata": {"objective_id": objective_id},
        },
    ]
    if include_tone:
        steps.append(
            {
                "id": f"{step_prefix}-tone",
                "type": "select_tone",
                "skill": "listening",
                "prompt": f"Listen closely. Which tone does {word.traditional} use?",
                "audio": {"text": word.traditional},
                "options": [
                    {"id": f"tone-{candidate}", "label": f"Tone {candidate}"}
                    for candidate in choice_tones
                ],
                "correct_option_id": f"tone-{tone}",
                "reveal_jyutping": word.jyutping,
                "metadata": {"tone": tone, "objective_id": objective_id},
            }
        )
    else:
        steps.append(
            {
                "id": f"{step_prefix}-match",
                "type": "match",
                "skill": "reading",
                "prompt": f"Match {word.traditional} with its meaning.",
                "options": [
                    {"id": "match-correct", "label": word.english},
                    {"id": "match-distractor-1", "label": "an unrelated object"},
                    {"id": "match-distractor-2", "label": "an unrelated action"},
                ],
                "correct_option_id": "match-correct",
                "metadata": {"objective_id": objective_id},
            }
        )
    return steps


def lesson_word_labels(bundle: LessonBundle) -> list[str]:
    return [word.traditional for word in bundle.words]


def cloze_distractors(answer: str, lesson_words: list[str]) -> list[str]:
    return [word for word in lesson_words if word != answer][:2]


def make_sentence_steps(
    *,
    step_prefix: str,
    objective_id: str,
    sentence: SentenceTarget,
    lesson_words: list[str],
) -> list[dict]:
    cloze_text = sentence.traditional.replace(sentence.cloze_answer, "＿＿", 1)
    distractors = cloze_distractors(sentence.cloze_answer, lesson_words)
    word_options = [
        {
            "id": f"{step_prefix}-word-{index}",
            "label": token,
            "audio": {"text": token},
        }
        for index, token in enumerate(sentence.tokens, start=1)
    ]
    return [
        {
            "id": f"{step_prefix}-cloze",
            "type": "cloze",
            "skill": "writing",
            "prompt": f"Complete the sentence: {cloze_text}",
            "audio": {"text": sentence.traditional},
            "options": [
                {
                    "id": "cloze-correct",
                    "label": sentence.cloze_answer,
                    "audio": {"text": sentence.cloze_answer},
                },
                *[
                    {
                        "id": f"cloze-distractor-{index}",
                        "label": distractor,
                        "audio": {"text": distractor},
                    }
                    for index, distractor in enumerate(distractors, start=1)
                ],
            ],
            "correct_option_id": "cloze-correct",
            "reveal_jyutping": sentence.jyutping,
            "reveal_english": sentence.english,
            "metadata": {
                "expected": sentence.cloze_answer,
                "allow_manual_input": True,
                "objective_id": objective_id,
                "lesson_words": lesson_words,
            },
        },
        {
            "id": f"{step_prefix}-order",
            "type": "order_words",
            "skill": "writing",
            "prompt": f"Build: {sentence.english}",
            "options": word_options,
            "metadata": {
                "expected_order": [
                    f"{step_prefix}-word-{index}"
                    for index in range(1, len(sentence.tokens) + 1)
                ],
                "objective_id": objective_id,
            },
        },
        {
            "id": f"{step_prefix}-listen-order",
            "type": "order_words",
            "skill": "writing",
            "prompt": "Listen and build the sentence.",
            "audio": {"text": sentence.traditional},
            "options": [
                {
                    "id": f"{step_prefix}-audio-word-{index}",
                    "label": token,
                    "audio": {"text": token},
                }
                for index, token in enumerate(sentence.tokens, start=1)
            ],
            "reveal_jyutping": sentence.jyutping,
            "reveal_character": sentence.traditional,
            "reveal_english": sentence.english,
            "metadata": {
                "expected_order": [
                    f"{step_prefix}-audio-word-{index}"
                    for index in range(1, len(sentence.tokens) + 1)
                ],
                "objective_id": objective_id,
            },
        },
    ]


def cloze_choice_pool(bundle: LessonBundle, lesson_type: str) -> list[str]:
    if lesson_type == "grammar":
        return list(
            dict.fromkeys(
                word.focus_token
                for word in bundle.words
                if word.focus_token
            )
        )
    return lesson_word_labels(bundle)


def make_bundle_steps(
    lesson_id: str,
    bundle: LessonBundle,
    lesson_type: str,
    *,
    sort_order: int,
    first_lesson: bool,
    component_data: tuple[tuple[str, str], ...] | None = None,
) -> list[dict]:
    steps: list[dict] = []
    lesson_words = lesson_word_labels(bundle)
    choice_pool = cloze_choice_pool(bundle, lesson_type)
    objective_id = f"{lesson_id}-objective"

    for word_index, word in enumerate(bundle.words):
        word_components = (
            COMPONENTS[word_index] if lesson_type == "component" else None
        )
        focus_token = word.focus_token
        if lesson_type == "grammar" and focus_token is None:
            for sentence in bundle.sentences:
                if sentence.cloze_answer in word.traditional:
                    focus_token = sentence.cloze_answer
                    break
        steps.append(
            build_intro_step(
                f"{lesson_id}-ex-{word_index:02d}",
                f"{lesson_id}-obj-{word_index:02d}",
                word,
                lesson_type,
                first_lesson=first_lesson,
                first_word=word_index == 0,
                component_data=word_components,
                focus_token=focus_token,
            )
        )

    for word_index, word in enumerate(bundle.words):
        steps.extend(
            make_word_drills(
                step_prefix=f"{lesson_id}-w{word_index:02d}",
                objective_id=f"{lesson_id}-obj-{word_index:02d}",
                word=word,
                lesson_type=lesson_type,
                include_tone=lesson_type == "sound",
            )
        )

    for sentence_index, sentence in enumerate(bundle.sentences):
        steps.extend(
            make_sentence_steps(
                step_prefix=f"{lesson_id}-s{sentence_index:02d}",
                objective_id=objective_id,
                sentence=sentence,
                lesson_words=choice_pool,
            )
        )

    return steps


def lesson_title(bundle: LessonBundle) -> str:
    return " · ".join(word.traditional for word in bundle.words)


def generate_document() -> dict:
    units = []
    lessons = []
    lexemes = []
    characters = []
    previous_unit = None
    previous_lesson = None
    global_order = 0

    for unit_order, ((unit_id, title, phase), (lesson_type, bundles)) in enumerate(
        zip(UNITS, BUNDLE_GROUPS, strict=True), start=1
    ):
        units.append(
            {
                "id": unit_id,
                "title": title,
                "phase": phase,
                "sort_order": unit_order,
                "prerequisites": [previous_unit] if previous_unit else [],
            }
        )
        for sort_order, bundle in enumerate(bundles, start=1):
            global_order += 1
            lesson_id = f"v2-{lesson_type}-{sort_order:02d}"
            primary = bundle.words[0]
            capstone = bundle.sentences[0]
            component_data = COMPONENTS if lesson_type == "component" else None
            lessons.append(
                {
                    "id": lesson_id,
                    "unit_id": unit_id,
                    "title": lesson_title(bundle),
                    "lesson_type": lesson_type,
                    "sort_order": sort_order,
                    "prerequisites": [previous_lesson] if previous_lesson else [],
                    "objectives": [f"{lesson_id}-objective"],
                    "content": {
                        "target": {
                            "traditional": primary.traditional,
                            "jyutping": primary.jyutping,
                            "tone": tones(primary.jyutping)[-1],
                            "tones": tones(primary.jyutping),
                            "english": primary.english,
                            "theme": bundle.title,
                            "words": [
                                {
                                    "traditional": word.traditional,
                                    "jyutping": word.jyutping,
                                    "english": word.english,
                                }
                                for word in bundle.words
                            ],
                        },
                        "context": {
                            "traditional": capstone.traditional,
                            "jyutping": capstone.jyutping,
                            "tones": tones(capstone.jyutping),
                            "english": capstone.english,
                            "progression": global_order,
                        },
                        "vocabulary": [
                            {"lexeme_id": f"{lesson_id}-word-{index:02d}"}
                            for index, _ in enumerate(bundle.words)
                        ],
                        "steps": make_bundle_steps(
                            lesson_id,
                            bundle,
                            lesson_type,
                            sort_order=sort_order,
                            first_lesson=global_order == 1,
                            component_data=component_data,
                        ),
                    },
                }
            )
            for word_index, word in enumerate(bundle.words):
                lexemes.append(
                    {
                        "id": f"{lesson_id}-word-{word_index:02d}",
                        "traditional": word.traditional,
                        "jyutping": word.jyutping,
                        "tone": tones(word.jyutping)[-1],
                        "tones": tones(word.jyutping),
                        "english": word.english,
                        "tags": [phase, "beginner-v2"],
                        "difficulty": 1 + (global_order - 1) // 3,
                    }
                )
            if lesson_type == "component":
                for word_index, word in enumerate(bundle.words):
                    component_parts = COMPONENTS[word_index]
                    characters.append(
                        {
                            "id": f"{lesson_id}-character-{word_index:02d}",
                            "glyph": word.traditional,
                            "meaning": word.english,
                            "jyutping": word.jyutping,
                            "tone": tones(word.jyutping)[-1],
                            "tones": tones(word.jyutping),
                            "radical": component_parts[0][0],
                            "components": [
                                {"glyph": glyph, "role": role}
                                for glyph, role in component_parts
                            ],
                            "related_words": [capstone.traditional.replace("。", "")],
                        }
                    )
            previous_lesson = lesson_id
        previous_unit = unit_id

    lesson_count = len(lessons)
    return {
        "version": "2.0.0",
        "level": "beginner",
        "generator": {
            "name": "generate_beginner_v2.py",
            "deterministic": True,
            "lesson_count": lesson_count,
            "words_per_lesson": [3, 4],
            "exercises_per_lesson": [20, 35],
        },
        "units": units,
        "lexemes": lexemes,
        "characters": characters,
        "lessons": lessons,
        "stories": [],
    }


def curriculum_expectations() -> dict:
    doc = generate_document()
    lessons = doc["lessons"]
    steps = [
        step for lesson in lessons for step in lesson.get("content", {}).get("steps", [])
    ]
    units = doc["units"]
    return {
        "lesson_count": len(lessons),
        "lesson_types": dict(Counter(lesson["lesson_type"] for lesson in lessons)),
        "unit_lesson_counts": [
            sum(lesson.get("unit_id") == unit.get("id") for lesson in lessons)
            for unit in units
        ],
        "skills": dict(Counter(step["skill"] for step in steps)),
        "exercise_types": dict(Counter(step["type"] for step in steps)),
        "progression": [
            lesson["content"]["context"]["progression"] for lesson in lessons
        ],
    }


def main() -> None:
    document = generate_document()
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} with {len(document['lessons'])} lessons")


if __name__ == "__main__":
    main()
