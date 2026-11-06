"""Basic content checks for one completed French text stage."""

import json
from pathlib import Path
import re
import sys
import unicodedata


COUNTS = {"01": 600, "02": 800, "03": 1000, "04": 1200,
          "05": 1400, "06": 1600, "07": 1000}
REQUIRED = {"schema_version", "id", "locale", "sentence", "cloze", "answer",
            "accepted_answers", "lemma", "meaning", "part_of_speech"}
OPTIONAL = {"register", "note"}
SPECIFIC = {"noun_support", "verb_frame", "pronunciation", "usage"}
ROOT = Path(__file__).resolve().parents[1]


def words(text):
    return len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text))


def characters(text):
    return sum(not ch.isspace() for ch in unicodedata.normalize("NFC", text))


def check(stage):
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    cards = json.loads((ROOT / "cards/fr-FR" / f"{stage}.json").read_text())
    require(isinstance(cards, list), "Stage must be a JSON array")
    if not isinstance(cards, list):
        return errors
    expected = [f"fr-{stage}-{index:04d}" for index in range(1, COUNTS[stage] + 1)]
    require(len(cards) == COUNTS[stage], f"Expected {COUNTS[stage]} cards")
    actual = []
    seen_sentences = {}
    seen_ids = set()
    for prior in sorted((ROOT / "cards/fr-FR").glob("*.json")):
        if prior.stem >= stage:
            continue
        for card in json.loads(prior.read_text()):
            c = card["common"]
            seen_ids.add(c["id"])
            seen_sentences[" ".join(c["sentence"].casefold().split())] = c["id"]

    word_cap, char_cap = (12, 90) if stage == "01" else (16, 120) if stage == "02" else (20, 150)
    for index, card in enumerate(cards, 1):
        label = f"card {index}"
        require(isinstance(card, dict) and set(card) == {"common", "language_specific"},
                f"{label}: expected exactly two regions")
        if not isinstance(card, dict) or not all(isinstance(card.get(k), dict) for k in ("common", "language_specific")):
            errors.append(f"{label}: regions must be objects")
            continue
        c, specific = card["common"], card["language_specific"]
        label = c.get("id", label)
        actual.append(c.get("id"))
        require(REQUIRED <= set(c) <= REQUIRED | OPTIONAL, f"{label}: common fields")
        require(type(c.get("schema_version")) is int and c["schema_version"] == 2,
                f"{label}: schema version")
        require(c.get("locale") == "fr-FR", f"{label}: locale")
        for key in (REQUIRED | OPTIONAL) - {"schema_version", "accepted_answers"}:
            if key in c:
                value = c[key]
                require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty {key}")
                if isinstance(value, str):
                    require(value == unicodedata.normalize("NFC", value), f"{label}: NFC {key}")
        if not all(isinstance(c.get(k), str) for k in ("sentence", "cloze", "answer")):
            continue
        sentence, cloze = c["sentence"], c["cloze"]
        require(cloze == c["answer"], f"{label}: answer differs from cloze")
        require(bool(cloze) and sentence.count(cloze) == 1, f"{label}: cloze must occur exactly once")
        require(words(sentence) <= word_cap and characters(sentence) <= char_cap,
                f"{label}: sentence exceeds caps")
        variants = c.get("accepted_answers")
        require(isinstance(variants, list), f"{label}: accepted_answers must be an array")
        for value in [cloze] + (variants if isinstance(variants, list) else []):
            require(isinstance(value, str) and bool(value.strip()), f"{label}: empty/nonstring answer")
            if isinstance(value, str):
                require(value == unicodedata.normalize("NFC", value), f"{label}: NFC answer")
                require(words(value) <= 5 and characters(value) <= 40, f"{label}: answer exceeds caps")
        require(c.get("id") not in seen_ids, f"{label}: duplicate ID")
        seen_ids.add(c.get("id"))
        sentence_key = " ".join(sentence.casefold().split())
        require(sentence_key not in seen_sentences,
                f"{label}: duplicate sentence with {seen_sentences.get(sentence_key)}")
        seen_sentences[sentence_key] = label
        require(set(specific) <= SPECIFIC, f"{label}: unknown language-specific field")
        for key, value in specific.items():
            if key == "noun_support":
                require(isinstance(value, list) and bool(value) and
                        all(isinstance(v, str) and bool(v.strip()) for v in value),
                        f"{label}: noun_support must be a nonempty string array")
            else:
                require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty {key}")
            if key == "pronunciation" and isinstance(value, str):
                require(value.startswith(("Target:", "Sentence:")), f"{label}: pronunciation scope")
            support_values = value if isinstance(value, list) else [value]
            for support in support_values:
                if isinstance(support, str):
                    require(support == unicodedata.normalize("NFC", support),
                            f"{label}: NFC {key}")
    require(actual == expected, "IDs must match the complete stage in order")

    coverage = (ROOT / "coverage/fr-FR" / f"{stage}.md").read_text()
    rows = [line for line in coverage.splitlines() if re.match(r"\|\s*fr-\d{2}-\d{4}\s*\|", line)]
    coverage_ids = []
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        require(len(cells) == 3 and all(cells), f"Invalid coverage row: {line}")
        coverage_ids.append(cells[0])
    require(coverage_ids == expected, "Expected one ordered coverage row per card")
    return errors


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COUNTS:
        raise SystemExit("Usage: ./.venv/bin/python scripts/check_text.py NN")
    try:
        errors = check(sys.argv[1])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"PASS: stage {sys.argv[1]}, exact card/coverage counts, fields, clozes, caps and duplicates")
