"""
Caminhos minimos e ROTAS ALTERNATIVAS usando apenas algoritmos da disciplina.

  * dijkstra        -> caminho minimo (heap binario), O((V+E) log V).
  * bellman_ford    -> caminho minimo, O(V*E); usado como verificacao
                       independente (ambos foram vistos em sala).
  * shortest_path   -> reconstroi o caminho e seu custo.
  * alternative_route -> ROTA ALTERNATIVA: recalcula o caminho minimo com
                       Dijkstra apos remover um trecho (rua bloqueada/em obra),
                       sem usar k-shortest paths.

O peso das arestas e' o tempo de viagem (segundos).
"""

from __future__ import annotations
import heapq
import math
from graph import Graph


def dijkstra(G: Graph, source: int, target: int | None = None,
             blocked_edges: set[tuple[int, int]] | None = None,
             blocked_nodes: set[int] | None = None):
    """Dijkstra com heap binario. Retorna (dist, prev)."""
    blocked_edges = blocked_edges or set()
    blocked_nodes = blocked_nodes or set()
    dist = {source: 0.0}
    prev: dict[int, int] = {}
    pq = [(0.0, source)]
    visited: set[int] = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if target is not None and u == target:
            break
        for v, e in G.neighbors(u):
            if v in blocked_nodes or (u, v) in blocked_edges:
                continue
            nd = d + e.weight
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def bellman_ford(G: Graph, source: int):
    """Bellman-Ford. Retorna (dist, prev). O(V*E).

    Serve de verificacao independente do Dijkstra (mesmos resultados, pois
    nao ha pesos negativos numa malha viaria).
    """
    dist = {u: math.inf for u in G.nodes()}
    prev: dict[int, int] = {}
    dist[source] = 0.0
    for _ in range(G.n - 1):
        changed = False
        for e in G.edges:
            if dist[e.u] + e.weight < dist[e.v]:
                dist[e.v] = dist[e.u] + e.weight
                prev[e.v] = e.u
                changed = True
        if not changed:
            break
    return dist, prev


def _reconstruct(prev, source, target):
    if target != source and target not in prev:
        return None
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def shortest_path(G: Graph, source: int, target: int,
                  blocked_edges=None, blocked_nodes=None):
    """Retorna (path, custo_em_segundos) ou (None, inf)."""
    dist, prev = dijkstra(G, source, target, blocked_edges, blocked_nodes)
    if target not in dist:
        return None, math.inf
    return _reconstruct(prev, source, target), dist[target]


def alternative_route(G: Graph, source: int, target: int,
                      avoid_edges: set[tuple[int, int]]):
    """Melhor rota evitando os trechos indicados (rua bloqueada)."""
    return shortest_path(G, source, target, blocked_edges=avoid_edges)


def edges_of_path(path):
    """Arcos dirigidos (u,v) usados por um caminho."""
    if not path:
        return set()
    return {(u, v) for u, v in zip(path, path[1:])}
