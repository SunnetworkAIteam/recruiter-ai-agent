from types import SimpleNamespace

import anthropic
import pytest

from app.core.exceptions import ClaudeAPIError
from app.services import claude_service


def _fake_message(text: str, input_tokens=100, output_tokens=50):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


VALID_RESPONSE_JSON = """{
  "tech_score": 85,
  "communication_score": 78,
  "role_match_score": 90,
  "summary": "Strong backend engineer with relevant experience.",
  "strengths": "Deep Python and distributed systems background.",
  "concerns": ""
}"""


class TestScoreResume:
    def test_parses_valid_response_successfully(self, mocker):
        mocker.patch.object(
            claude_service._client.messages, "create", return_value=_fake_message(VALID_RESPONSE_JSON)
        )
        result = claude_service.score_resume(
            resume_text="Experienced Python engineer, 5 years, FastAPI, distributed systems.",
            job_title="Senior Backend Engineer",
            job_description="Build scalable APIs",
            required_skills="Python, FastAPI, PostgreSQL",
            min_years_experience=3,
            candidate_id="cand-123",
        )
        assert result.tech_score == 85
        assert result.communication_score == 78
        assert result.role_match_score == 90
        assert "backend engineer" in result.summary.lower()

    def test_handles_markdown_fenced_json(self, mocker):
        fenced = f"```json\n{VALID_RESPONSE_JSON}\n```"
        mocker.patch.object(claude_service._client.messages, "create", return_value=_fake_message(fenced))
        result = claude_service.score_resume(
            resume_text="Some resume text here that is long enough.",
            job_title="Engineer",
            job_description="desc",
            required_skills="Python",
            min_years_experience=1,
            candidate_id="cand-124",
        )
        assert result.tech_score == 85

    def test_clamps_out_of_range_scores(self, mocker):
        out_of_range = VALID_RESPONSE_JSON.replace('"tech_score": 85', '"tech_score": 150')
        mocker.patch.object(
            claude_service._client.messages, "create", return_value=_fake_message(out_of_range)
        )
        result = claude_service.score_resume(
            resume_text="resume text",
            job_title="Engineer",
            job_description="desc",
            required_skills="Python",
            min_years_experience=1,
            candidate_id="cand-125",
        )
        assert result.tech_score == 100  # clamped, not 150

    def test_raises_on_malformed_json(self, mocker):
        mocker.patch.object(
            claude_service._client.messages,
            "create",
            return_value=_fake_message("I refuse to output JSON today, sorry!"),
        )
        with pytest.raises(ClaudeAPIError):
            claude_service.score_resume(
                resume_text="resume text",
                job_title="Engineer",
                job_description="desc",
                required_skills="Python",
                min_years_experience=1,
                candidate_id="cand-126",
            )

    def test_raises_on_missing_required_field(self, mocker):
        incomplete = '{"tech_score": 80, "summary": "ok"}'
        mocker.patch.object(claude_service._client.messages, "create", return_value=_fake_message(incomplete))
        with pytest.raises(ClaudeAPIError, match="missing required fields"):
            claude_service.score_resume(
                resume_text="resume text",
                job_title="Engineer",
                job_description="desc",
                required_skills="Python",
                min_years_experience=1,
                candidate_id="cand-127",
            )

    def test_wraps_api_error_after_retries_exhausted(self, mocker):
        mocker.patch.object(
            claude_service._client.messages,
            "create",
            side_effect=anthropic.APIConnectionError(request=mocker.Mock()),
        )
        with pytest.raises(ClaudeAPIError, match="temporarily unavailable"):
            claude_service.score_resume(
                resume_text="resume text",
                job_title="Engineer",
                job_description="desc",
                required_skills="Python",
                min_years_experience=1,
                candidate_id="cand-128",
            )

    def test_confidence_field_present_and_clamped(self, mocker):
        response_with_confidence = VALID_RESPONSE_JSON.replace(
            '"summary"', '"confidence": 150, "summary"'
        )
        mocker.patch.object(
            claude_service._client.messages, "create", return_value=_fake_message(response_with_confidence)
        )
        result = claude_service.score_resume(
            resume_text="resume text long enough to pass validation checks here",
            job_title="Engineer",
            job_description="desc",
            required_skills="Python",
            min_years_experience=1,
            candidate_id="cand-129",
        )
        assert result.confidence == 100  # clamped from 150

    def test_confidence_defaults_when_model_omits_it(self, mocker):
        mocker.patch.object(
            claude_service._client.messages, "create", return_value=_fake_message(VALID_RESPONSE_JSON)
        )
        result = claude_service.score_resume(
            resume_text="resume text long enough to pass validation checks here",
            job_title="Engineer",
            job_description="desc",
            required_skills="Python",
            min_years_experience=1,
            candidate_id="cand-130",
        )
        assert result.confidence == 70  # documented default when model omits the field

    def test_prompt_injection_defense_present_in_system_prompt(self):
        # Regression guard: if someone "simplifies" the system prompt later,
        # this test fails loudly instead of silently reopening the
        # injection vector described in the module docstring.
        assert "untrusted data" in claude_service.SCORING_SYSTEM_PROMPT
        assert "<resume_text>" in claude_service.SCORING_SYSTEM_PROMPT
