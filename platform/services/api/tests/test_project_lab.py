"""Stage 11 original project lab: real judge boundaries and explainable evidence."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.coding_arena import DockerRunner, JudgeUnavailable
from app.core import DemoEngine
from app.local_lab import LocalLab
from app.main import create_app
from app.project_lab import (PROJECTS, MILESTONE_COUNT, DEFENSE_COUNT,
                             ProjectLab, public_project)
from app.unified import UnifiedEvidence


class FakeDocker:
    """Deterministic CONTRACT double; actual Docker execution has separate live tests."""
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.calls = []

    def available(self, language):
        return self.enabled and language in ("java", "javascript", "python")

    def run(self, language, source, cases):
        if not self.enabled:
            raise JudgeUnavailable("Docker is not available")
        self.calls.append((language, source, len(cases)))
        status = "accepted" if source == "VALID ORIGINAL PROGRAM" else "wrong_answer"
        return [{"case": i + 1, "status": status} for i in range(len(cases))]


def setup():
    lab = LocalLab()
    unified = UnifiedEvidence(lab)
    fake = FakeDocker()
    unified.projects.runner = fake
    return lab, unified, fake


def test_catalog_is_original_curated_and_does_not_leak_hidden_cases_or_answers():
    lab, graph, _ = setup()
    cat = graph.projects.catalog(lab.profile()["role"])
    assert len(cat["projects"]) == 3
    assert cat["recommendation"]["project_id"] == "key-value-store"
    assert cat["source_index"] == "https://github.com/codecrafters-io/build-your-own-x"
    for pid in PROJECTS:
        doc = public_project(pid)
        assert doc["resources"] and all(x["via"].startswith("Build Your Own X") for x in doc["resources"])
        assert len(doc["milestones"]) == 2
        assert "cases" not in str(doc)
        assert all(len(x["public_examples"]) == 1 for x in doc["milestones"])
        assert all("correct" not in q and "explanation" not in q for q in doc["defense_questions"])
    assert MILESTONE_COUNT == DEFENSE_COUNT == 6


def test_role_changes_project_recommendation_without_fake_assessments():
    lab, graph, _ = setup()
    assert graph.projects.catalog("ml")["recommendation"]["project_id"] == "inverted-index"
    lab.update_profile("ml", "Python", 30)
    assert graph.projects.catalog(lab.profile()["role"])["recommendation"]["project_id"] == "inverted-index"
    assert graph.skillgraph()["event_count"] == 0


def test_second_milestone_cannot_skip_real_first_milestone():
    _, graph, fake = setup()
    with pytest.raises(ValueError, match="preceding milestone"):
        graph.projects.submit_milestone(
            "key-value-store", "mutations", "python", "VALID ORIGINAL PROGRAM"
        )
    assert not fake.calls
    assert graph.projects.milestone_evidence() == []


def test_pass_first_then_second_with_real_server_recorded_verdicts():
    _, graph, fake = setup()
    first = graph.projects.submit_milestone("key-value-store", "lookup", "python", "VALID ORIGINAL PROGRAM")
    assert first["all_passed"] and first["tests_passed"] == 3
    state = graph.projects.state("key-value-store")
    assert state["milestones"][0]["status"] == "passed"
    assert state["milestones"][1]["unlocked"]
    second = graph.projects.submit_milestone("key-value-store", "mutations", "java", "VALID ORIGINAL PROGRAM")
    assert second["all_passed"]
    assert graph.projects.state("key-value-store")["all_milestones_passed"]
    assert len(fake.calls) == 2


def test_wrong_submission_and_retry_do_not_rewrite_first_independent_evidence():
    _, graph, _ = setup()
    wrong = graph.projects.submit_milestone("inverted-index", "term-search", "python", "WRONG PROGRAM SOURCE")
    assert wrong["verdict"] == "wrong_answer"
    assert not graph.projects.state("inverted-index")["milestones"][0]["first_try_passed"]
    graph.projects.submit_milestone("inverted-index", "term-search", "python", "VALID ORIGINAL PROGRAM")
    state = graph.skillgraph()
    skill = next(s for s in state["skills"] if s["id"] == "project-build")
    assert skill["distinct_assessments"] == 1
    assert skill["first_try_correct_unassisted"] == 0
    assert state["sources"]["project_milestones"] == 2


def test_defense_locked_until_tested_code_and_rationale_is_not_ai_graded():
    _, graph, _ = setup()
    with pytest.raises(ValueError, match="Pass at least one"):
        graph.projects.defend("key-value-store", "overwrite", "b",
                              "Overwriting a key changes its value but not the number of keys.")
    graph.projects.submit_milestone("key-value-store", "lookup", "python", "VALID ORIGINAL PROGRAM")
    answer = graph.projects.defend("key-value-store", "overwrite", "b",
                                  "Overwriting a key changes its value but not the number of keys.")
    assert answer["correct"]
    assert answer["rationale_reviewed"] is False
    events = graph.evidence()["events"]
    kinds = {x["kind"] for x in events}
    assert "project_defense_choice" in kinds and "docker_project_milestone" in kinds
    question = next(s for s in graph.skillgraph()["skills"] if s["id"] == "project-defense")
    assert question["first_try_correct_unassisted"] == 1
    assert question["kind"] == "checked_design_choice"


def test_defense_wrong_answer_first_attempt_remains_wrong_after_retry():
    _, graph, _ = setup()
    graph.projects.submit_milestone("expression-interpreter", "left-to-right",
                                    "java", "VALID ORIGINAL PROGRAM")
    graph.projects.defend("expression-interpreter", "precedence", "a",
                          "I thought a simple left to right scan would be sufficient.")
    graph.projects.defend("expression-interpreter", "precedence", "b",
                          "Multiplication needs higher precedence to preserve arithmetic semantics.")
    skill = next(x for x in graph.skillgraph()["skills"] if x["id"] == "project-defense")
    assert skill["distinct_assessments"] == 1
    assert skill["first_try_correct_unassisted"] == 0
    assert graph.projects.state("expression-interpreter")["defense_questions"][0]["attempt_count"] == 2


def test_unreviewed_freeform_explanations_never_contribute_independent_grade():
    _, graph, _ = setup()
    graph.projects.submit_milestone("inverted-index", "term-search", "python", "VALID ORIGINAL PROGRAM")
    with pytest.raises(ValueError, match="20"):
        graph.projects.defend("inverted-index", "index-map", "a", "ok")
    graph.projects.defend("inverted-index", "index-map", "a",
                          "A term maps to the set of document IDs where it occurs.")
    evidence = graph.projects.defense_evidence()[0]
    assert evidence["rationale_reviewed"] is False
    assert evidence["correct"] is True
    for event in graph.evidence()["events"]:
        assert "rationale" not in event  # personal reasoning is not copied into the public graph


def test_artifact_links_are_user_reported_and_do_not_earn_a_project_grade():
    _, graph, _ = setup()
    for url in ["http://github.com/a/b", "https://github.com/a/b/issues/1",
                "https://evil.example/a/b", "https://github.com/a/b?x=1"]:
        with pytest.raises(ValueError):
            graph.projects.save_artifact("key-value-store", url, "My work")
    saved = graph.projects.save_artifact(
        "key-value-store", "https://github.com/example-user/learning-store", "My prototype"
    )
    assert saved["verification"] == "self-reported-link-not-reviewed"
    assert graph.projects.state("key-value-store")["artifact"]["url"].startswith("https://github.com")
    assert graph.skillgraph()["event_count"] == 0


def test_missing_docker_fails_explicitly_not_host_execution():
    _, graph, fake = setup()
    fake.enabled = False
    with pytest.raises(JudgeUnavailable):
        graph.projects.submit_milestone("key-value-store", "lookup", "python", "VALID ORIGINAL PROGRAM")
    assert graph.projects.milestone_evidence() == []


def test_all_dimensions_remain_separate():
    _, graph, _ = setup()
    assert len(graph.skillgraph()["skills"]) == 10
    graph.projects.submit_milestone("key-value-store", "lookup", "python", "VALID ORIGINAL PROGRAM")
    graph.projects.defend("key-value-store", "overwrite", "b",
                          "An overwrite preserves the set of keys and their cardinality.")
    skills = {x["id"]: x for x in graph.skillgraph()["skills"]}
    assert skills["project-build"]["distinct_assessments"] == 1
    assert skills["project-defense"]["distinct_assessments"] == 1
    assert skills["coding"]["distinct_assessments"] == 0
    assert skills["dsa"]["distinct_assessments"] == 0
    assert "No single percentage" in graph.skillgraph()["interpretation"]


def test_persistence_reset_and_progress_record(tmp_path):
    path = tmp_path / "lab.sqlite"
    first = LocalLab(path)
    graph = UnifiedEvidence(first)
    graph.projects.runner = FakeDocker()
    graph.projects.submit_milestone("key-value-store", "lookup", "python", "VALID ORIGINAL PROGRAM")
    graph.projects.save_artifact(
        "key-value-store", "https://github.com/example-user/learning-store", "Self-reported work"
    )
    reopened = UnifiedEvidence(LocalLab(path))
    assert reopened.projects.state("key-value-store")["progress"]["passed_milestones"] == 1
    assert reopened.projects.state("key-value-store")["artifact"] is not None
    reopened.clear()
    assert reopened.projects.state("key-value-store")["progress"]["passed_milestones"] == 0
    assert reopened.projects.state("key-value-store")["artifact"] is None


def test_api_catalog_and_skip_protection_without_docker():
    api = TestClient(create_app(DemoEngine(), local_lab=LocalLab()))
    c = api.get("/api/local/projects/catalog")
    assert c.status_code == 200
    assert len(c.json()["projects"]) == 3
    detail = api.get("/api/local/projects/key-value-store")
    assert detail.status_code == 200
    assert detail.json()["defense_unlocked"] is False
    skip = api.post("/api/local/projects/key-value-store/milestones/mutations/submit", json={
        "language": "python", "code": "VALID ORIGINAL PROGRAM"
    })
    assert skip.status_code == 422
    assert api.get("/api/local/projects/evidence/all").json()["milestones"] == []


def test_api_real_verified_evidence_workflow_with_injected_runner(monkeypatch):
    monkeypatch.setattr(DockerRunner, "available", lambda self, language: True)
    monkeypatch.setattr(DockerRunner, "run", lambda self, language, source, cases:
                        [{"case": i+1, "status": "accepted"} for i in range(len(cases))])
    api = TestClient(create_app(DemoEngine(), local_lab=LocalLab()))
    url = "/api/local/projects/key-value-store"
    submit = api.post(url + "/milestones/lookup/submit", json={
        "language": "javascript", "code": "VALID ORIGINAL PROGRAM"
    })
    assert submit.status_code == 200, submit.text
    assert submit.json()["result"]["source"] == "prepezy-docker-project-milestone"
    assert submit.json()["project"]["milestones"][1]["unlocked"]
    defense = api.post(url + "/defense/overwrite/submit", json={
        "choice_id": "b", "rationale": "Overwriting retains the original key and no new entry is created."
    })
    assert defense.status_code == 200
    assert defense.json()["result"]["rationale_reviewed"] is False
    evidence = api.get("/api/local/projects/evidence/all").json()
    assert len(evidence["milestones"]) == len(evidence["defense"]) == 1
    assert api.get("/api/local/skillgraph").json()["sources"]["project_milestones"] == 1
    assert api.get("/api/local/skillgraph").json()["sources"]["project_defense_choices"] == 1
    assert api.delete("/api/local/data").json()["cleared"]
    assert api.get("/api/local/projects/evidence/all").json()["milestones"] == []


def test_different_role_changes_planning_without_inventing_project_completions():
    lab, graph, _ = setup()
    before = graph.projects.catalog("backend")["recommendation"]
    assert before["project_id"] == "key-value-store"
    lab.update_profile("ml", "Python", 30)
    after = graph.projects.catalog(lab.profile()["role"])["recommendation"]
    assert after["project_id"] == "inverted-index"
    assert graph.projects.milestone_evidence() == []


def test_unknown_projects_are_not_accepted_or_faked():
    _, graph, _ = setup()
    with pytest.raises(ValueError):
        public_project("not-a-project")
    with pytest.raises(ValueError):
        graph.projects.submit_milestone("not-a-project", "lookup", "python", "VALID ORIGINAL PROGRAM")
    with pytest.raises(ValueError):
        graph.projects.defend("key-value-store", "not-a-question", "b",
                              "This explanation should not count toward evidence.")
