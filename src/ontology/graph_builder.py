"""graph_builder.py
Builds a NetworkX graph linking ETF -> security -> function
"""
import networkx as nx

def build_graph():
    G = nx.DiGraph()
    G.add_node("ETF-EX-001", type="etf")
    G.add_node("SEC-ABC", type="security")
    G.add_edge("ETF-EX-001", "SEC-ABC", weight=1.0)
    return G
