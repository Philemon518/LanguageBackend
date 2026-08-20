"""Generate the deterministic, curated beginner v2 curriculum seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "content" / "seeds" / "beginner_v2.json"


class LessonSpec(NamedTuple):
    traditional: str
    jyutping: str
    english: str
    sentence: str
    sentence_jyutping: str
    sentence_english: str
    tokens: tuple[str, ...]
    cloze_answer: str | None = None


SOUND_SPECS = (
    LessonSpec("水", "seoi2", "water", "杯水喺度。", "bui1 seoi2 hai2 dou6", "The glass of water is here.", ("杯水", "喺度")),
    LessonSpec("飲", "jam2", "drink", "我飲水。", "ngo5 jam2 seoi2", "I drink water.", ("我", "飲", "水")),
    LessonSpec("試", "si3", "try", "我試吓。", "ngo5 si3 haa5", "Let me try.", ("我", "試吓")),
    LessonSpec("茶", "caa4", "tea", "我飲茶。", "ngo5 jam2 caa4", "I drink tea.", ("我", "飲", "茶")),
    LessonSpec("我", "ngo5", "I; me", "我係學生。", "ngo5 hai6 hok6 saang1", "I am a student.", ("我", "係", "學生")),
    LessonSpec("食", "sik6", "eat", "我食飯。", "ngo5 sik6 faan6", "I eat a meal.", ("我", "食", "飯")),
    LessonSpec("書", "syu1", "book", "我睇書。", "ngo5 tai2 syu1", "I read a book.", ("我", "睇", "書")),
    LessonSpec("衫", "saam1", "shirt", "件衫好靚。", "gin6 saam1 hou2 leng3", "The shirt is beautiful.", ("件衫", "好靚")),
    LessonSpec("去", "heoi3", "go", "我去學校。", "ngo5 heoi3 hok6 haau6", "I go to school.", ("我", "去", "學校")),
    LessonSpec("人", "jan4", "person", "佢係香港人。", "keoi5 hai6 hoeng1 gong2 jan4", "They are a Hongkonger.", ("佢", "係", "香港人")),
    LessonSpec("有", "jau5", "have", "我有時間。", "ngo5 jau5 si4 gaan3", "I have time.", ("我", "有", "時間")),
    LessonSpec("飯", "faan6", "rice; meal", "我食咗飯。", "ngo5 sik6 zo2 faan6", "I have eaten.", ("我", "食咗", "飯")),
)

COMPONENT_SPECS = (
    LessonSpec("休", "jau1", "rest", "我想休息。", "ngo5 soeng2 jau1 sik1", "I want to rest.", ("我", "想", "休息")),
    LessonSpec("好", "hou2", "good", "今日好熱。", "gam1 jat6 hou2 jit6", "It is hot today.", ("今日", "好熱")),
    LessonSpec("明", "ming4", "understand; bright", "我明白。", "ngo5 ming4 baak6", "I understand.", ("我", "明白")),
    LessonSpec("問", "man6", "ask", "我想問你。", "ngo5 soeng2 man6 nei5", "I want to ask you.", ("我", "想問", "你")),
    LessonSpec("語", "jyu5", "language", "我學粵語。", "ngo5 hok6 jyut6 jyu5", "I study Cantonese.", ("我", "學", "粵語")),
    LessonSpec("飯", "faan6", "rice; meal", "我食飯。", "ngo5 sik6 faan6", "I eat a meal.", ("我", "食", "飯")),
    LessonSpec("時", "si4", "time", "我冇時間。", "ngo5 mou5 si4 gaan3", "I do not have time.", ("我", "冇", "時間")),
    LessonSpec("想", "soeng2", "want; think", "我想飲茶。", "ngo5 soeng2 jam2 caa4", "I want to drink tea.", ("我", "想", "飲茶")),
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

VOCAB_SPECS = (
    LessonSpec("你好", "nei5 hou2", "hello", "你好，我叫阿明。", "nei5 hou2 ngo5 giu3 aa3 ming4", "Hello, my name is Ah Ming.", ("你好", "我叫", "阿明")),
    LessonSpec("唔該", "m4 goi1", "please; thanks for a service", "唔該，我想要杯水。", "m4 goi1 ngo5 soeng2 jiu3 bui1 seoi2", "Please, I would like a glass of water.", ("唔該", "我想要", "杯水")),
    LessonSpec("多謝", "do1 ze6", "thank you for a gift or favor", "多謝你幫我。", "do1 ze6 nei5 bong1 ngo5", "Thank you for helping me.", ("多謝", "你幫我")),
    LessonSpec("早晨", "zou2 san4", "good morning", "老師，早晨。", "lou5 si1 zou2 san4", "Good morning, teacher.", ("老師", "早晨")),
    LessonSpec("再見", "zoi3 gin3", "goodbye", "聽日再見。", "ting1 jat6 zoi3 gin3", "See you tomorrow.", ("聽日", "再見")),
    LessonSpec("屋企", "uk1 kei2", "home", "我而家返屋企。", "ngo5 ji4 gaa1 faan1 uk1 kei2", "I am going home now.", ("我", "而家", "返屋企")),
    LessonSpec("學校", "hok6 haau6", "school", "我搭巴士去學校。", "ngo5 daap3 baa1 si2 heoi3 hok6 haau6", "I take the bus to school.", ("我", "搭巴士", "去學校")),
    LessonSpec("巴士", "baa1 si2", "bus", "呢架巴士去中環。", "ni1 gaa3 baa1 si2 heoi3 zung1 waan4", "This bus goes to Central.", ("呢架巴士", "去", "中環")),
    LessonSpec("茶餐廳", "caa4 caan1 teng1", "Hong Kong-style café", "我哋去茶餐廳食飯。", "ngo5 dei6 heoi3 caa4 caan1 teng1 sik6 faan6", "We go to a cha chaan teng for a meal.", ("我哋", "去茶餐廳", "食飯")),
    LessonSpec("飯", "faan6", "rice; meal", "我想要一碗飯。", "ngo5 soeng2 jiu3 jat1 wun2 faan6", "I would like a bowl of rice.", ("我", "想要", "一碗飯")),
    LessonSpec("水", "seoi2", "water", "唔該畀杯水我。", "m4 goi1 bei2 bui1 seoi2 ngo5", "Please give me a glass of water.", ("唔該", "畀杯水", "我")),
    LessonSpec("廁所", "ci3 so2", "toilet; restroom", "請問廁所喺邊度？", "cing2 man6 ci3 so2 hai2 bin1 dou6", "Excuse me, where is the restroom?", ("請問", "廁所", "喺邊度")),
)

GRAMMAR_SPECS = (
    LessonSpec("我係學生", "ngo5 hai6 hok6 saang1", "I am a student", "我係學生。", "ngo5 hai6 hok6 saang1", "I am a student.", ("我", "係", "學生"), "係"),
    LessonSpec("我唔係老師", "ngo5 m4 hai6 lou5 si1", "I am not a teacher", "我唔係老師。", "ngo5 m4 hai6 lou5 si1", "I am not a teacher.", ("我", "唔係", "老師"), "唔"),
    LessonSpec("我有一本書", "ngo5 jau5 jat1 bun2 syu1", "I have a book", "我有一本書。", "ngo5 jau5 jat1 bun2 syu1", "I have a book.", ("我", "有", "一本書"), "有"),
    LessonSpec("我冇時間", "ngo5 mou5 si4 gaan3", "I do not have time", "我冇時間。", "ngo5 mou5 si4 gaan3", "I do not have time.", ("我", "冇", "時間"), "冇"),
    LessonSpec("你去邊度呀", "nei5 heoi3 bin1 dou6 aa3", "Where are you going?", "你去邊度呀？", "nei5 heoi3 bin1 dou6 aa3", "Where are you going?", ("你", "去", "邊度呀"), "邊度"),
    LessonSpec("我想飲茶", "ngo5 soeng2 jam2 caa4", "I want to drink tea", "我想飲茶。", "ngo5 soeng2 jam2 caa4", "I want to drink tea.", ("我", "想", "飲茶"), "想"),
    LessonSpec("唔該畀杯水我", "m4 goi1 bei2 bui1 seoi2 ngo5", "Please give me a glass of water", "唔該畀杯水我。", "m4 goi1 bei2 bui1 seoi2 ngo5", "Please give me a glass of water.", ("唔該", "畀杯水", "我"), "畀"),
    LessonSpec("我食咗飯", "ngo5 sik6 zo2 faan6", "I have eaten", "我食咗飯。", "ngo5 sik6 zo2 faan6", "I have eaten.", ("我", "食咗", "飯"), "咗"),
)

UNITS = (
    ("v2-unit-sound", "Sound and Tone Foundations", "sound", 12),
    ("v2-unit-components", "Character Components", "components", 8),
    ("v2-unit-vocabulary", "Cantonese in Context", "vocabulary", 12),
    ("v2-unit-grammar", "Building Useful Sentences", "grammar", 8),
)

TONE_LABELS = {
    1: "Tone 1 · high level",
    2: "Tone 2 · rising",
    3: "Tone 3 · mid level",
    4: "Tone 4 · low falling",
    5: "Tone 5 · low rising",
    6: "Tone 6 · low level",
}


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


def intro_prompt(lesson_type: str, sort_order: int) -> str:
    if lesson_type == "sound":
        return (
            "Meet your first Cantonese word"
            if sort_order == 1
            else "Meet this Cantonese word"
        )
    prompts = {
        "component": "Meet this character and its parts",
        "vocabulary": "Meet this phrase",
        "grammar": "Meet this sentence pattern",
    }
    return prompts[lesson_type]


def build_intro_step(
    prefix: str,
    objective: str,
    spec: LessonSpec,
    lesson_type: str,
    *,
    sort_order: int = 1,
    component_data: tuple[tuple[str, str], ...] | None = None,
) -> dict:
    tone = tones(spec.jyutping)[-1]
    metadata: dict[str, str] = {
        "objective_id": objective,
        "character": spec.traditional,
        "pronunciation": pronunciation_without_tones(spec.jyutping),
        "jyutping": spec.jyutping,
        "tone_label": TONE_LABELS.get(tone, f"Tone {tone}"),
        "meaning": spec.english,
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
        if spec.cloze_answer:
            metadata["focus_token"] = spec.cloze_answer

    return {
        "id": f"{prefix}-00",
        "type": "word_intro",
        "skill": "reading",
        "prompt": intro_prompt(lesson_type, sort_order),
        "audio": {"text": spec.traditional},
        "options": [{"id": "intro-ready", "label": "I know this word now"}],
        "correct_option_id": "intro-ready",
        "reveal_jyutping": spec.jyutping,
        "reveal_character": spec.traditional,
        "reveal_english": spec.english,
        "metadata": metadata,
    }


def make_steps(
    lesson_id: str,
    spec: LessonSpec,
    lesson_type: str,
    *,
    sort_order: int = 1,
    component_data: tuple[tuple[str, str], ...] | None = None,
) -> list[dict]:
    tone = tones(spec.jyutping)[-1]
    other_tones = [candidate for candidate in range(1, 7) if candidate != tone][:2]
    choice_tones = [tone, *other_tones]
    objective = f"{lesson_id}-objective"
    prefix = f"{lesson_id}-ex"
    cloze_answer = spec.cloze_answer or spec.traditional
    cloze_text = spec.sentence.replace(cloze_answer, "＿＿", 1)
    cloze_distractors = [
        value
        for value in ("我", "水", "好", "去", "食")
        if value != cloze_answer
    ][:2]
    sentence_word_options = [
        {
            "id": f"word-{index}",
            "label": token,
            "audio": {"text": token},
        }
        for index, token in enumerate(spec.tokens, start=1)
    ]
    steps = [
        {
            "id": f"{prefix}-01",
            "type": "select_meaning",
            "skill": "listening",
            "prompt": "Listen first. Choose the meaning.",
            "audio": {"text": spec.traditional},
            "options": [
                {"id": "meaning-correct", "label": spec.english},
                {"id": "meaning-distractor-1", "label": "a different place"},
                {"id": "meaning-distractor-2", "label": "a different action"},
            ],
            "correct_option_id": "meaning-correct",
            "reveal_jyutping": spec.jyutping,
            "reveal_character": spec.traditional,
            "reveal_english": spec.english,
            "metadata": {"objective_id": objective, "representation_pair": "traditional-jyutping"},
        },
        {
            "id": f"{prefix}-02",
            "type": "select_jyutping",
            "skill": "listening",
            "prompt": "Listen again. Choose the matching Jyutping.",
            "audio": {"text": spec.traditional},
            "options": [
                {"id": "jyutping-correct", "label": spec.jyutping, "jyutping": spec.jyutping},
                {
                    "id": "jyutping-distractor-1",
                    "label": changed_final_tone(spec.jyutping, other_tones[0]),
                    "jyutping": changed_final_tone(spec.jyutping, other_tones[0]),
                },
                {
                    "id": "jyutping-distractor-2",
                    "label": changed_final_tone(spec.jyutping, other_tones[1]),
                    "jyutping": changed_final_tone(spec.jyutping, other_tones[1]),
                },
            ],
            "correct_option_id": "jyutping-correct",
            "reveal_jyutping": spec.jyutping,
            "reveal_character": spec.traditional,
            "metadata": {"objective_id": objective, "tones": tones(spec.jyutping)},
        },
        {
            "id": f"{prefix}-03",
            "type": "speak",
            "skill": "speaking",
            "prompt": f"Say {spec.traditional} after listening.",
            "audio": {"text": spec.traditional},
            "reveal_jyutping": spec.jyutping,
            "reveal_character": spec.traditional,
            "metadata": {
                "expected": spec.jyutping,
                "expected_text": spec.traditional,
                "objective_id": objective,
            },
        },
        {
            "id": f"{prefix}-04",
            "type": "select_character",
            "skill": "reading",
            "prompt": f"Choose the Traditional Chinese for {spec.jyutping}.",
            "options": [
                {
                    "id": "character-correct",
                    "label": spec.traditional,
                    "audio": {"text": spec.traditional},
                },
                {
                    "id": "character-distractor-1",
                    "label": "山",
                    "audio": {"text": "山"},
                },
                {
                    "id": "character-distractor-2",
                    "label": "火",
                    "audio": {"text": "火"},
                },
            ],
            "correct_option_id": "character-correct",
            "reveal_jyutping": spec.jyutping,
            "reveal_english": spec.english,
            "metadata": {"objective_id": objective},
        },
    ]
    if lesson_type == "sound":
        steps.append(
            {
                "id": f"{prefix}-05",
                "type": "select_tone",
                "skill": "listening",
                "prompt": "Listen closely. Which tone do you hear?",
                "audio": {"text": spec.traditional},
                "options": [
                    {"id": f"tone-{candidate}", "label": f"Tone {candidate}"}
                    for candidate in choice_tones
                ],
                "correct_option_id": f"tone-{tone}",
                "reveal_jyutping": spec.jyutping,
                "metadata": {"tone": tone, "objective_id": objective},
            }
        )
    else:
        steps.append(
            {
                "id": f"{prefix}-05",
                "type": "match",
                "skill": "reading",
                "prompt": f"Match {spec.traditional} with its meaning.",
                "options": [
                    {"id": "match-correct", "label": spec.english},
                    {"id": "match-distractor-1", "label": "an unrelated object"},
                    {"id": "match-distractor-2", "label": "an unrelated action"},
                ],
                "correct_option_id": "match-correct",
                "metadata": {"objective_id": objective},
            }
        )
    steps.extend(
        [
            {
                "id": f"{prefix}-06",
                "type": "cloze",
                "skill": "writing",
                "prompt": f"Complete the sentence: {cloze_text}",
                "audio": {"text": spec.sentence},
                "options": [
                    {
                        "id": "cloze-correct",
                        "label": cloze_answer,
                        "audio": {"text": cloze_answer},
                    },
                    *[
                        {
                            "id": f"cloze-distractor-{index}",
                            "label": distractor,
                            "audio": {"text": distractor},
                        }
                        for index, distractor in enumerate(
                            cloze_distractors, start=1
                        )
                    ],
                ],
                "correct_option_id": "cloze-correct",
                "reveal_jyutping": spec.sentence_jyutping,
                "reveal_english": spec.sentence_english,
                "metadata": {
                    "expected": cloze_answer,
                    "allow_manual_input": True,
                    "objective_id": objective,
                },
            },
            {
                "id": f"{prefix}-07",
                "type": "order_words",
                "skill": "writing",
                "prompt": f"Build: {spec.sentence_english}",
                "options": sentence_word_options,
                "metadata": {
                    "expected_order": [
                        f"word-{index}" for index in range(1, len(spec.tokens) + 1)
                    ],
                    "objective_id": objective,
                },
            },
            {
                "id": f"{prefix}-08",
                "type": "order_words",
                "skill": "writing",
                "prompt": "Listen and build the sentence.",
                "audio": {"text": spec.sentence},
                "options": [
                    {
                        "id": f"audio-word-{index}",
                        "label": token,
                        "audio": {"text": token},
                    }
                    for index, token in enumerate(spec.tokens, start=1)
                ],
                "reveal_jyutping": spec.sentence_jyutping,
                "reveal_character": spec.sentence,
                "reveal_english": spec.sentence_english,
                "metadata": {
                    "expected_order": [
                        f"audio-word-{index}"
                        for index in range(1, len(spec.tokens) + 1)
                    ],
                    "objective_id": objective,
                },
            },
        ]
    )
    steps.insert(
        0,
        build_intro_step(
            prefix,
            objective,
            spec,
            lesson_type,
            sort_order=sort_order,
            component_data=component_data,
        ),
    )
    return steps


def generate_document() -> dict:
    all_groups = (
        ("sound", SOUND_SPECS),
        ("component", COMPONENT_SPECS),
        ("vocabulary", VOCAB_SPECS),
        ("grammar", GRAMMAR_SPECS),
    )
    units = []
    lessons = []
    lexemes = []
    characters = []
    previous_unit = None
    previous_lesson = None
    global_order = 0

    for unit_order, ((unit_id, title, phase, _), (lesson_type, specs)) in enumerate(
        zip(UNITS, all_groups, strict=True), start=1
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
        for sort_order, spec in enumerate(specs, start=1):
            global_order += 1
            lesson_id = f"v2-{lesson_type}-{sort_order:02d}"
            lexeme_id = f"{lesson_id}-target"
            objective = f"{lesson_id}-objective"
            component_data = (
                COMPONENTS[sort_order - 1] if lesson_type == "component" else None
            )
            lessons.append(
                {
                    "id": lesson_id,
                    "unit_id": unit_id,
                    "title": f"{spec.traditional} · {spec.jyutping} · {spec.english}",
                    "lesson_type": lesson_type,
                    "sort_order": sort_order,
                    "prerequisites": [previous_lesson] if previous_lesson else [],
                    "objectives": [objective],
                    "content": {
                        "target": {
                            "traditional": spec.traditional,
                            "jyutping": spec.jyutping,
                            "tone": tones(spec.jyutping)[-1],
                            "tones": tones(spec.jyutping),
                            "english": spec.english,
                        },
                        "context": {
                            "traditional": spec.sentence,
                            "jyutping": spec.sentence_jyutping,
                            "tones": tones(spec.sentence_jyutping),
                            "english": spec.sentence_english,
                            "progression": global_order,
                        },
                        "vocabulary": [{"lexeme_id": lexeme_id}],
                        "steps": make_steps(
                            lesson_id,
                            spec,
                            lesson_type,
                            sort_order=sort_order,
                            component_data=component_data,
                        ),
                    },
                }
            )
            lexemes.append(
                {
                    "id": lexeme_id,
                    "traditional": spec.traditional,
                    "jyutping": spec.jyutping,
                    "tone": tones(spec.jyutping)[-1],
                    "tones": tones(spec.jyutping),
                    "english": spec.english,
                    "tags": [phase, "beginner-v2"],
                    "difficulty": 1 + (global_order - 1) // 14,
                }
            )
            if lesson_type == "component":
                component_data = COMPONENTS[sort_order - 1]
                characters.append(
                    {
                        "id": f"{lesson_id}-character",
                        "glyph": spec.traditional,
                        "meaning": spec.english,
                        "jyutping": spec.jyutping,
                        "tone": tones(spec.jyutping)[-1],
                        "tones": tones(spec.jyutping),
                        "radical": component_data[0][0],
                        "components": [
                            {"glyph": glyph, "role": role} for glyph, role in component_data
                        ],
                        "related_words": [spec.sentence.replace("。", "")],
                    }
                )
            previous_lesson = lesson_id
        previous_unit = unit_id

    return {
        "version": "2.0.0",
        "level": "beginner",
        "generator": {
            "name": "generate_beginner_v2.py",
            "deterministic": True,
            "lesson_count": 40,
            "exercises_per_lesson": [8, 10],
        },
        "units": units,
        "lexemes": lexemes,
        "characters": characters,
        "lessons": lessons,
        "stories": [],
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
