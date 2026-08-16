from src.governance.deterministic_gates import ev_gate


def test_ev_gate():
    assert ev_gate(0.8, 0.7)
    assert not ev_gate(0.5, 0.7)
