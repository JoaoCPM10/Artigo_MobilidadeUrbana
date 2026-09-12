"""
Analise de CONECTIVIDADE usando SOMENTE o que foi visto na disciplina:
percurso em grafos (BFS/DFS) e as definicoes formais de conexidade,
articulacao e ponte.

  * bfs / dfs                      -> percursos basicos (Percurso em Grafos).
  * connected_components           -> componentes do grafo nao-dirigido (BFS).
  * strongly_connected_components  -> pela DEFINICAO: dois vertices estao na
                                      mesma componente fortemente conexa se ha
                                      caminho dirigido de um para o outro e
                                      vice-versa. Calculado com BFS no grafo e
                                      no grafo reverso (sem algoritmo de Tarjan).
  * articulation_points            -> pela DEFINICAO: vertice cuja remocao
                                      desconecta o grafo (testado removendo o
                                      vertice e recontando componentes via BFS).
  * bridges                        -> pela DEFINICAO: aresta cuja remocao
                                      desconecta o grafo (idem).

As analises estruturais (componentes, articulacao, ponte) usam o grafo
NAO-DIRIGIDO (a rua existe fisicamente independente do sentido); ja a
conexidade forte usa o grafo dirigido (o sentido importa para o motorista).
"""

from __future__ import annotations
from collections import deque
from graph import Graph


# ---------------------------------------------------------------------------
# Percursos basicos (Percurso em Grafos)
# ---------------------------------------------------------------------------
def bfs(G: Graph, source: int, reverse: bool = False) -> set[int]:
    """Conjunto de vertices alcancaveis a partir de source (BFS dirigido).

    reverse=True percorre as arestas no sentido contrario (grafo reverso).
    """
    seen = {source}
    q = deque([source])
    while q:
        u = q.popleft()
        nbrs = (e.u for e in G.radj[u]) if reverse else (v for v, _ in G.neighbors(u))
        for w in nbrs:
            if w not in seen:
                seen.add(w)
                q.append(w)
    return seen


def dfs(G: Graph, source: int) -> list[int]:
    """DFS iterativo. Retorna a ordem de visita."""
    seen = {source}
    order = []
    stack = [source]
    while stack:
        u = stack.pop()
        order.append(u)
        for v, _ in G.neighbors(u):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return order


# ---------------------------------------------------------------------------
# Componentes do grafo nao-dirigido (a partir de uma lista de arestas fisicas)
# ---------------------------------------------------------------------------
def _undirected_adjacency(nodes, edges):
    adj = {u: [] for u in nodes}
    for (u, v) in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def _count_components(nodes, adj, skip_node=None, skip_edge=None) -> int:
    """Conta componentes conexas (BFS), podendo ignorar um no ou uma aresta."""
    seen = set()
    if skip_node is not None:
        seen.add(skip_node)
    n_comp = 0
    for s in nodes:
        if s in seen:
            continue
        n_comp += 1
        q = deque([s])
        seen.add(s)
        while q:
            u = q.popleft()
            for w in adj[u]:
                if w in seen:
                    continue
                if skip_edge is not None and {u, w} == skip_edge:
                    continue
                seen.add(w)
                q.append(w)
    return n_comp


def connected_components(nodes, edges) -> list[list[int]]:
    adj = _undirected_adjacency(nodes, edges)
    seen = set()
    comps = []
    for s in nodes:
        if s in seen:
            continue
        comp = []
        q = deque([s])
        seen.add(s)
        while q:
            u = q.popleft()
            comp.append(u)
            for w in adj[u]:
                if w not in seen:
                    seen.add(w)
                    q.append(w)
        comps.append(comp)
    return comps


# ---------------------------------------------------------------------------
# Componentes fortemente conexas pela DEFINICAO (BFS no grafo e no reverso)
# ---------------------------------------------------------------------------
def strongly_connected_components(G: Graph) -> list[list[int]]:
    remaining = set(G.nodes())
    sccs = []
    while remaining:
        s = next(iter(remaining))
        reach = bfs(G, s)                 # alcancaveis a partir de s
        reach_rev = bfs(G, s, reverse=True)  # que alcancam s
        comp = (reach & reach_rev) & remaining
        if s not in comp:
            comp = {s}
        sccs.append(list(comp))
        remaining -= comp
    return sccs


# ---------------------------------------------------------------------------
# Articulacoes e pontes pela DEFINICAO (remover e recontar componentes)
# ---------------------------------------------------------------------------
def articulation_points(nodes, edges) -> set[int]:
    adj = _undirected_adjacency(nodes, edges)
    base = _count_components(nodes, adj)
    aps = set()
    for v in nodes:
        # remover v deve ser comparado contra (base + 1): o proprio v vira
        # uma "componente" ausente. v e' articulacao se o resto se parte em
        # mais de uma componente.
        comps_without_v = _count_components([u for u in nodes if u != v],
                                            adj, skip_node=v)
        if comps_without_v > base:
            aps.add(v)
    return aps


def bridges(nodes, edges) -> list[tuple[int, int]]:
    adj = _undirected_adjacency(nodes, edges)
    base = _count_components(nodes, adj)
    # multiplicidade de cada par: se ha duas ruas ligando o mesmo par de
    # intersecoes, nenhuma delas e' ponte (remover uma mantem a outra).
    mult: dict[frozenset, int] = {}
    for (u, v) in edges:
        mult[frozenset((u, v))] = mult.get(frozenset((u, v)), 0) + 1
    result = []
    for (u, v) in edges:
        if mult[frozenset((u, v))] > 1:
            continue
        if _count_components(nodes, adj, skip_edge={u, v}) > base:
            result.append((u, v))
    return result
