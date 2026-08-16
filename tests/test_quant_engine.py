from src.quant_engine.flow_decomposition import compute_u_f_i_t


def test_compute_u_f_i_t_normalizes():
    flows = [1, 1, 2]
    out = compute_u_f_i_t(flows)
    assert abs(sum(out) - 1.0) < 1e-9
