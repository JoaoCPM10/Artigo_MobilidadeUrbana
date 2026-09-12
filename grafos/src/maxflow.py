"""
GARGALOS via FLUXO MAXIMO / CORTE MINIMO (algoritmo de Edmonds-Karp).

Vistos em sala: Ford-Fulkerson e sua especializacao Edmonds-Karp (busca do
caminho aumentante por BFS), e o Teorema do Fluxo Maximo / Corte Minimo:

    "O valor maximo de um fluxo O-D e' igual a capacidade minima de um
     corte que separa a origem O do destino D."

Aplicacao a mobilidade urbana: atribuindo CAPACIDADE 1 a cada rua, o fluxo
maximo entre duas regioes e' o numero de ROTAS por ruas distintas (aresta-
disjuntas) entre elas, e o CORTE MINIMO e' o menor conjunto de ruas cuja
interdicao isola uma regiao da outra — ou seja, o gargalo da rede.

Implementacao: Edmonds-Karp em O(V * E^2).
"""

from __future__ import annotations
from collections import deque


def edmonds_karp(nodes, capacity, source, sink):
    """Fluxo maximo de source a sink.

    capacity: dict (u, v) -> capacidade (>0). Arestas nao listadas tem cap 0.
    Retorna (valor_do_fluxo, fluxo, reachable, cut_edges):
      - fluxo: dict (u,v) -> fluxo enviado.
      - reachable: conjunto S do corte minimo (lado da origem).
      - cut_edges: arestas (u,v) com u em S e v fora de S (o corte minimo).
    """
    # grafo residual: capacidade restante por arco
    res: dict[tuple[int, int], float] = {}
    adj: dict[int, set[int]] = {u: set() for u in nodes}
    for (u, v), c in capacity.items():
        res[(u, v)] = res.get((u, v), 0) + c
        res.setdefault((v, u), 0)        # arco reverso (residual)
        adj[u].add(v)
        adj[v].add(u)

    flow_value = 0.0
    while True:
        # BFS por um caminho aumentante (Edmonds-Karp)
        prev = {source: None}
        q = deque([source])
        while q:
            u = q.popleft()
            if u == sink:
                break
            for v in adj[u]:
                if v not in prev and res.get((u, v), 0) > 1e-9:
                    prev[v] = u
                    q.append(v)
        if sink not in prev:
            break  # sem caminho aumentante -> fluxo maximo atingido

        # gargalo do caminho encontrado
        path = []
        v = sink
        while v is not None:
            path.append(v)
            v = prev[v]
        path.reverse()
        bottleneck = min(res[(path[i], path[i + 1])]
                         for i in range(len(path) - 1))
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            res[(a, b)] -= bottleneck
            res[(b, a)] = res.get((b, a), 0) + bottleneck
        flow_value += bottleneck

    # lado da origem no corte minimo = alcancaveis na rede residual
    reachable = set()
    q = deque([source])
    reachable.add(source)
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in reachable and res.get((u, v), 0) > 1e-9:
                reachable.add(v)
                q.append(v)

    cut_edges = [(u, v) for (u, v), c in capacity.items()
                 if u in reachable and v not in reachable]

    # fluxo efetivo por arco (capacidade - residual)
    flow = {}
    for (u, v), c in capacity.items():
        f = c - res.get((u, v), 0)
        if f > 1e-9:
            flow[(u, v)] = f

    return flow_value, flow, reachable, cut_edges


def unit_capacity_network(undirected_edges):
    """Capacidade 1 por rua, nos dois sentidos (rede nao-dirigida).

    undirected_edges: lista de (u, v, ...) (extras ignorados).
    """
    cap = {}
    for e in undirected_edges:
        u, v = e[0], e[1]
        cap[(u, v)] = cap.get((u, v), 0) + 1
        cap[(v, u)] = cap.get((v, u), 0) + 1
    return cap
