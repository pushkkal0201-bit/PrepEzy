from app.core import DemoEngine


def test_questions_do_not_expose_answers():
    assert all("answer" not in question and "explanation" not in question for question in DemoEngine.public_questions())


def test_initial_recommendations_depend_on_goal():
    engine = DemoEngine()
    assert engine.snapshot("demo-backend")["recommendation"]["skill"] == "dsa"
    assert engine.snapshot("demo-ml")["recommendation"]["skill"] == "ml"


def test_server_scores_and_updates_model():
    engine = DemoEngine()
    result = engine.submit("demo-backend", "dsa-1", "a")
    assert result["correct"] is False
    assert result["learner"]["recommendation"]["skill"] == "dsa"
    assert result["learner"]["competencies"][0]["attempts"] == 1


def test_correct_answer_is_scored_by_server():
    result = DemoEngine().submit("demo-ml", "ml-1", "c")
    assert result["correct"] is True


def test_separate_demo_learners():
    engine = DemoEngine()
    engine.submit("demo-backend", "sql-1", "a")
    assert engine.snapshot("demo-backend")["total_attempts"] == 1
    assert engine.snapshot("demo-ml")["total_attempts"] == 0


def test_sqlite_persistence(tmp_path):
    path = tmp_path / "demo.sqlite"
    DemoEngine(path).submit("demo-backend", "sql-1", "b")
    assert DemoEngine(path).snapshot("demo-backend")["total_attempts"] == 1


def test_invalid_inputs_rejected_without_recording():
    engine = DemoEngine()
    for user, question, choice in [("unknown", "sql-1", "b"), ("demo-ml", "unknown", "b"), ("demo-ml", "sql-1", "unknown")]:
        try:
            engine.submit(user, question, choice)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid input was accepted")
    assert engine.snapshot("demo-ml")["total_attempts"] == 0
