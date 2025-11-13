# backend/ml_engine.py
"""
Simple deterministic risk engine with a version counter.
We keep this simple and explainable for the demo:
 - predict_risk(marks, attendance) => 0..1 (higher => more risky)
 - get_model_version() returns a simple integer string
 - rebuild_model() toggles internal version (simulated retrain)
"""
import math
import threading

_model_version_lock = threading.Lock()
_model_version = 1

def predict_risk(marks, attendance):
    try:
        marks = float(marks)
    except Exception:
        marks = 0.0
    try:
        attendance = float(attendance)
    except Exception:
        attendance = 0.0

    # clamp inputs
    marks = max(0.0, min(100.0, marks))
    attendance = max(0.0, min(100.0, attendance))

    marks_norm = marks / 100.0
    attend_norm = attendance / 100.0

    # Weighted performance score
    performance_score = (0.6 * marks_norm) + (0.4 * attend_norm)
    risk = 1.0 - performance_score
    risk = max(0.0, min(1.0, risk))
    return round(risk, 3)

def get_model_version():
    global _model_version
    return str(_model_version)

def rebuild_model():
    """
    Simulate rebuilding: increment version counter.
    In real system this would retrain and save a model file.
    """
    global _model_version
    with _model_version_lock:
        _model_version += 1
    return str(_model_version)
