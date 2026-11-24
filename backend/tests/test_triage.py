from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings
from app.schemas import TriageAnswerRequest
from app.services.triage import QUESTIONS, TriageService


def submit(
    service: TriageService,
    session_id: str,
    question_id: str,
    values: list[str],
    action: str = "next",
):
    response = service.answer(
        session_id,
        TriageAnswerRequest(
            question_id=question_id,
            values=values,
            action=action,
        ),
    )
    assert response is not None
    return response


def test_active_bleeding_ends_triage_with_emergency_outcome(demo_context):
    settings, _, context = demo_context
    service = TriageService(settings, context)
    session = service.start()

    response = submit(
        service,
        session.session_id,
        "symptoms",
        ["active_bleeding"],
    )

    assert response.status == "completed"
    assert response.outcome
    assert response.outcome.level == "emergency"
    assert response.question is None


def test_high_risk_condition_requires_professional_review(demo_context):
    settings, _, context = demo_context
    service = TriageService(settings, context)
    session = service.start()
    session_id = session.session_id

    response = submit(service, session_id, "symptoms", ["none"])
    response = submit(service, session_id, "conditions", ["fat_malabsorption"])
    response = submit(service, session_id, "medications", ["none"])
    response = submit(service, session_id, "special_population", ["none"])
    response = submit(service, session_id, "diet", ["normal"])
    response = submit(service, session_id, "labs", ["none"])
    response = submit(service, session_id, "supplement", ["none"])

    assert response.status == "completed"
    assert response.outcome
    assert response.outcome.level == "professional_review"
    assert "不能诊断" in response.outcome.cannot_conclude


def test_absence_of_reported_risk_is_not_a_no_supplement_conclusion(
    demo_context,
):
    settings, _, context = demo_context
    service = TriageService(settings, context)
    session = service.start()
    session_id = session.session_id

    response = submit(service, session_id, "symptoms", ["none"])
    response = submit(service, session_id, "conditions", ["none"])
    response = submit(service, session_id, "medications", ["none"])
    response = submit(service, session_id, "special_population", ["none"])
    response = submit(service, session_id, "diet", ["normal"])
    response = submit(service, session_id, "labs", ["none"])
    response = submit(service, session_id, "supplement", ["none"])

    assert response.outcome
    assert response.outcome.level == "insufficient_information"
    assert "不等于没有维生素K缺乏" in response.outcome.summary
    assert "您不需要补充" not in response.outcome.summary


def test_unsure_answer_escalates_to_professional_review(demo_context):
    settings, _, context = demo_context
    service = TriageService(settings, context)
    session = service.start()
    session_id = session.session_id

    response = submit(service, session_id, "symptoms", ["none"])
    response = submit(service, session_id, "conditions", ["unsure"])
    response = submit(service, session_id, "medications", ["none"])
    response = submit(service, session_id, "special_population", ["none"])
    response = submit(service, session_id, "diet", ["normal"])
    response = submit(service, session_id, "labs", ["none"])
    response = submit(service, session_id, "supplement", ["none"])

    assert response.outcome
    assert response.outcome.level == "professional_review"


def test_triage_back_returns_to_previous_question(demo_context):
    settings, _, context = demo_context
    service = TriageService(settings, context)
    session = service.start()

    response = submit(service, session.session_id, "symptoms", ["none"])
    assert response.question
    assert response.question.id == QUESTIONS[1].id

    response = submit(
        service,
        session.session_id,
        response.question.id,
        [],
        action="back",
    )

    assert response.question
    assert response.question.id == QUESTIONS[0].id


def test_triage_api_stops_immediately_for_emergency(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path / "data", _env_file=None)
    settings.ensure_dirs()
    monkeypatch.setattr(main_module, "settings", settings)

    with TestClient(main_module.app) as client:
        started = client.post("/api/v1/triage/sessions")
        session_id = started.json()["session_id"]
        answered = client.post(
            f"/api/v1/triage/sessions/{session_id}/answer",
            json={
                "question_id": "symptoms",
                "values": ["black_stool"],
                "action": "next",
            },
        )

    assert started.status_code == 200
    assert answered.status_code == 200
    assert answered.json()["status"] == "completed"
    assert answered.json()["outcome"]["level"] == "emergency"
    assert answered.json()["question"] is None
