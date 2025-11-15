from backend_v2_withEncryption_withRoles import ml_engine


def test_predict_risk_bounds():
    assert 0.0 <= ml_engine.predict_risk(100, 100) <= 1.0
    assert 0.0 <= ml_engine.predict_risk(0, 0) <= 1.0
    assert ml_engine.predict_risk(100, 100) == 0.0
    assert ml_engine.predict_risk(0, 0) == 1.0


def test_rebuild_version_increment():
    prev = int(ml_engine.get_model_version())
    new = int(ml_engine.rebuild_model())
    assert new == prev + 1
