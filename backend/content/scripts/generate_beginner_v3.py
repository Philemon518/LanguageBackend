"""Generate the deterministic Beginner v3 foundation curriculum."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import NamedTuple

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
ROOT = SCRIPT_ROOT.parent if SCRIPT_ROOT.name == "backend" else SCRIPT_ROOT
OUTPUT = ROOT / "content" / "seeds" / "beginner_v3.json"
MIRROR_OUTPUT = ROOT / "backend" / "content" / "seeds" / "beginner_v3.json"
MIRROR_GENERATOR = ROOT / "backend" / "content" / "scripts" / "generate_beginner_v3.py"
V2_GENERATOR = ROOT / "content" / "scripts" / "generate_beginner_v2.py"
MIRROR_V2_GENERATOR = (
    ROOT / "backend" / "content" / "scripts" / "generate_beginner_v2.py"
)


class Target(NamedTuple):
    traditional: str
    jyutping: str
    english: str


TONES = (
    Target("詩", "si1", "poem"),
    Target("史", "si2", "history"),
    Target("試", "si3", "try"),
    Target("時", "si4", "time"),
    Target("市", "si5", "market"),
    Target("事", "si6", "matter"),
)

NUMBERS = (
    Target("一", "jat1", "one"),
    Target("二", "ji6", "two"),
    Target("三", "saam1", "three"),
    Target("四", "sei3", "four"),
    Target("五", "ng5", "five"),
    Target("六", "luk6", "six"),
    Target("七", "cat1", "seven"),
    Target("八", "baat3", "eight"),
    Target("九", "gau2", "nine"),
    Target("十", "sap6", "ten"),
)

# Spoken Cantonese (口語), not 書面語: 係 / 咩 / 係咪 / 我個名, never 是 / 什麼 / 嗎 / 我的名字.
WO = Target("我", "ngo5", "I / me")
GIU = Target("叫", "giu3", "to be called")
HAI = Target("係", "hai6", "is / are / yes")
GO = Target("個", "go3", "classifier")
MING = Target("名", "ming4", "name")
JAU = Target("有", "jau5", "have")
BUN = Target("本", "bun2", "book classifier")
SYU = Target("書", "syu1", "book")
NEI = Target("你", "nei5", "you")
ME = Target("咩", "me1", "what")
HAI_MAI = Target("係咪", "hai6 mai6", "is it?")
WO_GIU = Target("我叫", "ngo5 giu3", "I'm called")
WO_HAI = Target("我係", "ngo5 hai6", "I am")
WO_GO_MING_HAI = Target("我個名係", "ngo5 go3 ming4 hai6", "my name is")
WO_JAU = Target("我有", "ngo5 jau5", "I have")
SAAM_BUN_SYU = Target("三本書", "saam1 bun2 syu1", "three books")
YAT_BUN_SYU = Target("一本書", "jat1 bun2 syu1", "one book")
NEI_GIU_ME_MING = Target("你叫咩名", "nei5 giu3 me1 ming4", "what's your name")
NEI_GIU_ME = Target("你叫咩", "nei5 giu3 me1", "what are you called")
NEI_HAI_MAI = Target("你係咪", "nei5 hai6 mai6", "are you")
JORDYN = "Jordyn"
NAME_DISTRACTORS = ("Alex", "Sam")

TONE_LABELS = {
    1: "Tone 1 · high level",
    2: "Tone 2 · high rising",
    3: "Tone 3 · mid level",
    4: "Tone 4 · low falling",
    5: "Tone 5 · low rising",
    6: "Tone 6 · low level",
}


def tones(jyutping: str) -> list[int]:
    return [int(syllable[-1]) for syllable in jyutping.split()]


def audio(target: Target) -> dict:
    """Return an explicit, portable Cantonese audio request."""
    return {
        "text": target.traditional,
        "traditional": target.traditional,
        "jyutping": target.jyutping,
        "language": "yue-HK",
        "script": "Hant",
    }


def target_dict(target: Target) -> dict:
    return {
        "traditional": target.traditional,
        "jyutping": target.jyutping,
        "tone": tones(target.jyutping)[-1],
        "tones": tones(target.jyutping),
        "english": target.english,
        "audio": audio(target),
    }


def option(option_id: str, target: Target, label: str | None = None) -> dict:
    return {
        "id": option_id,
        "label": label or target.traditional,
        "jyutping": target.jyutping,
        "audio": audio(target),
    }


def metadata(
    *,
    objective_id: str,
    section: str,
    target: Target | None = None,
    cumulative_through: int | None = None,
) -> dict:
    result = {
        "objective_id": objective_id,
        "section": section,
        "exercise_kind": section,
    }
    if target:
        result["traditional"] = target.traditional
        result["jyutping"] = target.jyutping
        result["tones"] = tones(target.jyutping)
    if cumulative_through is not None:
        result["cumulative_through"] = cumulative_through
    return result


def lesson_intro(
    *,
    lesson_id: str,
    title: str,
    summary: str,
    goals: list[str],
    new_items: tuple[Target, ...],
    review_items: tuple[Target, ...],
) -> dict:
    return {
        "title": title,
        "summary": summary,
        "learning_goals": goals,
        "new_items": [target_dict(item) for item in new_items],
        "review_items": [target_dict(item) for item in review_items],
        "audio": audio(new_items[0]),
        "presentation": {
            "traditional_label": "Traditional Chinese",
            "romanization_label": "Jyutping",
            "listen_first": True,
        },
        "id": f"{lesson_id}-intro",
    }


def latin_item(name: str) -> dict:
    return {
        "traditional": name,
        "jyutping": "",
        "english": name,
        "placeholder": True,
    }


def word_tile(option_id: str, item: Target | str) -> dict:
    if isinstance(item, str):
        return {"id": option_id, "label": item, "placeholder": True}
    return option(option_id, item)


def order_step(
    step_id: str,
    prompt: str,
    tokens: list[Target | str],
    *,
    objective_id: str,
    section: str,
    spoken: Target | None = None,
) -> dict:
    options = [
        word_tile(f"{step_id}-word-{index}", token)
        for index, token in enumerate(tokens, start=1)
    ]
    step = {
        "id": step_id,
        "type": "order_words",
        "skill": "writing",
        "prompt": prompt,
        "options": options,
        "metadata": {
            "objective_id": objective_id,
            "section": section,
            "exercise_kind": section,
            "expected_order": [option["id"] for option in options],
            "spoken_cantonese": True,
        },
    }
    if spoken:
        step["audio"] = audio(spoken)
        step["reveal_character"] = spoken.traditional
        step["reveal_jyutping"] = spoken.jyutping
        step["reveal_english"] = spoken.english
        step["skill"] = "listening"
        step["metadata"]["auditory_only_until_answer"] = True
    return step


def cloze_step(
    step_id: str,
    prompt: str,
    answer: Target | str,
    distractors: list[Target | str],
    *,
    objective_id: str,
    section: str,
    spoken: Target | None = None,
) -> dict:
    choices = [answer, *distractors]
    options = [
        word_tile(f"{step_id}-choice-{index}", item)
        for index, item in enumerate(choices, start=1)
    ]
    step = {
        "id": step_id,
        "type": "cloze",
        "skill": "reading",
        "prompt": prompt,
        "options": options,
        "correct_option_id": options[0]["id"],
        "metadata": {
            "objective_id": objective_id,
            "section": section,
            "exercise_kind": section,
            "expected": answer if isinstance(answer, str) else answer.traditional,
            "allow_manual_input": False,
            "spoken_cantonese": True,
        },
    }
    if spoken:
        step["audio"] = audio(spoken)
        step["skill"] = "listening"
        step["reveal_character"] = spoken.traditional
        step["reveal_jyutping"] = spoken.jyutping
        step["reveal_english"] = spoken.english
    if isinstance(answer, Target):
        step["reveal_character"] = answer.traditional
        step["reveal_jyutping"] = answer.jyutping
        step["reveal_english"] = answer.english
    return step


def speak_step(
    step_id: str,
    prompt: str,
    target: Target,
    *,
    objective_id: str,
    section: str,
) -> dict:
    return {
        "id": step_id,
        "type": "speak",
        "skill": "speaking",
        "prompt": prompt,
        "audio": audio(target),
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            "objective_id": objective_id,
            "section": section,
            "exercise_kind": section,
            "expected": target.jyutping,
            "expected_text": target.traditional,
            "spoken_cantonese": True,
        },
    }


def listen_choice_step(
    step_id: str,
    prompt: str,
    target: Target,
    choices: tuple[Target, ...],
    *,
    objective_id: str,
    section: str,
) -> dict:
    options = [
        option(f"{step_id}-opt-{index}", item)
        for index, item in enumerate(choices, start=1)
    ]
    correct = next(
        option_row["id"]
        for option_row, item in zip(options, choices, strict=True)
        if item == target
    )
    return {
        "id": step_id,
        "type": "select_character",
        "skill": "listening",
        "prompt": prompt,
        "audio": audio(target),
        "options": options,
        "correct_option_id": correct,
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            **metadata(objective_id=objective_id, section=section, target=target),
            "auditory_only_until_answer": True,
            "spoken_cantonese": True,
        },
    }


def intro_item(item: Target | str) -> dict:
    if isinstance(item, str):
        return latin_item(item)
    return target_dict(item)


def intro_step(lesson_id: str, intro: dict, objective_id: str) -> dict:
    first = next(
        (item for item in intro["new_items"] if item.get("audio")),
        intro["new_items"][0],
    )
    return {
        "id": f"{lesson_id}-intro",
        "type": "lesson_intro",
        "skill": "listening",
        "prompt": intro["title"],
        "audio": first.get("audio") or intro.get("audio"),
        "options": [{"id": "intro-ready", "label": "Start lesson"}],
        "correct_option_id": "intro-ready",
        "reveal_character": first["traditional"],
        "reveal_jyutping": first.get("jyutping") or "",
        "reveal_english": first["english"],
        "metadata": {
            "objective_id": objective_id,
            "section": "introduction",
            "exercise_kind": "introduction",
            "lesson_intro": intro,
        },
    }


def tone_recognition_step(
    lesson_id: str, index: int, target: Target, lesson_targets: tuple[Target, ...]
) -> dict:
    tone = tones(target.jyutping)[-1]
    choice_tones = [tone]
    for candidate in (1, 2, 3, 4, 5, 6):
        if candidate != tone and candidate not in choice_tones:
            choice_tones.append(candidate)
        if len(choice_tones) == 3:
            break
    return {
        "id": f"{lesson_id}-recognition-{index:02d}",
        "type": "select_tone",
        "skill": "listening",
        "prompt": "Listen without reading first. Which Cantonese tone do you hear?",
        "audio": audio(target),
        "options": [
            {"id": f"tone-{value}", "label": TONE_LABELS[value]}
            for value in choice_tones
        ],
        "correct_option_id": f"tone-{tone}",
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            **metadata(
                objective_id=f"{lesson_id}-hear-tones",
                section="recognition",
                target=target,
            ),
            "contrast_set": [item.jyutping for item in lesson_targets],
            "auditory_only_until_answer": True,
        },
    }


def tone_challenge_step(
    lesson_id: str, index: int, target: Target, lesson_targets: tuple[Target, ...]
) -> dict:
    distractors = [item for item in lesson_targets if item != target][:2]
    choices = (target, *distractors)
    return {
        "id": f"{lesson_id}-challenge-{index:02d}",
        "type": "select_jyutping",
        "skill": "listening",
        "prompt": "Tone challenge: choose the exact Jyutping you hear.",
        "audio": audio(target),
        "options": [
            option(
                f"jyutping-{choice.jyutping}",
                choice,
                choice.jyutping,
            )
            for choice in choices
        ],
        "correct_option_id": f"jyutping-{target.jyutping}",
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            **metadata(
                objective_id=f"{lesson_id}-contrast-tones",
                section="challenge",
                target=target,
            ),
            "contrast_set": [item.jyutping for item in lesson_targets],
            "auditory_only_until_answer": True,
        },
    }


def build_tone_lesson(
    *,
    lesson_id: str,
    sort_order: int,
    title: str,
    new_targets: tuple[Target, ...],
    review_targets: tuple[Target, ...],
    prerequisites: list[str],
    progression: int,
) -> dict:
    lesson_targets = review_targets + new_targets
    intro = lesson_intro(
        lesson_id=lesson_id,
        title=title,
        summary="Train your ear before relying on written tone numbers.",
        goals=[
            "Hear pitch height and movement",
            "Connect a spoken syllable to its Jyutping tone number",
        ],
        new_items=new_targets,
        review_items=review_targets,
    )
    steps = [intro_step(lesson_id, intro, f"{lesson_id}-hear-tones")]
    steps.extend(
        tone_recognition_step(lesson_id, index, target, lesson_targets)
        for index, target in enumerate(lesson_targets, start=1)
    )
    steps.extend(
        tone_challenge_step(lesson_id, index, target, lesson_targets)
        for index, target in enumerate(lesson_targets, start=1)
    )
    return {
        "id": lesson_id,
        "unit_id": "v3-unit-0-tones",
        "title": title,
        "lesson_type": "tone",
        "sort_order": sort_order,
        "prerequisites": prerequisites,
        "objectives": [f"{lesson_id}-hear-tones", f"{lesson_id}-contrast-tones"],
        "content": {
            "lesson_intro": intro,
            "target": {
                **target_dict(new_targets[0]),
                "theme": "Cantonese tone recognition",
                "words": [target_dict(item) for item in lesson_targets],
            },
            "context": {
                "traditional": "、".join(item.traditional for item in lesson_targets),
                "jyutping": " ".join(item.jyutping for item in lesson_targets),
                "tones": [tones(item.jyutping)[-1] for item in lesson_targets],
                "english": "Cantonese tone contrast set",
                "progression": progression,
            },
            "vocabulary": [
                {"lexeme_id": f"v3-tone-{tones(item.jyutping)[-1]}"}
                for item in lesson_targets
            ],
            "steps": steps,
        },
    }


def number_recognition_step(
    lesson_id: str,
    index: int,
    target: Target,
    learned: tuple[Target, ...],
) -> dict:
    distractors = [item for item in learned if item != target]
    if len(distractors) < 2:
        distractors.extend(NUMBERS[len(learned) : len(learned) + 2 - len(distractors)])
    choices = (target, *distractors[:2])
    return {
        "id": f"{lesson_id}-recognition-{index:02d}",
        "type": "select_character",
        "skill": "listening",
        "prompt": "Listen. Choose the Traditional Chinese number you hear.",
        "audio": audio(target),
        "options": [
            option(f"number-{NUMBERS.index(choice) + 1}", choice) for choice in choices
        ],
        "correct_option_id": f"number-{NUMBERS.index(target) + 1}",
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            **metadata(
                objective_id=f"{lesson_id}-recognize",
                section="recognition",
                target=target,
                cumulative_through=len(learned),
            ),
            "auditory_only_until_answer": True,
        },
    }


def number_challenge_step(
    lesson_id: str,
    target: Target,
    learned: tuple[Target, ...],
) -> dict:
    choices = list(learned)
    if len(choices) < 3:
        choices.extend(NUMBERS[len(choices) : 3])
    return {
        "id": f"{lesson_id}-challenge-cumulative",
        "type": "select_meaning",
        "skill": "listening",
        "prompt": f"Cumulative challenge: identify a number from one to {len(learned)}.",
        "audio": audio(target),
        "options": [
            option(
                f"value-{NUMBERS.index(choice) + 1}",
                choice,
                str(NUMBERS.index(choice) + 1),
            )
            for choice in choices
        ],
        "correct_option_id": f"value-{NUMBERS.index(target) + 1}",
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            **metadata(
                objective_id=f"{lesson_id}-recall",
                section="challenge",
                target=target,
                cumulative_through=len(learned),
            ),
            "review_pool": [target_dict(item) for item in learned],
            "auditory_only_until_answer": True,
        },
    }


def build_number_lesson(
    *,
    number: int,
    prerequisites: list[str],
    progression: int,
) -> dict:
    lesson_id = f"v3-number-{number:02d}"
    current = NUMBERS[number - 1]
    learned = NUMBERS[:number]
    review = NUMBERS[: number - 1]
    title = f"Number {number}: {current.traditional} · {current.jyutping}"
    intro = lesson_intro(
        lesson_id=lesson_id,
        title=title,
        summary=f"Add {current.traditional} ({current.jyutping}) and review one through {number}.",
        goals=[
            f"Recognize {current.traditional} by sound and Traditional Chinese",
            f"Recall every number from one through {number}",
        ],
        new_items=(current,),
        review_items=review,
    )
    steps = [intro_step(lesson_id, intro, f"{lesson_id}-recognize")]
    steps.extend(
        number_recognition_step(lesson_id, index, target, learned)
        for index, target in enumerate(learned, start=1)
    )
    steps.append(number_challenge_step(lesson_id, current, learned))
    steps.append(
        {
            "id": f"{lesson_id}-challenge-speak",
            "type": "speak",
            "skill": "speaking",
            "prompt": f"Say {current.traditional} after listening.",
            "audio": audio(current),
            "reveal_character": current.traditional,
            "reveal_jyutping": current.jyutping,
            "reveal_english": current.english,
            "metadata": {
                **metadata(
                    objective_id=f"{lesson_id}-produce",
                    section="challenge",
                    target=current,
                    cumulative_through=number,
                ),
                "expected": current.jyutping,
                "expected_text": current.traditional,
            },
        }
    )
    return {
        "id": lesson_id,
        "unit_id": "v3-unit-1-numbers",
        "title": title,
        "lesson_type": "number",
        "sort_order": number,
        "prerequisites": prerequisites,
        "objectives": [
            f"{lesson_id}-recognize",
            f"{lesson_id}-recall",
            f"{lesson_id}-produce",
        ],
        "content": {
            "lesson_intro": intro,
            "target": {
                **target_dict(current),
                "theme": f"Numbers one through {number}",
                "words": [target_dict(item) for item in learned],
            },
            "context": {
                "traditional": "、".join(item.traditional for item in learned),
                "jyutping": " ".join(item.jyutping for item in learned),
                "tones": [tones(item.jyutping)[-1] for item in learned],
                "english": f"Numbers one through {number}",
                "progression": progression,
            },
            "vocabulary": [
                {"lexeme_id": f"v3-number-{index:02d}"}
                for index in range(1, number + 1)
            ],
            "steps": steps,
        },
    }


def spoken_lesson_intro(
    *,
    lesson_id: str,
    title: str,
    summary: str,
    goals: list[str],
    new_items: tuple[Target | str, ...],
    review_items: tuple[Target | str, ...],
    sections: list[dict],
) -> dict:
    items = [intro_item(item) for item in new_items]
    audio_source = next(item for item in items if item.get("audio"))
    return {
        "id": f"{lesson_id}-intro",
        "title": title,
        "summary": summary,
        "learning_goals": goals,
        "new_items": items,
        "review_items": [intro_item(item) for item in review_items],
        "audio": audio_source["audio"],
        "presentation": {
            "traditional_label": "Spoken Cantonese",
            "romanization_label": "Jyutping",
            "listen_first": True,
        },
        "sections": sections,
    }


def pack_spoken_lesson(
    *,
    lesson_id: str,
    title: str,
    lesson_type: str,
    sort_order: int,
    previous: str,
    intro: dict | None,
    primary: Target,
    theme: str,
    words: tuple[Target, ...],
    lexemes: list[str],
    steps: list[dict],
    progression: int,
) -> dict:
    content: dict = {
        "target": {
            **target_dict(primary),
            "theme": theme,
            "words": [target_dict(item) for item in words],
        },
        "context": {
            "traditional": "、".join(item.traditional for item in words),
            "jyutping": " ".join(item.jyutping for item in words),
            "tones": [tone for item in words for tone in tones(item.jyutping)],
            "english": theme,
            "progression": progression,
        },
        "vocabulary": [{"lexeme_id": lexeme_id} for lexeme_id in lexemes],
        "steps": steps,
    }
    if intro is not None:
        content["lesson_intro"] = intro
    return {
        "id": lesson_id,
        "unit_id": "v3-unit-2",
        "title": title,
        "lesson_type": lesson_type,
        "sort_order": sort_order,
        "prerequisites": [previous],
        "objectives": [f"{lesson_id}-speak"],
        "content": content,
    }


def short_number_review(lesson_id: str, picks: tuple[Target, ...], start: int) -> list[dict]:
    return [
        number_recognition_step(lesson_id, start + index, target, NUMBERS)
        for index, target in enumerate(picks)
    ]


def typing_character_step(
    step_id: str,
    target: Target,
    *,
    objective_id: str,
    section: str,
) -> dict:
    return {
        "id": step_id,
        "type": "typing",
        "skill": "writing",
        "prompt": f"Type {target.traditional}.",
        "reveal_character": target.traditional,
        "reveal_jyutping": target.jyutping,
        "reveal_english": target.english,
        "metadata": {
            "objective_id": objective_id,
            "section": section,
            "exercise_kind": section,
            "accepted_answers": [target.traditional],
            "input_mode": "chinese_character",
            "spoken_cantonese": True,
        },
    }


def build_introduction_lessons(previous: str) -> list[dict]:
    """Six spoken-Cantonese introduction lessons. No 书面语, no 字."""
    lessons: list[dict] = []
    obj = lambda lesson_id: f"{lesson_id}-speak"

    # 2.1 我 · 叫
    lesson_id = "v3-intro-01"
    intro = spoken_lesson_intro(
        lesson_id=lesson_id,
        title="我 · 叫",
        summary="Say who you are in spoken Cantonese: 我叫 Jordyn.",
        goals=[
            "Hear and read 我 and 叫",
            "Build 我叫 Jordyn with tiles",
            "Say 我叫",
        ],
        new_items=(WO, GIU, JORDYN),
        review_items=(),
        sections=[
            {
                "type": "text",
                "title": "Spoken Cantonese",
                "body": "This is how people talk. 我叫 Jordyn means “I'm called Jordyn.” Jordyn is a name tile you choose, not a name you type.",
            },
            {
                "type": "cards",
                "title": "First sentence",
                "cards": [
                    {"title": "我叫", "body": "Spoken: ngo5 giu3 — I'm called"},
                    {"title": "Jordyn", "body": "A name block. Tap it. Do not type your own name."},
                ],
            },
        ],
    )
    steps = [intro_step(lesson_id, intro, obj(lesson_id))]
    steps.append(
        listen_choice_step(
            f"{lesson_id}-hear-wo",
            "Listen. Choose the spoken word you hear.",
            WO,
            (WO, GIU, NEI),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        listen_choice_step(
            f"{lesson_id}-hear-giu",
            "Listen. Choose the spoken word you hear.",
            GIU,
            (GIU, WO, HAI),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-giu",
            "Build this spoken sentence: 我叫 Jordyn。",
            [WO, GIU, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GIU,
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-giu",
            "我＿＿ Jordyn。",
            GIU,
            [HAI, JAU],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-jordyn",
            "我叫 ＿＿。",
            JORDYN,
            list(NAME_DISTRACTORS),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-wo-giu",
            "Listen, then say 我叫.",
            WO_GIU,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.extend(short_number_review(lesson_id, (NUMBERS[0], NUMBERS[2], NUMBERS[9]), 1))
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="我 · 叫",
            lesson_type="introduction",
            sort_order=1,
            previous=previous,
            intro=intro,
            primary=WO,
            theme="我叫 Jordyn",
            words=(WO, GIU),
            lexemes=["v3-wo", "v3-giu", "v3-jordyn"],
            steps=steps,
            progression=13,
        )
    )
    previous = lesson_id

    # 2.2 係 · 個 · 名
    lesson_id = "v3-intro-02"
    intro = spoken_lesson_intro(
        lesson_id=lesson_id,
        title="係 · 個 · 名",
        summary="Same meaning, three spoken shapes: 我叫 / 我係 / 我個名係.",
        goals=[
            "Hear 係, 個, and 名",
            "Say 我係 and 我個名係",
            "Know 係 can also mean yes",
        ],
        new_items=(HAI, GO, MING),
        review_items=(WO, GIU, JORDYN),
        sections=[
            {
                "type": "text",
                "title": "Same idea, different talk",
                "body": "In spoken Cantonese you can say 我叫 Jordyn, 我係 Jordyn, or 我個名係 Jordyn. All mean you are Jordyn.",
            },
            {
                "type": "cards",
                "title": "Three spoken sentences",
                "cards": [
                    {"title": "我叫 Jordyn。", "body": "I'm called Jordyn."},
                    {"title": "我係 Jordyn。", "body": "I am Jordyn. 係 also answers yes."},
                    {"title": "我個名係 Jordyn。", "body": "My name is Jordyn."},
                ],
            },
        ],
    )
    steps = [intro_step(lesson_id, intro, obj(lesson_id))]
    for target, pool in (
        (HAI, (HAI, GIU, WO)),
        (GO, (GO, MING, WO)),
        (MING, (MING, GO, NEI)),
    ):
        steps.append(
            listen_choice_step(
                f"{lesson_id}-hear-{target.jyutping.replace(' ', '-')}",
                "Listen. Choose the spoken word you hear.",
                target,
                pool,
                objective_id=obj(lesson_id),
                section="recognition",
            )
        )
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-hai",
            "Build this spoken sentence: 我係 Jordyn。",
            [WO, HAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_HAI,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-go-ming",
            "Build this spoken sentence: 我個名係 Jordyn。",
            [WO, GO, MING, HAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GO_MING_HAI,
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-hai",
            "我＿＿ Jordyn。",
            HAI,
            [GIU, JAU],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-ming",
            "我個＿＿係 Jordyn。",
            MING,
            [GIU, NEI],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-wo-hai",
            "Listen, then say 我係.",
            WO_HAI,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-wo-go-ming",
            "Listen, then say 我個名係.",
            WO_GO_MING_HAI,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.extend(short_number_review(lesson_id, (NUMBERS[1], NUMBERS[4], NUMBERS[6]), 1))
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="係 · 個 · 名",
            lesson_type="introduction",
            sort_order=2,
            previous=previous,
            intro=intro,
            primary=HAI,
            theme="我個名係 Jordyn",
            words=(HAI, GO, MING),
            lexemes=["v3-hai", "v3-go", "v3-ming", "v3-wo", "v3-giu", "v3-jordyn"],
            steps=steps,
            progression=14,
        )
    )
    previous = lesson_id

    # 2.3 練習
    lesson_id = "v3-intro-03"
    intro = spoken_lesson_intro(
        lesson_id=lesson_id,
        title="練習",
        summary="Practice the spoken sentences you already have. No new words.",
        goals=["Reuse 我叫, 我係, and 我個名係", "Keep numbers in play"],
        new_items=(WO_GIU,),
        review_items=(WO, GIU, HAI, GO, MING, JORDYN),
        sections=[
            {
                "type": "text",
                "title": "Keep talking",
                "body": "Same spoken sentences: 我叫 Jordyn。我係 Jordyn。我個名係 Jordyn。",
            }
        ],
    )
    steps = [intro_step(lesson_id, intro, obj(lesson_id))]
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-giu",
            "Build this spoken sentence: 我叫 Jordyn。",
            [WO, GIU, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GIU,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-hai",
            "Build this spoken sentence: 我係 Jordyn。",
            [WO, HAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_HAI,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-ming",
            "Build this spoken sentence: 我個名係 Jordyn。",
            [WO, GO, MING, HAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GO_MING_HAI,
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-jordyn",
            "我個名係 ＿＿。",
            JORDYN,
            list(NAME_DISTRACTORS),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-wo-giu",
            "Listen, then say 我叫.",
            WO_GIU,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        typing_character_step(
            f"{lesson_id}-type-wo",
            WO,
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.extend(short_number_review(lesson_id, (NUMBERS[3], NUMBERS[7], NUMBERS[8]), 1))
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="練習",
            lesson_type="introduction",
            sort_order=3,
            previous=previous,
            intro=intro,
            primary=WO_GIU,
            theme="Practice 我叫 / 我係 / 我個名係",
            words=(WO, GIU, HAI, GO, MING),
            lexemes=["v3-wo", "v3-giu", "v3-hai", "v3-go", "v3-ming", "v3-jordyn"],
            steps=steps,
            progression=15,
        )
    )
    previous = lesson_id

    # 2.4 有
    lesson_id = "v3-intro-04"
    intro = spoken_lesson_intro(
        lesson_id=lesson_id,
        title="有",
        summary="Put numbers into spoken talk: 我有三本書.",
        goals=["Hear 有", "Use a number inside 我有三本書", "Keep 我叫 in play"],
        new_items=(JAU, BUN, SYU),
        review_items=(WO, GIU, HAI, NUMBERS[2], JORDYN),
        sections=[
            {
                "type": "text",
                "title": "Numbers in a sentence",
                "body": "我叫 Jordyn。我有三本書。有 means have. 三本書 is a spoken chunk for three books.",
            }
        ],
    )
    steps = [intro_step(lesson_id, intro, obj(lesson_id))]
    steps.append(
        listen_choice_step(
            f"{lesson_id}-hear-jau",
            "Listen. Choose the spoken word you hear.",
            JAU,
            (JAU, HAI, GIU),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        listen_choice_step(
            f"{lesson_id}-hear-books",
            "Listen. Choose what you hear.",
            SAAM_BUN_SYU,
            (SAAM_BUN_SYU, YAT_BUN_SYU, WO_GIU),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-books",
            "Build this spoken sentence: 我有三本書。",
            [WO, JAU, NUMBERS[2], BUN, SYU],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=Target("我有三本書", "ngo5 jau5 saam1 bun2 syu1", "I have three books"),
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-jau",
            "我＿＿三本書。",
            JAU,
            [HAI, GIU],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-number",
            "我有＿＿本書。",
            NUMBERS[2],
            [NUMBERS[0], NUMBERS[4]],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-jau",
            "Listen, then say 我有.",
            WO_JAU,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-books",
            "Listen, then say 三本書.",
            SAAM_BUN_SYU,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.extend(short_number_review(lesson_id, (NUMBERS[2], NUMBERS[5], NUMBERS[0]), 1))
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="有",
            lesson_type="introduction",
            sort_order=4,
            previous=previous,
            intro=intro,
            primary=JAU,
            theme="我有三本書",
            words=(JAU, BUN, SYU, NUMBERS[2]),
            lexemes=["v3-jau", "v3-bun", "v3-syu", "v3-wo", "v3-giu", "v3-jordyn"],
            steps=steps,
            progression=16,
        )
    )
    previous = lesson_id

    # 2.5 你 · 咩 · 係咪
    lesson_id = "v3-intro-05"
    intro = spoken_lesson_intro(
        lesson_id=lesson_id,
        title="你 · 咩 · 係咪",
        summary="Ask in spoken Cantonese: 你叫咩名？你係咪 Jordyn？",
        goals=[
            "Hear 你, 咩, and 係咪",
            "Ask 你叫咩名 and 你叫咩",
            "Ask 你係咪 Jordyn and answer 係",
        ],
        new_items=(NEI, ME, HAI_MAI),
        review_items=(WO, GIU, HAI, MING, JORDYN),
        sections=[
            {
                "type": "text",
                "title": "Questions people actually ask",
                "body": "Ask with 咩 and 係咪. 你叫咩名？你叫咩？你係咪 Jordyn？ Answer 係。",
            }
        ],
    )
    steps = [intro_step(lesson_id, intro, obj(lesson_id))]
    for target, pool in (
        (NEI, (NEI, WO, ME)),
        (ME, (ME, MING, GIU)),
        (HAI_MAI, (HAI_MAI, HAI, ME)),
    ):
        steps.append(
            listen_choice_step(
                f"{lesson_id}-hear-{target.traditional}",
                "Listen. Choose the spoken word you hear.",
                target,
                pool,
                objective_id=obj(lesson_id),
                section="recognition",
            )
        )
    steps.append(
        order_step(
            f"{lesson_id}-order-name-q",
            "Build this spoken question: 你叫咩名？",
            [NEI, GIU, ME, MING],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=NEI_GIU_ME_MING,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-me",
            "Build this spoken question: 你叫咩？",
            [NEI, GIU, ME],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=NEI_GIU_ME,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-hai-mai",
            "Build this spoken question: 你係咪 Jordyn？",
            [NEI, HAI_MAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=NEI_HAI_MAI,
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-me",
            "你叫＿＿名？",
            ME,
            [MING, HAI],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-jordyn",
            "你係咪 ＿＿？",
            JORDYN,
            list(NAME_DISTRACTORS),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-yes",
            "你係咪 Jordyn？＿＿。",
            HAI,
            [GIU, ME],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-name-q",
            "Listen, then say 你叫咩名.",
            NEI_GIU_ME_MING,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-hai",
            "Listen, then say 係.",
            HAI,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="你 · 咩 · 係咪",
            lesson_type="introduction",
            sort_order=5,
            previous=previous,
            intro=intro,
            primary=NEI,
            theme="你叫咩名？",
            words=(NEI, ME, HAI_MAI),
            lexemes=["v3-nei", "v3-me", "v3-hai-mai", "v3-ming", "v3-hai", "v3-jordyn"],
            steps=steps,
            progression=17,
        )
    )
    previous = lesson_id

    # 2.6 介紹練習 — no intro page
    lesson_id = "v3-intro-review"
    steps = []
    steps.append(
        order_step(
            f"{lesson_id}-order-wo-giu",
            "Build this spoken sentence: 我叫 Jordyn。",
            [WO, GIU, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GIU,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-ming",
            "Build this spoken sentence: 我個名係 Jordyn。",
            [WO, GO, MING, HAI, JORDYN],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=WO_GO_MING_HAI,
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-books",
            "Build this spoken sentence: 我有三本書。",
            [WO, JAU, NUMBERS[2], BUN, SYU],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=Target("我有三本書", "ngo5 jau5 saam1 bun2 syu1", "I have three books"),
        )
    )
    steps.append(
        order_step(
            f"{lesson_id}-order-q",
            "Build this spoken question: 你叫咩名？",
            [NEI, GIU, ME, MING],
            objective_id=obj(lesson_id),
            section="recognition",
            spoken=NEI_GIU_ME_MING,
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-jordyn",
            "你係咪 ＿＿？",
            JORDYN,
            list(NAME_DISTRACTORS),
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        cloze_step(
            f"{lesson_id}-cloze-yes",
            "你係咪 Jordyn？＿＿。",
            HAI,
            [ME, JAU],
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-wo-giu",
            "Listen, then say 我叫.",
            WO_GIU,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        speak_step(
            f"{lesson_id}-speak-q",
            "Listen, then say 你叫咩名.",
            NEI_GIU_ME_MING,
            objective_id=obj(lesson_id),
            section="challenge",
        )
    )
    steps.append(
        typing_character_step(
            f"{lesson_id}-type-nei",
            NEI,
            objective_id=obj(lesson_id),
            section="recognition",
        )
    )
    steps.extend(
        short_number_review(lesson_id, (NUMBERS[2], NUMBERS[4], NUMBERS[9], NUMBERS[1]), 1)
    )
    lessons.append(
        pack_spoken_lesson(
            lesson_id=lesson_id,
            title="介紹練習",
            lesson_type="introduction_review",
            sort_order=6,
            previous=previous,
            intro=None,
            primary=WO,
            theme="介紹自己練習",
            words=(WO, GIU, HAI, GO, MING, JAU, NEI, ME, HAI_MAI),
            lexemes=[
                "v3-wo",
                "v3-giu",
                "v3-hai",
                "v3-go",
                "v3-ming",
                "v3-jau",
                "v3-nei",
                "v3-me",
                "v3-hai-mai",
                "v3-jordyn",
            ],
            steps=steps,
            progression=18,
        )
    )
    return lessons


def generate_document() -> dict:
    """Build Unit 0 orientation, Unit 1 numbers, and Unit 2 spoken introductions."""

    def choice_step(
        step_id: str,
        prompt: str,
        choices: list[dict],
        correct_id: str,
        *,
        section: str,
        audio_ref: dict | None = None,
        prompt_image: str | None = None,
        reveal: Target | None = None,
        objective_id: str,
        exercise_type: str = "choice",
    ) -> dict:
        step = {
            "id": step_id,
            "type": exercise_type,
            "skill": "listening" if audio_ref else "reading",
            "prompt": prompt,
            "options": choices,
            "correct_option_id": correct_id,
            "metadata": {
                "objective_id": objective_id,
                "section": section,
                "exercise_kind": section,
            },
        }
        if audio_ref:
            step["audio"] = audio_ref
            step["metadata"]["auditory_only_until_answer"] = True
        if prompt_image:
            step["prompt_image"] = prompt_image
        if reveal:
            step.update(
                reveal_character=reveal.traditional,
                reveal_jyutping=reveal.jyutping,
                reveal_english=reveal.english,
            )
            step["metadata"].update(
                traditional=reveal.traditional,
                jyutping=reveal.jyutping,
                tones=tones(reveal.jyutping),
            )
        return step

    def conceptual_lesson() -> dict:
        lesson_id = "v3-orientation"
        intro = {
            "id": f"{lesson_id}-intro",
            "title": "廣東話",
            "summary": "Build a mental model of spoken Cantonese before memorizing words.",
            "learning_goals": [
                "Know where Cantonese is spoken and how it differs from Mandarin",
                "Distinguish speech, characters, meaning, and Jyutping pronunciation",
            ],
            "new_items": [
                target_dict(Target("廣東話", "gwong2 dung1 waa2", "Cantonese")),
                target_dict(Target("粵語", "jyut6 jyu5", "Cantonese language")),
            ],
            "review_items": [],
            "audio": audio(Target("廣東話", "gwong2 dung1 waa2", "Cantonese")),
            "presentation": {
                "traditional_label": "Traditional Chinese",
                "romanization_label": "Jyutping",
                "listen_first": False,
            },
            "sections": [
                {
                    "type": "hero",
                    "title": "廣東話 / 粵語",
                    "body": "Both names mean Cantonese. It is widely spoken in Hong Kong.",
                    "audio": [
                        audio(Target("廣東話", "gwong2 dung1 waa2", "Cantonese")),
                        audio(Target("粵語", "jyut6 jyu5", "Cantonese language")),
                    ],
                },
                {
                    "type": "comparison",
                    "title": "Cantonese and Mandarin",
                    "items": [
                        {
                            "label": "Cantonese",
                            "body": "A distinct spoken Chinese language with six tones.",
                        },
                        {
                            "label": "Mandarin",
                            "body": "A different spoken Chinese language and the basis of the modern written standard.",
                        },
                    ],
                },
                {
                    "type": "cards",
                    "title": "Speech and writing",
                    "cards": [
                        {
                            "title": "Spoken Cantonese",
                            "body": "Everyday conversation uses colloquial Cantonese grammar and vocabulary. We learn this first.",
                        },
                        {
                            "title": "Standard Written Chinese",
                            "body": "The formal written standard is closer to Mandarin-based grammar and can be read aloud with Cantonese pronunciations.",
                        },
                        {
                            "title": "Characters and sound",
                            "body": "Characters normally carry meaning. Cantonese also uses some phonetic loans, but characters are not generally sound without meaning.",
                        },
                    ],
                },
                {
                    "type": "comparison",
                    "title": "Traditional and Simplified",
                    "items": [
                        {
                            "label": "Traditional",
                            "body": "Used in Hong Kong and taught in this course.",
                        },
                        {
                            "label": "Simplified",
                            "body": "A different written form of many of the same words.",
                        },
                    ],
                },
                {
                    "type": "model",
                    "title": "Three things to connect",
                    "rows": [
                        {"source": "Chinese character", "target": "meaning"},
                        {"source": "Jyutping", "target": "pronunciation"},
                        {"source": "Cantonese speech", "target": "sound"},
                    ],
                },
            ],
        }
        concepts = [
            (
                "Where is Cantonese widely spoken?",
                ["Hong Kong", "Only Beijing", "Only Singapore"],
                "Hong Kong",
            ),
            (
                "Which writing system does Hong Kong use?",
                [
                    "Traditional Chinese",
                    "Simplified Chinese only",
                    "The Latin alphabet only",
                ],
                "Traditional Chinese",
            ),
            (
                "What does Jyutping represent?",
                ["Cantonese pronunciation", "English meaning", "Stroke order"],
                "Cantonese pronunciation",
            ),
            (
                "What will this course teach first?",
                ["Spoken Cantonese", "Formal essays", "Mandarin pronunciation"],
                "Spoken Cantonese",
            ),
        ]
        steps = [intro_step(lesson_id, intro, f"{lesson_id}-mental-model")]
        for index, (prompt, labels, answer) in enumerate(concepts, start=1):
            choices = [
                {"id": f"answer-{choice_index}", "label": label}
                for choice_index, label in enumerate(labels, start=1)
            ]
            steps.append(
                choice_step(
                    f"{lesson_id}-check-{index:02d}",
                    prompt,
                    choices,
                    f"answer-{labels.index(answer) + 1}",
                    section="recognition",
                    objective_id=f"{lesson_id}-mental-model",
                )
            )
        return {
            "id": lesson_id,
            "unit_id": "v3-unit-0",
            "title": "廣東話",
            "lesson_type": "orientation",
            "sort_order": 1,
            "prerequisites": [],
            "objectives": [f"{lesson_id}-mental-model"],
            "content": {
                "lesson_intro": intro,
                "target": {
                    **target_dict(Target("廣東話", "gwong2 dung1 waa2", "Cantonese")),
                    "theme": "What Cantonese is",
                    "words": [],
                },
                "context": {
                    "traditional": "廣東話",
                    "jyutping": "gwong2 dung1 waa2",
                    "tones": [2, 1, 2],
                    "english": "What is Cantonese?",
                    "progression": 1,
                },
                "vocabulary": [],
                "steps": steps,
            },
        }

    def tone_lesson() -> dict:
        lesson_id = "v3-tones"
        intro = {
            "id": f"{lesson_id}-intro",
            "title": "聲調",
            "summary": "Jyutping spells Cantonese sounds; the final number marks one of six tones.",
            "learning_goals": [
                "Hear the six Cantonese tone contours",
                "Match a sound to its Jyutping and tone number",
                "Repeat a tone after listening",
            ],
            "new_items": [target_dict(item) for item in TONES],
            "review_items": [],
            "audio": audio(TONES[0]),
            "presentation": {
                "traditional_label": "Hidden source character",
                "romanization_label": "Jyutping",
                "listen_first": True,
            },
            "sections": [
                {
                    "type": "text",
                    "title": "Jyutping and tones",
                    "body": "Jyutping records pronunciation. The number after a syllable identifies its tone: si1 through si6.",
                },
                {
                    "type": "audio_grid",
                    "title": "Listen to all six",
                    "items": [
                        {
                            "label": item.jyutping,
                            "tone_label": TONE_LABELS[index],
                            "audio": audio(item),
                        }
                        for index, item in enumerate(TONES, start=1)
                    ],
                },
                {
                    "type": "comparison",
                    "title": "Listening and speaking",
                    "items": [
                        {
                            "label": "Listening",
                            "body": "Notice pitch height and movement.",
                        },
                        {
                            "label": "Speaking",
                            "body": "Copy both the syllable and its tone.",
                        },
                    ],
                },
            ],
        }
        steps = [intro_step(lesson_id, intro, f"{lesson_id}-hear")]
        for index, target in enumerate(TONES, start=1):
            steps.append(tone_recognition_step(lesson_id, index, target, TONES))
            steps.append(tone_challenge_step(lesson_id, index, target, TONES))
        same_pairs = [
            (TONES[0], TONES[0], True),
            (TONES[1], TONES[4], False),
            (TONES[5], TONES[5], True),
        ]
        for index, (first, second, same) in enumerate(same_pairs, start=1):
            steps.append(
                {
                    "id": f"{lesson_id}-compare-{index:02d}",
                    "type": "audio_comparison",
                    "skill": "listening",
                    "prompt": "Are these two Cantonese sounds the same?",
                    "audio": audio(first),
                    "options": [
                        {"id": "same", "label": "Same"},
                        {"id": "different", "label": "Different"},
                    ],
                    "correct_option_id": "same" if same else "different",
                    "comparison": {
                        "samples": [{"audio": audio(first)}, {"audio": audio(second)}]
                    },
                    "metadata": {
                        "objective_id": f"{lesson_id}-compare",
                        "section": "recognition",
                        "exercise_kind": "recognition",
                        "auditory_only_until_answer": True,
                    },
                }
            )
        for index, target in enumerate(TONES, start=1):
            steps.append(
                {
                    "id": f"{lesson_id}-speak-{index:02d}",
                    "type": "speak",
                    "skill": "speaking",
                    "prompt": f"Listen, then repeat {target.jyutping}.",
                    "audio": audio(target),
                    "reveal_jyutping": target.jyutping,
                    "metadata": {
                        "objective_id": f"{lesson_id}-speak",
                        "section": "challenge",
                        "exercise_kind": "challenge",
                        "expected": target.jyutping,
                        "expected_text": target.traditional,
                        "source_character_hidden": True,
                    },
                }
            )
        return {
            "id": lesson_id,
            "unit_id": "v3-unit-0",
            "title": "聲調",
            "lesson_type": "tone",
            "sort_order": 2,
            "prerequisites": ["v3-orientation"],
            "objectives": [
                f"{lesson_id}-hear",
                f"{lesson_id}-compare",
                f"{lesson_id}-speak",
            ],
            "content": {
                "lesson_intro": intro,
                "target": {
                    **target_dict(TONES[0]),
                    "theme": "Six Cantonese tones",
                    "words": [],
                },
                "context": {
                    "traditional": "聲調",
                    "jyutping": "sing1 diu6",
                    "tones": [1, 6],
                    "english": "Sounds and tones",
                    "progression": 2,
                },
                "vocabulary": [],
                "steps": steps,
            },
        }

    def gesture_path(number: int) -> str:
        return f"assets/number_gestures/{number}.png"

    def pool_options(
        pool: tuple[Target, ...], target: Target, label_kind: str
    ) -> list[dict]:
        choices = list(pool)
        for fallback in NUMBERS:
            if fallback not in choices:
                choices.append(fallback)
            if len(choices) >= 3:
                break
        result = []
        for candidate in choices:
            number = NUMBERS.index(candidate) + 1
            if label_kind == "character":
                label = candidate.traditional
            elif label_kind == "number":
                label = str(number)
            else:
                label = candidate.jyutping
            result.append({"id": f"number-{number}", "label": label})
        return result

    def number_practice(
        lesson_id: str,
        pool: tuple[Target, ...],
        target: Target,
        sequence: int,
        section: str,
    ) -> list[dict]:
        number = NUMBERS.index(target) + 1
        objective = f"{lesson_id}-numbers"
        character_options = pool_options(pool, target, "character")
        number_options = pool_options(pool, target, "number")
        jyutping_options = pool_options(pool, target, "jyutping")
        audio_choices = [
            {
                "id": f"number-{NUMBERS.index(item) + 1}",
                "label": f"Sound {index}",
                "audio": audio(item),
            }
            for index, item in enumerate(
                [target, *[candidate for candidate in pool if candidate != target]][:3],
                start=1,
            )
        ]
        while len(audio_choices) < 3:
            fallback = NUMBERS[len(audio_choices)]
            if all(
                choice["id"] != f"number-{NUMBERS.index(fallback) + 1}"
                for choice in audio_choices
            ):
                audio_choices.append(
                    {
                        "id": f"number-{NUMBERS.index(fallback) + 1}",
                        "label": f"Sound {len(audio_choices) + 1}",
                        "audio": audio(fallback),
                    }
                )
        common = dict(section=section, reveal=target, objective_id=objective)
        return [
            choice_step(
                f"{lesson_id}-{sequence:02d}-hear-character",
                "Listen. Choose the Traditional Chinese character.",
                character_options,
                f"number-{number}",
                audio_ref=audio(target),
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-character-hear",
                f"Which sound matches {target.traditional}?",
                audio_choices,
                f"number-{number}",
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-hear-number",
                "Listen. Choose the Arabic numeral.",
                number_options,
                f"number-{number}",
                audio_ref=audio(target),
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-number-character",
                f"Choose the Traditional Chinese character for {number}.",
                character_options,
                f"number-{number}",
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-character-jyutping",
                f"Choose the Jyutping for {target.traditional}.",
                jyutping_options,
                f"number-{number}",
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-gesture-number",
                "Which number does this Hong Kong hand gesture show?",
                number_options,
                f"number-{number}",
                prompt_image=gesture_path(number),
                exercise_type="image_comparison",
                **common,
            ),
            choice_step(
                f"{lesson_id}-{sequence:02d}-number-gesture",
                f"Choose the Hong Kong hand gesture for {number}.",
                [
                    {
                        "id": f"number-{NUMBERS.index(item) + 1}",
                        "label": str(NUMBERS.index(item) + 1),
                        "image": gesture_path(NUMBERS.index(item) + 1),
                    }
                    for item in [
                        target,
                        *[candidate for candidate in pool if candidate != target],
                    ][:3]
                ],
                f"number-{number}",
                exercise_type="image_comparison",
                **common,
            ),
            {
                "id": f"{lesson_id}-{sequence:02d}-speak",
                "type": "speak",
                "skill": "speaking",
                "prompt": f"Say {number} in Cantonese.",
                "audio": audio(target),
                "reveal_character": target.traditional,
                "reveal_jyutping": target.jyutping,
                "reveal_english": target.english,
                "metadata": {
                    "objective_id": objective,
                    "section": section,
                    "exercise_kind": section,
                    "expected": target.jyutping,
                    "expected_text": target.traditional,
                    "cumulative_pool": [item.traditional for item in pool],
                },
            },
        ]

    def number_intro(
        lesson_id: str, new_items: tuple[Target, ...], review: tuple[Target, ...]
    ) -> dict:
        return {
            "id": f"{lesson_id}-intro",
            "title": "、".join(item.traditional for item in new_items),
            "summary": "Learn the new number, then recognize it in every representation.",
            "learning_goals": [
                "Connect sound, Jyutping, character, Arabic numeral, and gesture",
                "Say each learned number in Cantonese",
            ],
            "new_items": [target_dict(item) for item in new_items],
            "review_items": [target_dict(item) for item in review],
            "audio": audio(new_items[0]),
            "presentation": {
                "traditional_label": "Traditional Chinese",
                "romanization_label": "Jyutping",
                "listen_first": True,
            },
            "sections": [
                {
                    "type": "number_rows",
                    "title": "New numbers",
                    "items": [
                        {
                            **target_dict(item),
                            "number": NUMBERS.index(item) + 1,
                            "image": gesture_path(NUMBERS.index(item) + 1),
                        }
                        for item in new_items
                    ],
                }
            ],
        }

    def learning_number_lesson(
        index: int,
        new_items: tuple[Target, ...],
        pool: tuple[Target, ...],
        previous: str,
    ) -> dict:
        lesson_id = f"v3-number-{index:02d}"
        intro = number_intro(lesson_id, new_items, pool[: len(pool) - len(new_items)])
        steps = [intro_step(lesson_id, intro, f"{lesson_id}-numbers")]
        for sequence, target in enumerate(pool, start=1):
            steps.extend(
                number_practice(lesson_id, pool, target, sequence, "recognition")
            )
        return {
            "id": lesson_id,
            "unit_id": "v3-unit-1",
            "title": "、".join(item.traditional for item in new_items),
            "lesson_type": "number",
            "sort_order": index,
            "prerequisites": [previous],
            "objectives": [f"{lesson_id}-numbers"],
            "content": {
                "lesson_intro": intro,
                "target": {
                    **target_dict(new_items[0]),
                    "theme": f"Numbers one through {len(pool)}",
                    "words": [target_dict(item) for item in pool],
                },
                "context": {
                    "traditional": "、".join(item.traditional for item in pool),
                    "jyutping": " ".join(item.jyutping for item in pool),
                    "tones": [tones(item.jyutping)[-1] for item in pool],
                    "english": f"Numbers one through {len(pool)}",
                    "progression": index + 2,
                },
                "vocabulary": [
                    {"lexeme_id": f"v3-number-{number:02d}"}
                    for number in range(1, len(pool) + 1)
                ],
                "steps": steps,
            },
        }

    def review_lesson(challenge: bool, previous: str) -> dict:
        index = 10 if challenge else 9
        lesson_id = "v3-number-challenge" if challenge else "v3-number-review"
        title = "數字挑戰" if challenge else "數字練習"
        steps: list[dict] = []
        if challenge:
            for sequence, target in enumerate(NUMBERS, start=1):
                number = sequence
                steps.append(
                    choice_step(
                        f"{lesson_id}-listen-{sequence:02d}",
                        "Listen. Choose the number.",
                        pool_options(NUMBERS, target, "number"),
                        f"number-{number}",
                        section="challenge",
                        audio_ref=audio(target),
                        reveal=target,
                        objective_id=f"{lesson_id}-mastery",
                    )
                )
            for sequence, target in enumerate(NUMBERS, start=1):
                steps.append(
                    {
                        "id": f"{lesson_id}-speak-{sequence:02d}",
                        "type": "speak",
                        "skill": "speaking",
                        "prompt": f"Say {sequence} in Cantonese.",
                        "audio": audio(target),
                        "metadata": {
                            "objective_id": f"{lesson_id}-mastery",
                            "section": "challenge",
                            "exercise_kind": "challenge",
                            "expected": target.jyutping,
                            "expected_text": target.traditional,
                        },
                    }
                )
            for sequence, target in enumerate(NUMBERS, start=1):
                steps.append(
                    choice_step(
                        f"{lesson_id}-gesture-{sequence:02d}",
                        "Identify the number shown by this Hong Kong hand gesture.",
                        pool_options(NUMBERS, target, "number"),
                        f"number-{sequence}",
                        section="challenge",
                        prompt_image=gesture_path(sequence),
                        reveal=target,
                        objective_id=f"{lesson_id}-mastery",
                        exercise_type="image_comparison",
                    )
                )
            for sequence, target in enumerate(NUMBERS, start=1):
                steps.append(
                    {
                        "id": f"{lesson_id}-typing-{sequence:02d}",
                        "type": "typing",
                        "skill": "writing",
                        "prompt": f"Type {sequence} as a Traditional Chinese character.",
                        "reveal_character": target.traditional,
                        "reveal_jyutping": target.jyutping,
                        "metadata": {
                            "objective_id": f"{lesson_id}-mastery",
                            "section": "challenge",
                            "exercise_kind": "challenge",
                            "accepted_answers": [target.traditional],
                            "input_mode": "chinese_character",
                        },
                    }
                )
        else:
            sequences = [
                (1, 4, 7),
                (8, 2, 10),
                (3, 9, 5),
                (6, 1, 8),
                (10, 7, 4),
            ]
            sequence_options = [
                {
                    "id": f"sequence-{sequence_index}",
                    "label": " · ".join(str(number) for number in numbers),
                }
                for sequence_index, numbers in enumerate(sequences, start=1)
            ]
            for sequence_index, numbers in enumerate(sequences, start=1):
                spoken = Target(
                    "、".join(NUMBERS[number - 1].traditional for number in numbers),
                    " ".join(NUMBERS[number - 1].jyutping for number in numbers),
                    "number sequence",
                )
                steps.append(
                    choice_step(
                        f"{lesson_id}-sequence-{sequence_index:02d}",
                        "Listen. Choose the number sequence in the same order.",
                        sequence_options,
                        f"sequence-{sequence_index}",
                        section="recognition",
                        audio_ref=audio(spoken),
                        reveal=spoken,
                        objective_id=f"{lesson_id}-mastery",
                    )
                )
            for sequence, target in enumerate(NUMBERS, start=1):
                steps.extend(
                    number_practice(lesson_id, NUMBERS, target, sequence, "recognition")
                )
        return {
            "id": lesson_id,
            "unit_id": "v3-unit-1",
            "title": title,
            "lesson_type": "number_challenge" if challenge else "number_review",
            "sort_order": index,
            "prerequisites": [previous],
            "objectives": [f"{lesson_id}-mastery"],
            "content": {
                "target": {
                    **target_dict(NUMBERS[-1]),
                    "theme": title,
                    "words": [target_dict(item) for item in NUMBERS],
                },
                "context": {
                    "traditional": "一、二、三、四、五、六、七、八、九、十",
                    "jyutping": " ".join(item.jyutping for item in NUMBERS),
                    "tones": [tones(item.jyutping)[-1] for item in NUMBERS],
                    "english": title,
                    "progression": index + 2,
                },
                "vocabulary": [
                    {"lexeme_id": f"v3-number-{number:02d}"} for number in range(1, 11)
                ],
                "steps": steps,
            },
        }

    units = [
        {
            "id": "v3-unit-0",
            "title": "廣東話",
            "phase": "orientation",
            "sort_order": 0,
            "prerequisites": [],
        },
        {
            "id": "v3-unit-1",
            "title": "數字",
            "phase": "numbers",
            "sort_order": 1,
            "prerequisites": ["v3-unit-0"],
        },
        {
            "id": "v3-unit-2",
            "title": "介紹自己",
            "phase": "introductions",
            "sort_order": 2,
            "prerequisites": ["v3-unit-1"],
        },
    ]
    lessons = [conceptual_lesson(), tone_lesson()]
    previous = "v3-tones"
    first = learning_number_lesson(1, NUMBERS[:3], NUMBERS[:3], previous)
    lessons.append(first)
    previous = first["id"]
    for index, number_count in enumerate(range(4, 11), start=2):
        lesson = learning_number_lesson(
            index,
            (NUMBERS[number_count - 1],),
            NUMBERS[:number_count],
            previous,
        )
        lessons.append(lesson)
        previous = lesson["id"]
    review = review_lesson(False, previous)
    lessons.append(review)
    challenge = review_lesson(True, review["id"])
    lessons.append(challenge)
    lessons.extend(build_introduction_lessons(challenge["id"]))

    lexemes = [
        {
            "id": "v3-cantonese",
            **target_dict(Target("廣東話", "gwong2 dung1 waa2", "Cantonese")),
            "tags": ["beginner-v3", "orientation"],
            "difficulty": 1,
        },
        {
            "id": "v3-yue",
            **target_dict(Target("粵語", "jyut6 jyu5", "Cantonese language")),
            "tags": ["beginner-v3", "orientation"],
            "difficulty": 1,
        },
    ]
    lexemes.extend(
        {
            "id": f"v3-tone-{index}",
            **target_dict(target),
            "tags": ["beginner-v3", "tone", f"tone-{index}"],
            "difficulty": 1,
        }
        for index, target in enumerate(TONES, start=1)
    )
    lexemes.extend(
        {
            "id": f"v3-number-{index:02d}",
            **target_dict(target),
            "tags": ["beginner-v3", "number", f"number-{index}"],
            "difficulty": 1 if index <= 5 else 2,
        }
        for index, target in enumerate(NUMBERS, start=1)
    )
    spoken_lexemes = [
        (WO, "v3-wo"),
        (GIU, "v3-giu"),
        (HAI, "v3-hai"),
        (GO, "v3-go"),
        (MING, "v3-ming"),
        (JAU, "v3-jau"),
        (BUN, "v3-bun"),
        (SYU, "v3-syu"),
        (NEI, "v3-nei"),
        (ME, "v3-me"),
        (HAI_MAI, "v3-hai-mai"),
    ]
    lexemes.extend(
        {
            "id": lexeme_id,
            **target_dict(target),
            "tags": ["beginner-v3", "introduction", "spoken"],
            "difficulty": 1,
        }
        for target, lexeme_id in spoken_lexemes
    )
    lexemes.append(
        {
            "id": "v3-jordyn",
            "traditional": JORDYN,
            "jyutping": "",
            "english": JORDYN,
            "placeholder": True,
            "tags": ["beginner-v3", "introduction", "placeholder"],
            "difficulty": 1,
        }
    )
    step_count = sum(len(lesson["content"]["steps"]) for lesson in lessons)
    return {
        "version": "3.0.0",
        "level": "beginner",
        "generator": {
            "name": "generate_beginner_v3.py",
            "deterministic": True,
            "unit_count": 3,
            "lesson_count": 18,
            "step_count": step_count,
            "number_gesture_assets": [gesture_path(number) for number in range(1, 11)],
        },
        "units": units,
        "lexemes": lexemes,
        "characters": [],
        "lessons": lessons,
        "stories": [],
    }


def curriculum_expectations() -> dict:
    document = generate_document()
    lessons = document["lessons"]
    steps = [step for lesson in lessons for step in lesson["content"]["steps"]]
    return {
        "lesson_count": len(lessons),
        "unit_lesson_counts": [
            sum(lesson["unit_id"] == unit["id"] for lesson in lessons)
            for unit in document["units"]
        ],
        "lesson_types": dict(Counter(lesson["lesson_type"] for lesson in lessons)),
        "exercise_types": dict(Counter(step["type"] for step in steps)),
        "skills": dict(Counter(step["skill"] for step in steps)),
        "progression": list(range(1, len(lessons) + 1)),
    }


def main() -> None:
    document = generate_document()
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    for output in dict.fromkeys((OUTPUT, MIRROR_OUTPUT)):
        output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {output} with {len(document['lessons'])} lessons")
    if Path(__file__).resolve() != MIRROR_GENERATOR.resolve():
        MIRROR_GENERATOR.write_text(
            Path(__file__).read_text(encoding="utf-8"), encoding="utf-8"
        )
        print(f"Mirrored generator to {MIRROR_GENERATOR}")
    if V2_GENERATOR.exists() and not MIRROR_V2_GENERATOR.exists():
        MIRROR_V2_GENERATOR.write_text(
            V2_GENERATOR.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print(f"Mirrored v2 generator to {MIRROR_V2_GENERATOR}")


if __name__ == "__main__":
    main()
