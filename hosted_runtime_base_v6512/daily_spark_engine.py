"""Deterministic ScoreMax V6.2.5 Daily Spark helpers.

No Flask or external AI dependency. Academic source material stays governed in
ScoreMax; Word of the Day is selected from a stored, age-appropriate library.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from typing import Any, Iterable

WORD_LIBRARY: tuple[dict[str, Any], ...] = (
    {"word":"Abundant","pronunciation":"uh-BUN-duhnt","definition":"Existing in large quantities; plentiful.","example":"The library offered abundant resources for independent study.","synonym":"plentiful","antonym":"scarce","application":"Use it to describe resources, evidence or opportunities.","difficulty":2,"min_age":11,"max_age":18,"tags":["general","academic"]},
    {"word":"Adaptable","pronunciation":"uh-DAP-tuh-buhl","definition":"Able to adjust successfully to new conditions.","example":"An adaptable learner changes strategy when the first method does not work.","synonym":"flexible","antonym":"inflexible","application":"Useful when writing about people, systems or survival.","difficulty":2,"min_age":11,"max_age":18,"tags":["general","communication"]},
    {"word":"Ambiguous","pronunciation":"am-BIG-yoo-uhs","definition":"Open to more than one interpretation; not completely clear.","example":"The ambiguous instruction led students to understand the task differently.","synonym":"unclear","antonym":"unambiguous","application":"Useful in language analysis and evaluation.","difficulty":3,"min_age":13,"max_age":19,"tags":["academic","exam"]},
    {"word":"Articulate","pronunciation":"ar-TIK-yuh-luht","definition":"Able to express ideas clearly and effectively.","example":"She gave an articulate explanation of her opinion.","synonym":"eloquent","antonym":"inarticulate","application":"Use it to describe clear speaking or writing.","difficulty":3,"min_age":12,"max_age":19,"tags":["communication","general"]},
    {"word":"Astute","pronunciation":"uh-STYOOT","definition":"Quick to notice and understand important details.","example":"His astute observation revealed the weakness in the argument.","synonym":"perceptive","antonym":"unobservant","application":"Strong evaluative vocabulary for people and decisions.","difficulty":4,"min_age":14,"max_age":20,"tags":["general","academic"]},
    {"word":"Authentic","pronunciation":"aw-THEN-tik","definition":"Genuine, real or true to its origin.","example":"The historian compared the letter with other authentic records.","synonym":"genuine","antonym":"fake","application":"Useful when discussing evidence, experiences or identity.","difficulty":2,"min_age":11,"max_age":20,"tags":["general","academic"]},
    {"word":"Coherent","pronunciation":"koh-HEER-uhnt","definition":"Clear, logical and well organised.","example":"Her essay presented a coherent argument from beginning to end.","synonym":"logical","antonym":"confused","application":"A key word for evaluating writing and explanations.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","exam"]},
    {"word":"Compelling","pronunciation":"kuhm-PEL-ing","definition":"So convincing or interesting that it strongly holds attention.","example":"The writer used compelling evidence to support the claim.","synonym":"persuasive","antonym":"unconvincing","application":"Useful in essays, reviews and argument analysis.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","communication"]},
    {"word":"Concise","pronunciation":"kuhn-SISE","definition":"Expressing something clearly in only a few words.","example":"The best response was accurate, relevant and concise.","synonym":"brief","antonym":"wordy","application":"Useful for exam answers and professional communication.","difficulty":2,"min_age":11,"max_age":20,"tags":["exam","communication"]},
    {"word":"Conscientious","pronunciation":"kon-shee-EN-shuhs","definition":"Careful, responsible and committed to doing things properly.","example":"The conscientious student checked every source before submitting the work.","synonym":"diligent","antonym":"careless","application":"Use it to describe responsible behaviour.","difficulty":4,"min_age":14,"max_age":20,"tags":["general","character"]},
    {"word":"Credible","pronunciation":"KRED-uh-buhl","definition":"Believable and worthy of trust.","example":"A credible source explains where its information came from.","synonym":"reliable","antonym":"dubious","application":"Important for source evaluation and research.","difficulty":2,"min_age":11,"max_age":20,"tags":["academic","digital-literacy"]},
    {"word":"Diligent","pronunciation":"DIL-uh-juhnt","definition":"Showing steady, careful effort in work or duties.","example":"Her diligent revision produced gradual improvement.","synonym":"hard-working","antonym":"negligent","application":"Useful for describing sustained effort.","difficulty":3,"min_age":12,"max_age":20,"tags":["general","character"]},
    {"word":"Discerning","pronunciation":"dih-SUR-ning","definition":"Able to judge quality or truth carefully.","example":"A discerning reader notices both the strengths and limitations of a source.","synonym":"judicious","antonym":"undiscriminating","application":"Strong vocabulary for critical thinking.","difficulty":4,"min_age":14,"max_age":20,"tags":["academic","general"]},
    {"word":"Eloquent","pronunciation":"EL-uh-kwuhnt","definition":"Fluent, clear and persuasive in speaking or writing.","example":"Her eloquent speech encouraged the audience to reconsider the issue.","synonym":"expressive","antonym":"inarticulate","application":"Useful when analysing speeches or describing communication.","difficulty":4,"min_age":13,"max_age":20,"tags":["communication","general"]},
    {"word":"Empirical","pronunciation":"em-PIR-i-kuhl","definition":"Based on observation, experience or measured evidence.","example":"The conclusion was supported by empirical data from the experiment.","synonym":"evidence-based","antonym":"theoretical","application":"Useful in science, research and evaluation.","difficulty":4,"min_age":14,"max_age":20,"tags":["academic","science"]},
    {"word":"Endeavour","pronunciation":"en-DEV-uhr","definition":"A serious attempt or effort to achieve something.","example":"Completing the project became a shared endeavour.","synonym":"effort","antonym":"inaction","application":"A strong alternative to 'try' or 'attempt'.","difficulty":3,"min_age":12,"max_age":20,"tags":["general","writing"]},
    {"word":"Evaluate","pronunciation":"ih-VAL-yoo-ayt","definition":"To judge quality or value using relevant evidence.","example":"Evaluate the argument by considering its evidence and limitations.","synonym":"assess","antonym":"ignore","application":"A common examination command word.","difficulty":2,"min_age":11,"max_age":20,"tags":["exam","academic"]},
    {"word":"Formidable","pronunciation":"FOR-mi-duh-buhl","definition":"Inspiring respect because of great strength, difficulty or ability.","example":"The team faced a formidable challenge but prepared carefully.","synonym":"daunting","antonym":"manageable","application":"Useful descriptive vocabulary for challenges or opponents.","difficulty":4,"min_age":13,"max_age":20,"tags":["general","writing"]},
    {"word":"Impartial","pronunciation":"im-PAR-shuhl","definition":"Fair and not favouring one side.","example":"An impartial reviewer considers the evidence before reaching a judgement.","synonym":"unbiased","antonym":"biased","application":"Useful in discussions of fairness, evidence and judgement.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","citizenship"]},
    {"word":"Innovative","pronunciation":"IN-uh-vay-tiv","definition":"Introducing a new and effective idea or method.","example":"The students proposed an innovative way to reduce waste.","synonym":"inventive","antonym":"conventional","application":"Useful in business, science and design writing.","difficulty":2,"min_age":11,"max_age":20,"tags":["general","academic"]},
    {"word":"Insightful","pronunciation":"IN-site-fuhl","definition":"Showing a deep and accurate understanding.","example":"Her insightful comment connected the evidence to the wider issue.","synonym":"perceptive","antonym":"superficial","application":"Useful for evaluating analysis and interpretation.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","communication"]},
    {"word":"Meticulous","pronunciation":"muh-TIK-yuh-luhs","definition":"Extremely careful and precise about details.","example":"He was meticulous when checking every calculation.","synonym":"thorough","antonym":"careless","application":"Useful for describing high-quality working habits.","difficulty":4,"min_age":13,"max_age":20,"tags":["general","character"]},
    {"word":"Nuanced","pronunciation":"NYOO-ahnst","definition":"Showing subtle differences or careful distinctions.","example":"A nuanced answer recognises that the issue has more than one side.","synonym":"subtle","antonym":"simplistic","application":"Excellent vocabulary for higher-level evaluation.","difficulty":4,"min_age":14,"max_age":20,"tags":["academic","exam"]},
    {"word":"Pragmatic","pronunciation":"prag-MAT-ik","definition":"Focused on practical results rather than ideal theories.","example":"They chose a pragmatic solution that could be implemented immediately.","synonym":"practical","antonym":"idealistic","application":"Useful in business, politics and decision-making contexts.","difficulty":4,"min_age":14,"max_age":20,"tags":["general","academic"]},
    {"word":"Prevalent","pronunciation":"PREV-uh-luhnt","definition":"Common or widespread in a particular place or time.","example":"Online learning became increasingly prevalent.","synonym":"widespread","antonym":"rare","application":"Useful when describing trends and patterns.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","writing"]},
    {"word":"Profound","pronunciation":"pruh-FOUND","definition":"Very great, deep or important.","example":"The discovery had a profound effect on scientific thinking.","synonym":"deep","antonym":"superficial","application":"Useful for describing effects, ideas and emotions.","difficulty":3,"min_age":12,"max_age":20,"tags":["general","writing"]},
    {"word":"Resilient","pronunciation":"rih-ZIL-yuhnt","definition":"Able to recover and continue after difficulty.","example":"She remained resilient after a disappointing result and adjusted her plan.","synonym":"strong","antonym":"fragile","application":"Useful for personal development and character descriptions.","difficulty":2,"min_age":11,"max_age":20,"tags":["general","character"]},
    {"word":"Scrutinise","pronunciation":"SKROO-tuh-nize","definition":"To examine something very carefully.","example":"Scrutinise the graph before deciding which conclusion is supported.","synonym":"inspect","antonym":"glance","application":"Useful for exam instructions and source analysis.","difficulty":4,"min_age":13,"max_age":20,"tags":["academic","exam"]},
    {"word":"Substantiate","pronunciation":"sub-STAN-shee-ayt","definition":"To support a claim with evidence.","example":"The writer must substantiate the conclusion with reliable data.","synonym":"verify","antonym":"disprove","application":"Powerful vocabulary for evidence-based writing.","difficulty":5,"min_age":15,"max_age":20,"tags":["academic","exam"]},
    {"word":"Tenacious","pronunciation":"tuh-NAY-shuhs","definition":"Very determined and unwilling to give up.","example":"Her tenacious approach helped her master a difficult topic.","synonym":"persistent","antonym":"easily discouraged","application":"Useful for describing determination.","difficulty":4,"min_age":13,"max_age":20,"tags":["general","character"]},
    {"word":"Tentative","pronunciation":"TEN-tuh-tiv","definition":"Not fully certain or decided; cautious.","example":"The researchers reached a tentative conclusion because the sample was small.","synonym":"provisional","antonym":"definite","application":"Useful when evidence is limited.","difficulty":3,"min_age":13,"max_age":20,"tags":["academic","science"]},
    {"word":"Thrive","pronunciation":"thryve","definition":"To grow, develop or succeed strongly.","example":"Students thrive when challenge is balanced with useful support.","synonym":"flourish","antonym":"decline","application":"Useful in personal, social and biological contexts.","difficulty":2,"min_age":10,"max_age":20,"tags":["general"]},
    {"word":"Ubiquitous","pronunciation":"yoo-BIK-wi-tuhs","definition":"Present or found almost everywhere.","example":"Smartphones have become ubiquitous in modern life.","synonym":"widespread","antonym":"scarce","application":"A memorable word for describing widespread things.","difficulty":5,"min_age":15,"max_age":20,"tags":["general","writing"]},
    {"word":"Validate","pronunciation":"VAL-i-dayt","definition":"To confirm that something is accurate, acceptable or well supported.","example":"The team repeated the test to validate the result.","synonym":"confirm","antonym":"invalidate","application":"Useful in science, research and quality assurance.","difficulty":3,"min_age":12,"max_age":20,"tags":["academic","science"]},
    {"word":"Versatile","pronunciation":"VUR-suh-tile","definition":"Able to be used effectively in many different ways.","example":"Writing is a versatile skill that supports every subject.","synonym":"adaptable","antonym":"limited","application":"Useful for describing people, skills or tools.","difficulty":3,"min_age":12,"max_age":20,"tags":["general","communication"]},
    {"word":"Vigilant","pronunciation":"VIJ-uh-luhnt","definition":"Carefully watchful for possible problems or danger.","example":"A vigilant reader checks whether online information is trustworthy.","synonym":"alert","antonym":"careless","application":"Useful in digital literacy and safety contexts.","difficulty":3,"min_age":12,"max_age":20,"tags":["general","digital-literacy"]},
)


def age_from_dob(dob: object, on_date: date | None = None) -> int | None:
    if not dob:
        return None
    try:
        born = datetime.fromisoformat(str(dob)[:10]).date()
    except (TypeError, ValueError):
        return None
    today = on_date or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def stable_index(seed: str, length: int) -> int:
    if length <= 0:
        raise ValueError("A non-empty selection pool is required.")
    return int(sha256(seed.encode("utf-8")).hexdigest()[:16], 16) % length


def choose_word(rows: Iterable[Any], *, student_id: int, spark_date: str, age: int | None, seen_ids: set[int] | None = None) -> Any | None:
    seen_ids = seen_ids or set()
    all_rows = list(rows)
    eligible = []
    for row in all_rows:
        keys = row.keys() if hasattr(row, "keys") else row
        min_age = int(row["min_age"] or 0) if "min_age" in keys else 0
        max_age = int(row["max_age"] or 99) if "max_age" in keys else 99
        if age is not None and not (min_age <= age <= max_age):
            continue
        if int(row["id"]) in seen_ids:
            continue
        eligible.append(row)
    if not eligible:
        eligible = [r for r in all_rows if age is None or int(r["min_age"] or 0) <= age <= int(r["max_age"] or 99)] or all_rows
    if not eligible:
        return None
    eligible.sort(key=lambda r: (int(r["difficulty_rank"] or 0), str(r["word"]).casefold(), int(r["id"])))
    return eligible[stable_index(f"word|{student_id}|{spark_date}", len(eligible))]


def word_payload(row: Any) -> dict[str, Any]:
    return {
        "word": row["word"],
        "pronunciation": row["pronunciation"] or "",
        "definition": row["definition"],
        "example_sentence": row["example_sentence"],
        "synonym": row["synonym"] or "",
        "antonym": row["antonym"] or "",
        "exam_application": row["exam_application"] or "",
        "difficulty_rank": int(row["difficulty_rank"] or 0),
        "content_version": row["content_version"] or "1.0",
    }


def academic_payload(row: Any, *, reason: str) -> dict[str, Any]:
    raw_type = str(row["qtype"] or "").strip().lower().replace("-", "_").replace(" ", "_")
    free_response = raw_type in {"fill_blank", "fill_in_the_blank", "numerical", "numeric"}
    options = []
    if not free_response:
        for key, label in (("option_a", "A"), ("option_b", "B"), ("option_c", "C"), ("option_d", "D")):
            value = row[key] if key in row.keys() else ""
            if value:
                options.append({"value": label, "label": value})
        if raw_type in {"true/false", "true_false", "truefalse"} and not options:
            options = [{"value": "A", "label": "True"}, {"value": "B", "label": "False"}]
    return {
        "question_db_id": int(row["id"]),
        "question_id": row["question_id"] or "",
        "subject": row["subject"] or "",
        "chapter": row["chapter"] or "",
        "topic": row["topic"] or "",
        "level": row["level"] or "Foundation",
        "qtype": row["qtype"] or "MCQ",
        "prompt": row["question"],
        "options": options,
        "explanation": row["explanation"] or "",
        "selection_reason": reason,
        "content_version": str(row["version_no"] if "version_no" in row.keys() and row["version_no"] else "1"),
    }
