"""BTO-vs-Resale recommendation from a short questionnaire.

A small, declarative points engine: each answer adds points toward BTO or
Resale; the net leaning becomes the recommendation, with reasons tied to the
answers that drove it. When a town + flat type are supplied, the live
BTO-vs-resale comparison is attached and a price-gap reason is woven in.

Adding/tuning a question is one entry in QUESTIONS — the API exposes the schema
so the form renders dynamically.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    bto: int = 0
    resale: int = 0
    reason: str = ""   # why this answer leans the way it does


@dataclass(frozen=True)
class Question:
    id: str
    label: str
    options: list[Option] = field(default_factory=list)


QUESTIONS: tuple[Question, ...] = (
    Question("timeline", "When do you need to move in?", [
        Option("soon", "Within a year", resale=3,
               reason="you need to move within a year — a new BTO takes ~3–4 years to build"),
        Option("mid", "In 1–3 years", resale=1,
               reason="your timeline is fairly near-term"),
        Option("flexible", "Flexible — 3+ years is fine", bto=2,
               reason="you can wait, which suits a BTO's build time"),
    ]),
    Question("budget", "How much does the lowest price matter?", [
        Option("tight", "A lot — I want the cheapest option", bto=2,
               reason="BTO flats are subsidised and cheaper than resale"),
        Option("comfortable", "It's not my main concern"),
    ]),
    Question("location", "How specific is your preferred location?", [
        Option("specific", "I want a particular town or area", resale=2,
               reason="resale lets you buy in any town; BTO launches are limited to a few"),
        Option("open", "Open to wherever's good value", bto=1,
               reason="being location-flexible opens up more BTO launches"),
    ]),
    Question("eligibility", "Which best describes you?", [
        Option("first_fam", "First-timer family", bto=1,
               reason="first-timer families get the best BTO ballot odds and grants"),
        Option("second_fam", "Second-timer family", resale=1,
               reason="second-timers face lower BTO odds and tighter restrictions"),
        Option("single_young", "Single, under 35", resale=2,
               reason="under-35 singles can't buy most BTO flats"),
        Option("single_senior", "Single, 35 or older"),
        Option("senior", "Senior / retiree", bto=1,
               reason="seniors get priority BTO schemes such as 2-room Flexi"),
    ]),
    Question("certainty", "How do you feel about balloting?", [
        Option("certain", "I want a flat for sure, soon", resale=2,
               reason="resale has no ballot — you buy a flat directly"),
        Option("ok_ballot", "OK to ballot a few times", bto=2,
               reason="you're willing to ballot, which a BTO requires"),
    ]),
    Question("priority", "What matters most to you?", [
        Option("price", "The lowest price", bto=2,
               reason="price is your priority, and BTO is the cheaper route"),
        Option("speed", "Moving in fast", resale=2,
               reason="resale lets you move in within months"),
        Option("location2", "A specific location", resale=1,
               reason="you want a specific spot, which resale offers"),
        Option("value", "Long-term value", resale=1,
               reason="resale flats are more liquid to sell or upgrade later"),
    ]),
)

_BY_ID = {q.id: q for q in QUESTIONS}


def questions() -> list[dict]:
    return [{"id": q.id, "label": q.label,
             "options": [{"value": o.value, "label": o.label} for o in q.options]}
            for q in QUESTIONS]


def recommend(answers: dict, repo=None, engine=None,
              town: str | None = None, flat_type: str | None = None) -> dict:
    bto = resale = 0
    leaning: list[tuple[str, str]] = []   # (side, reason)
    for q in QUESTIONS:
        opt = next((o for o in q.options if o.value == answers.get(q.id)), None)
        if opt is None:
            continue
        bto += opt.bto
        resale += opt.resale
        if opt.reason:
            side = "bto" if opt.bto > opt.resale else "resale" if opt.resale > opt.bto else None
            if side:
                leaning.append((side, opt.reason))

    net = bto - resale
    if net >= 3:
        rec = "bto"
    elif net <= -3:
        rec = "resale"
    else:
        rec = "either"
    confidence = ("strong" if abs(net) >= 5 else "moderate" if abs(net) >= 3 else "lean")

    if rec == "either":
        reasons = [r for _, r in leaning][:4]
    else:
        reasons = [r for s, r in leaning if s == rec][:4]

    # Data grounding.
    comparison = None
    if town and flat_type and repo is not None and engine is not None:
        try:
            from app.services.bto_compare import compare
            comparison = compare(repo, engine, town, flat_type)
            diff = comparison["gap"]["price_diff"]
            pct = comparison["gap"]["price_pct"]
            if diff:
                more = "more" if diff > 0 else "less"
                reasons.insert(0, f"In {town}, a {flat_type} resale costs about "
                                  f"${abs(diff):,} {more} than a new BTO ({pct}%).")
        except Exception:
            comparison = None

    if not reasons:
        reasons = ["Your answers are evenly balanced — both BTO and resale are reasonable."]

    return {
        "recommendation": rec,
        "confidence": confidence,
        "score": {"bto": bto, "resale": resale, "net": net},
        "reasons": reasons[:5],
        "comparison": comparison,
    }
