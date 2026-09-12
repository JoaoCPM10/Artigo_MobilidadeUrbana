"""
Estrutura de dados de grafo para redes de ruas urbanas.

Modelamos a malha viária como um grafo DIRECIONADO e PONDERADO:
  - Vertices  -> cruzamentos (intersecoes), com coordenadas (x, y).
  - Arestas   -> trechos de rua (quadras), com:
        * length      : comprimento geometrico do trecho (metros).
        * travel_time : tempo de travessia (s), = length / velocidade.
        * oneway      : True se a rua e' de mao unica.

Ruas de mao dupla sao representadas por duas arestas direcionadas (u->v e v->u).
Ruas de mao unica por uma unica aresta. Isso permite estudar conectividade
forte (alcancabilidade real de carro), algo impossivel num grafo nao-dirigido.

Tudo e' implementado sem bibliotecas de grafos (apenas a biblioteca padrao),
pois o objetivo do trabalho e' exercitar os algoritmos diretamente.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math


@dataclass
class Edge:
    u: int
    v: int
    length: float          # metros
    travel_time: float     # segundos
    oneway: bool = False

    @property
    def weight(self) -> float:
        # Peso padrao usado nos caminhos minimos = tempo de viagem.
        return self.travel_time


class Graph:
    """Grafo direcionado ponderado com lista de adjacencia."""

    def __init__(self) -> None:
        self.coords: dict[int, tuple[float, float]] = {}
        self.adj: dict[int, list[Edge]] = {}     # u -> arestas de saida
        self.radj: dict[int, list[Edge]] = {}    # u -> arestas de entrada (grafo reverso)
        self.edges: list[Edge] = []

    # ---- construcao -------------------------------------------------------
    def add_node(self, node_id: int, x: float, y: float) -> None:
        if node_id not in self.coords:
            self.coords[node_id] = (x, y)
            self.adj[node_id] = []
            self.radj[node_id] = []

    def _add_directed(self, u: int, v: int, length: float,
                      travel_time: float, oneway: bool) -> None:
        e = Edge(u, v, length, travel_time, oneway)
        self.adj[u].append(e)
        self.radj[v].append(e)
        self.edges.append(e)

    def add_street(self, u: int, v: int, *, speed_kmh: float = 40.0,
                   oneway: bool = False) -> None:
        """Adiciona um trecho de rua entre os cruzamentos u e v.

        Se oneway=False cria as duas arestas direcionadas (mao dupla).
        """
        (x1, y1), (x2, y2) = self.coords[u], self.coords[v]
        length = math.hypot(x2 - x1, y2 - y1)
        travel_time = length / (speed_kmh * 1000.0 / 3600.0)  # s = m / (m/s)
        self._add_directed(u, v, length, travel_time, oneway)
        if not oneway:
            self._add_directed(v, u, length, travel_time, oneway)

    def add_directed_explicit(self, u: int, v: int, length: float,
                              travel_time: float) -> None:
        """Adiciona um unico arco u->v com comprimento e tempo ja calculados.

        Usado pelo carregador OSM apos a simplificacao da topologia.
        """
        self._add_directed(u, v, length, travel_time, oneway=True)

    # ---- consultas --------------------------------------------------------
    @property
    def n(self) -> int:
        return len(self.coords)

    @property
    def m(self) -> int:
        return len(self.edges)

    def nodes(self) -> list[int]:
        return list(self.coords.keys())

    def neighbors(self, u: int):
        """Itera sobre (vizinho, aresta) das arestas de saida de u."""
        for e in self.adj[u]:
            yield e.v, e

    def out_degree(self, u: int) -> int:
        return len(self.adj[u])

    def in_degree(self, u: int) -> int:
        return len(self.radj[u])

    # ---- versao nao-dirigida (para pontes / articulacao / conectividade) --
    def undirected_adj(self) -> dict[int, set[int]]:
        """Retorna a adjacencia tratando o grafo como nao-dirigido.

        Util para analise estrutural (pontes, pontos de articulacao),
        onde interessa a existencia fisica do trecho, nao o sentido.
        """
        ua: dict[int, set[int]] = {u: set() for u in self.coords}
        for e in self.edges:
            ua[e.u].add(e.v)
            ua[e.v].add(e.u)
        return ua

    def undirected_edges(self) -> list[tuple[int, int]]:
        seen: set[tuple[int, int]] = set()
        result: list[tuple[int, int]] = []
        for e in self.edges:
            key = (min(e.u, e.v), max(e.u, e.v))
            if key not in seen:
                seen.add(key)
                result.append(key)
        return result
