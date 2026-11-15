import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
import ui_adapter
from pipeline import CheckResult, Source


def _result(**kw):
    base = dict(
        verdict="Contradicted", headline="No: 20 hours in session.", explanation="Because.",
        sources=[Source(url="https://www.uscis.gov/x", title="USCIS page", quote="20 hours", date=None, scope="federal"),
                 Source(url="https://oiss.isp.msu.edu/y", title="MSU page", quote="fall and spring", date="2026-01-05", scope="school")],
        language="en", school="Michigan State University",
    )
    base.update(kw)
    return CheckResult(**base)


def test_english_answer_shape():
    ui = ui_adapter.to_ui(_result(), "msu")
    assert ui["pills"] == [{"label": "Contradicted", "text": "Contradicted", "kind": "contradicted"}]
    assert ui["headline"] == "No: 20 hours in session." and not ui["rtl"] and not ui["beta"]
    assert ui["show_ask_office"] is False
    assert ui["disclaimer"] == "Not legal advice. Confirm with MSU Office for International Students and Scholars (OISS)."


def test_missing_date_is_shown_as_not_shown_never_invented():
    ui = ui_adapter.to_ui(_result(), "msu")
    first, second = ui["sources"]
    assert first["date"] is None and first["date_text"] == "Date not shown"
    assert second["date"] == "2026-01-05" and second["date_text"] == "2026-01-05"


def test_source_categories_and_domains():
    ui = ui_adapter.to_ui(_result(), "msu")
    assert ui["sources"][0]["category"] == "U.S. Government" and ui["sources"][0]["domain"] == "www.uscis.gov"
    assert ui["sources"][1]["category"] == "Michigan State University"


def test_rule_status_adds_a_second_pill_and_na_does_not():
    assert len(ui_adapter.to_ui(_result(rule_status="In effect"), "msu")["pills"]) == 2
    assert len(ui_adapter.to_ui(_result(rule_status="Not applicable"), "msu")["pills"]) == 1
    assert ui_adapter.to_ui(_result(rule_status="Proposed only"), "msu")["pills"][1]["kind"] == "proposed"


def test_arabic_gets_localized_label_beside_english_rtl_and_beta():
    ui = ui_adapter.to_ui(_result(language="ar"), "msu")
    assert ui["pills"][0]["text"] == "يتعارض مع المصادر · Contradicted"
    assert ui["rtl"] is True and ui["beta"] is True
    assert ui["beta_text"] == "ترجمة تجريبية. لم يراجعها متحدث أصلي بعد."
    assert ui["sources"][0]["date_text"] == "التاريخ غير معروض"


def test_unclear_asks_the_office_and_keeps_the_english_question():
    r = _result(verdict="Unclear", question_for_office="What is the current OPT fee?", next_step="اسأل المكتب", language="ar")
    ui = ui_adapter.to_ui(r, "uchicago")
    assert ui["show_ask_office"] and ui["question_for_office"] == "What is the current OPT fee?"
    assert ui["office"]["url"] == "https://internationalaffairs.uchicago.edu"


def test_headline_falls_back_to_explanation():
    assert ui_adapter.to_ui(_result(headline=""), "msu")["headline"] == "Because."


def test_school_office_comes_from_sources_yaml_not_a_duplicate_table():
    cfg = pipeline.load_config()
    for key in cfg["schools"]:
        assert ui_adapter.office_for(key)["name"] == cfg["schools"][key]["office"]


def test_unknown_language_code_falls_back_to_english_strings():
    ui = ui_adapter.to_ui(_result(language="xx"), "msu")
    assert ui["sources"][0]["date_text"] == "Date not shown"
