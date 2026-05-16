import pytest
from pydantic import ValidationError

from agentic_ra.agents.base import _parse_report
from agentic_ra.api.schemas import ResearchRequest
from agentic_ra.contracts import Citation, Claim, ResearchReport

_CIT = {"index": 1, "title": "t", "url": "https://example.com", "snippet": "s"}


def test_request_strips_and_rejects_blank() -> None:
    assert ResearchRequest(question="  hello world  ").question == "hello world"
    with pytest.raises(ValidationError):
        ResearchRequest(question="   ")


def test_report_round_trips_through_json() -> None:
    report = ResearchReport(
        question="q",
        summary="s",
        claims=[Claim(text="c", citation_indices=[1])],
        citations=[Citation(**_CIT)],
    )
    restored = ResearchReport.model_validate_json(report.model_dump_json())
    assert restored == report


def test_dangling_citation_detection() -> None:
    report = ResearchReport(
        question="q",
        summary="s",
        claims=[Claim(text="c", citation_indices=[1, 3])],
        citations=[Citation(**_CIT)],
    )
    assert report.validate_citation_refs() == [3]


def test_citation_indices_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Claim(text="c", citation_indices=[0])


def test_citation_requires_snippet() -> None:
    with pytest.raises(ValidationError):
        Citation(index=1, title="t", url="https://example.com", snippet="")


def test_parse_report_rejects_dangling_refs() -> None:
    report, err = _parse_report(
        "q",
        {
            "summary": "s",
            "claims": [{"text": "c", "citation_indices": [2]}],
            "citations": [_CIT],
        },
    )
    assert report is None
    assert err is not None and "unknown citation" in err


def test_parse_report_accepts_valid() -> None:
    report, err = _parse_report(
        "q",
        {
            "summary": "s",
            "claims": [{"text": "c", "citation_indices": [1]}],
            "citations": [_CIT],
        },
    )
    assert err is None
    assert report is not None and report.question == "q"
