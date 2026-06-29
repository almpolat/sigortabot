"""Soru seçici: data/questions.json'dan akıllı sıralama ile soru seçer."""

import json
import random
from pathlib import Path
from typing import Optional

DATA_PATH = Path(__file__).parent.parent / "data" / "questions.json"


def load_questions() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["sorular"]


def pick_questions(
    n: int = 5,
    kategori: Optional[str] = None,
    min_komik: int = 1,
    seed: Optional[int] = None,
) -> list[dict]:
    """
    En yüksek komik_potansiyel'e sahip soruları seçer.
    n: kaç soru seçileceği
    kategori: filtre (None = hepsi)
    min_komik: minimum komik_potansiyel eşiği (1-5)
    seed: tekrarlanabilirlik için
    """
    questions = load_questions()

    if kategori:
        questions = [q for q in questions if q["kategori"] == kategori]

    questions = [q for q in questions if q["komik_potansiyel"] >= min_komik]

    questions.sort(key=lambda q: q["komik_potansiyel"], reverse=True)

    if seed is not None:
        random.seed(seed)

    # Yüksek komik_potansiyel'e ağırlık ver ama tam sıralı olmasın
    weights = [q["komik_potansiyel"] ** 2 for q in questions]
    selected = random.choices(questions, weights=weights, k=min(n, len(questions)))

    # Tekrarları kaldır (id bazında)
    seen = set()
    unique = []
    for q in selected:
        if q["id"] not in seen:
            seen.add(q["id"])
            unique.append(q)

    return unique


def get_question_by_id(question_id: int) -> Optional[dict]:
    questions = load_questions()
    return next((q for q in questions if q["id"] == question_id), None)


def get_categories() -> list[str]:
    questions = load_questions()
    return list({q["kategori"] for q in questions})
