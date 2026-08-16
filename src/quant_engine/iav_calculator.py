"""iav_calculator.py
Standardized composite IAV scoring placeholder.
"""

def compute_iav(scores):
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
