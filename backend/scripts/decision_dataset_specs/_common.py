"""Shared helpers for the built-in decision dataset generators.

Every spec module in this package builds its rows from hand-written
templates with ``{slot}`` placeholders. The helpers below fill those
templates from slot pools, add light conversational wrapping (greetings,
sign-offs) and stylistic noise (lowercase, dropped punctuation), and
guarantee per-label uniqueness so the published datasets contain no
duplicate rows.

All randomness flows through the ``random.Random`` instance handed in by
the caller, so the output is fully deterministic for a given seed.
"""

from __future__ import annotations

import random
import re
from typing import Callable, Iterable, Mapping, Sequence, Union

SlotValue = Union[Sequence[str], Callable[[random.Random], str]]
Slots = Mapping[str, SlotValue]

_SLOT_RE = re.compile(r"\{(=?)(\w+)\}")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Collapse whitespace and fix spacing before punctuation."""
    text = _WS_RE.sub(" ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def render(template: str, slots: Slots, rng: random.Random) -> str:
    """Fill every ``{slot}`` in ``template`` with a random value from ``slots``.

    A slot value may be a sequence of strings (one is picked) or a callable
    taking the RNG (useful for numbers, ids and dates). When the same slot
    appears twice, each occurrence gets a *different* value where possible
    ("{plan} vs {plan}" → "Plus vs Team"); write ``{=slot}`` to repeat the
    value drawn earlier instead ("You are {persona}. {=persona} never ...").
    """
    drawn: dict[str, list[str]] = {}

    def repl(match: re.Match) -> str:
        reuse, key = match.group(1), match.group(2)
        if key not in slots:
            raise KeyError(f"Template slot '{{{key}}}' has no values: {template!r}")
        if reuse and drawn.get(key):
            return drawn[key][-1]
        value = slots[key]
        previous = drawn.setdefault(key, [])
        for _ in range(8):
            choice = value(rng) if callable(value) else rng.choice(list(value))
            if choice not in previous:
                break
        previous.append(choice)
        return choice

    # Two passes so slot values may themselves contain slots.
    out = _SLOT_RE.sub(repl, template)
    if _SLOT_RE.search(out):
        out = _SLOT_RE.sub(repl, out)
    return normalize(out)


def stylize(text: str, rng: random.Random, p_lower: float = 0.12, p_strip_punct: float = 0.08) -> str:
    """Apply light, label-preserving noise that mimics real user input."""
    if rng.random() < p_lower:
        text = text.lower()
    if rng.random() < p_strip_punct:
        text = text.rstrip(".!")
    return text


def wrap(
    text: str,
    rng: random.Random,
    prefixes: Sequence[str] = (),
    suffixes: Sequence[str] = (),
    p_prefix: float = 0.35,
    p_suffix: float = 0.35,
) -> str:
    """Optionally prepend a greeting and append a sign-off."""
    if prefixes and rng.random() < p_prefix:
        prefix = rng.choice(list(prefixes))
        # "Hi, How do I…" reads wrong; turn a trailing comma into "!" so the
        # capitalised template that follows stays grammatical.
        if prefix.endswith(","):
            prefix = prefix[:-1] + "!"
        text = f"{prefix} {text}"
    if suffixes and rng.random() < p_suffix:
        text = f"{text} {rng.choice(list(suffixes))}"
    return normalize(text)


def label_items(
    rng: random.Random,
    label: str,
    n: int,
    templates: Sequence[str],
    slots: Slots,
    *,
    hard_templates: Sequence[str] = (),
    hard_share: float = 0.0,
    prefixes: Sequence[str] = (),
    suffixes: Sequence[str] = (),
    p_prefix: float = 0.35,
    p_suffix: float = 0.35,
    style: bool = True,
    max_attempts_factor: int = 80,
) -> list[dict]:
    """Generate ``n`` unique rows for ``label``.

    ``hard_share`` of the rows (rounded) come from ``hard_templates`` and are
    tagged ``difficulty="hard"`` — use them for ambiguous phrasing, hard
    negatives, or messages that mention another label's vocabulary while
    still clearly belonging to this one.
    """
    if not templates:
        raise ValueError(f"No templates for label '{label}'")
    n_hard = int(round(n * hard_share)) if hard_templates else 0
    n_easy = n - n_hard

    seen: set[str] = set()
    items: list[dict] = []

    def produce(pool: Sequence[str], count: int, difficulty: str) -> None:
        produced = 0
        attempts = 0
        limit = max(count * max_attempts_factor, 200)
        while produced < count and attempts < limit:
            attempts += 1
            text = render(rng.choice(list(pool)), slots, rng)
            text = wrap(text, rng, prefixes, suffixes, p_prefix, p_suffix)
            if style:
                text = stylize(text, rng)
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append({"text": text, "label": label, "difficulty": difficulty})
            produced += 1
        if produced < count:
            raise ValueError(
                f"Label '{label}': only {produced}/{count} unique {difficulty} rows "
                f"after {attempts} attempts — add more templates or slot values."
            )

    produce(templates, n_easy, "easy")
    if n_hard:
        produce(hard_templates, n_hard, "hard")
    return items


# ── Reusable slot generators ────────────────────────────────────────────

FIRST_NAMES = [
    "Alex", "Maria", "John", "Priya", "Chen", "Fatima", "Lucas", "Emma", "Diego",
    "Aisha", "Noah", "Sofia", "Kenji", "Olivia", "Mateo", "Hannah", "Omar", "Laura",
    "Ivan", "Grace", "Rafael", "Zoe", "Samuel", "Yuki", "Daniel", "Amara",
]

LAST_NAMES = [
    "Smith", "Silva", "Johnson", "Patel", "Wang", "Khan", "Garcia", "Müller",
    "Rossi", "Kim", "Nguyen", "Brown", "Costa", "Ivanova", "Okafor", "Lopez",
]


def full_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def amount(rng: random.Random, low: int = 5, high: int = 900, symbol: str = "$") -> str:
    value = rng.uniform(low, high)
    if rng.random() < 0.4:
        return f"{symbol}{int(value)}"
    return f"{symbol}{value:,.2f}"


def order_id(rng: random.Random, prefix: str = "") -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"#{rng.randint(100000, 999999)}"
    if style == 1:
        return f"{prefix or 'ORD'}-{rng.randint(10000, 99999)}"
    return f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(1000000, 9999999)}"


MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def date_phrase(rng: random.Random) -> str:
    style = rng.randint(0, 3)
    if style == 0:
        return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 1:
        return f"last {rng.choice(WEEKDAYS)}"
    if style == 2:
        return f"{rng.randint(2, 14)} days ago"
    return f"on the {rng.randint(1, 28)}th"


def clock_time(rng: random.Random) -> str:
    hour = rng.randint(7, 19)
    minute = rng.choice([0, 15, 30, 45])
    suffix = "am" if hour < 12 else "pm"
    hour12 = hour if hour <= 12 else hour - 12
    return f"{hour12}:{minute:02d}{suffix}" if minute else f"{hour12}{suffix}"


def digits(n: int) -> Callable[[random.Random], str]:
    def _gen(rng: random.Random) -> str:
        return "".join(str(rng.randint(0, 9)) for _ in range(n))

    return _gen


def integer(low: int, high: int) -> Callable[[random.Random], str]:
    def _gen(rng: random.Random) -> str:
        return str(rng.randint(low, high))

    return _gen


def merge(*parts: Iterable[dict]) -> list[dict]:
    out: list[dict] = []
    for part in parts:
        out.extend(part)
    return out
