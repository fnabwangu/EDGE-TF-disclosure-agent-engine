"""thesis_monitor.py
Real-time thesis drift monitor placeholder.
"""

def compute_drift(score_history):
    if not score_history:
        return 0.0
    return score_history[-1] - score_history[0]
