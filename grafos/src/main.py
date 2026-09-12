"""
Pipeline principal — Tema 5: Grafos em mobilidade urbana
Estudo de caso: bairro da URCA (Rio de Janeiro), dados reais do OpenStreetMap.

Usa SOMENTE algoritmos vistos na disciplina:
  (A) CONECTIVIDADE      -> BFS/DFS; componentes; fortemente conexo (BFS no
                            grafo e no reverso); articulacoes e pontes pela
                            definicao.
  (B) ROTAS ALTERNATIVAS -> Dijkstra (e Bellman-Ford como verificacao);
                            rota alternativa recalculada ao bloquear um trecho.
  (C) GARGALOS           -> estruturais (pontes/articulacoes, fracos e
                            fortes) e por fluxo maximo / corte minimo
                            (Edmonds-Karp).

Gera figuras (output/) e metricas (output/metrics.json).

Uso:  py main.py
"""

from __future__ import annotations
import json
import math
import os
import random
import time

from graph import Graph
from osm_loader import load_neighborhood
import connectivity as cc
import shortest_paths as sp
import maxflow as mf
import visualize as viz

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUT, exist_ok=True)

# Bairro da Urca, RJ (bounding box S,W,N,E)
NEIGHBORHOOD = "urca"
BBOX = "-22.958,-43.171,-22.943,-43.155"


def banner(t):
    print("\n" + "=" * 64 + f"\n {t}\n" + "=" * 64)


# ---------------------------------------------------------------------------
# Copias do grafo com uma aresta ou um vertice removido, para testar pontes e
# articulacoes FORTES (conexidade dirigida) restritas ao nucleo. Usa somente
# a estrutura Graph existente (sem bibliotecas de grafos), copiando os
# atributos ja calculados de cada arco (length, travel_time) em vez de
# recalcula-los a partir das coordenadas.
# ---------------------------------------------------------------------------
def _copia_sem_aresta(G: Graph, u: int, v: int) -> Graph:
    H = Graph()
    for nid, (x, y) in G.coords.items():
        H.add_node(nid, x, y)
    par = {u, v}
    for e in G.edges:
        if {e.u, e.v} == par:
            continue
        H._add_directed(e.u, e.v, e.length, e.travel_time, e.oneway)
    return H


def _copia_sem_no(G: Graph, w: int) -> Graph:
    H = Graph()
    for nid, (x, y) in G.coords.items():
        if nid != w:
            H.add_node(nid, x, y)
    for e in G.edges:
        if e.u == w or e.v == w:
            continue
        H._add_directed(e.u, e.v, e.length, e.travel_time, e.oneway)
    return H


def _nucleo_intacto(H: Graph, alvo: set[int]) -> bool:
    """Os vertices de `alvo` (o nucleo original, menos o removido se for o
    caso) ainda formam uma unica componente fortemente conexa em H?"""
    for comp in cc.strongly_connected_components(H):
        if alvo <= set(comp):
            return True
    return False


def main():
    t0_all = time.perf_counter()
    metrics = {}

    # ----------------------------------------------------------- carrega mapa
    data = load_neighborhood(NEIGHBORHOOD, BBOX)
    G = data["graph"]
    edges_u = [(u, v) for (u, v, _, _) in data["undirected_edges"]]
    nodes = G.nodes()
    banner("REDE DE RUAS — URCA (RJ), OpenStreetMap")
    print(f"Pontos OSM brutos: {data['n_raw_nodes']} | vias OSM: {data['n_ways']}")
    print(f"Apos simplificacao: {G.n} intersecoes (V), {G.m} arcos (E), "
          f"{len(edges_u)} trechos de rua")
    metrics["rede"] = {
        "fonte": "OpenStreetMap (Overpass API)",
        "bairro": "Urca, Rio de Janeiro",
        "bbox": BBOX,
        "pontos_osm": data["n_raw_nodes"],
        "vias_osm": data["n_ways"],
        "V_intersecoes": G.n,
        "E_arcos": G.m,
        "trechos": len(edges_u),
    }
    viz.fig_overview(data, os.path.join(OUT, "01_urca.png"))

    # --------------------------------------------------------- conectividade
    banner("(A) CONECTIVIDADE")
    t0 = time.perf_counter()
    comps = cc.connected_components(nodes, edges_u)
    scc = cc.strongly_connected_components(G)
    t_conn = time.perf_counter() - t0
    comp_sizes = sorted((len(c) for c in comps), reverse=True)
    scc_sizes = sorted((len(c) for c in scc), reverse=True)
    deg = {u: 0 for u in nodes}
    for (u, v) in edges_u:
        deg[u] += 1; deg[v] += 1
    dead_ends = [u for u in nodes if deg[u] == 1]
    n_nao_triviais = sum(1 for c in scc if len(c) > 1)
    print(f"Componentes (nao-dirigido): {len(comps)} (maior = {comp_sizes[0]})")
    print(f"Componentes fortemente conexas: {len(scc)} (maior = {scc_sizes[0]})")
    print(f"Intersecoes fora da CFC gigante: {G.n - scc_sizes[0]} "
          f"(efeito das mãos únicas)")
    print(f"Ruas sem saida (cul-de-sac, grau 1): {len(dead_ends)}")
    print(f"Tempo: {t_conn*1000:.1f} ms")
    metrics["conectividade"] = {
        "componentes": len(comps),
        "maior_componente": comp_sizes[0],
        "scc": len(scc),
        "maior_scc": scc_sizes[0],
        "fora_da_scc_gigante": G.n - scc_sizes[0],
        "ruas_sem_saida": len(dead_ends),
        "tempo_ms": round(t_conn * 1000, 2),
    }
    viz.fig_scc(data, scc, os.path.join(OUT, "02_scc.png"))

    # nucleo fortemente conexo gigante -- usado no restante do pipeline
    giant = max(scc, key=len)
    gset = set(giant)
    gl = list(giant)

    # ---------------------------------------------- gargalos estruturais
    banner("(C.1) GARGALOS ESTRUTURAIS: pontes e articulacoes (definicao)")
    t0 = time.perf_counter()
    aps = cc.articulation_points(nodes, edges_u)
    brs = cc.bridges(nodes, edges_u)
    t_struct = time.perf_counter() - t0
    print(f"Pontos de articulacao: {len(aps)} de {G.n} intersecoes")
    print(f"Pontes (cut-edges): {len(brs)} de {len(edges_u)} trechos")
    print(f"Tempo: {t_struct*1000:.1f} ms")
    metrics["gargalos_estruturais"] = {
        "articulacoes": len(aps),
        "pontes": len(brs),
        "tempo_ms": round(t_struct * 1000, 2),
    }
    viz.fig_critical(data, brs, aps, os.path.join(OUT, "03_criticos.png"))

    # ------------------------------------- gargalos estruturais DIRIGIDOS
    banner("(C.1.5) GARGALOS ESTRUTURAIS DIRIGIDOS: pontes/articulacoes "
           "FORTES restritas ao nucleo")
    t0 = time.perf_counter()
    weak_edge_pairs = {frozenset(e) for e in brs}
    aps_set = set(aps)

    # pares de nos unicos dentro do nucleo (uma rua com trechos paralelos
    # entre o mesmo par de intersecoes conta como UMA rua para efeito de
    # fechamento: fechar a rua fecha os dois trechos ao mesmo tempo).
    pares_nucleo = []
    vistos = set()
    for (u, v) in edges_u:
        if u in gset and v in gset:
            k = frozenset((u, v))
            if k not in vistos:
                vistos.add(k)
                pares_nucleo.append((u, v))

    core_breaking_edges = []
    for (u, v) in pares_nucleo:
        H = _copia_sem_aresta(G, u, v)
        if not _nucleo_intacto(H, gset):
            core_breaking_edges.append((u, v))

    core_breaking_nodes = []
    for u in gset:
        H = _copia_sem_no(G, u)
        if not _nucleo_intacto(H, gset - {u}):
            core_breaking_nodes.append(u)
    t_forte = time.perf_counter() - t0

    edges_both = [e for e in core_breaking_edges if frozenset(e) in weak_edge_pairs]
    edges_strong_only = [e for e in core_breaking_edges if frozenset(e) not in weak_edge_pairs]
    core_pairs_set = {frozenset(e) for e in core_breaking_edges}
    edges_weak_only = [e for e in brs if frozenset(e) not in core_pairs_set]

    nodes_both = [n for n in core_breaking_nodes if n in aps_set]
    nodes_strong_only = [n for n in core_breaking_nodes if n not in aps_set]

    print(f"Nucleo fortemente conexo: {len(gset)} intersecoes")
    print(f"Pontes fortes (fragmentam o nucleo): {len(core_breaking_edges)} "
          f"de {len(pares_nucleo)} pares de rua do nucleo")
    print(f"Articulacoes fortes (fragmentam o nucleo): {len(core_breaking_nodes)} "
          f"de {len(gset)} intersecoes do nucleo")
    print(f"  cruzamento pontes:       fraca+forte={len(edges_both)}  "
          f"so forte={len(edges_strong_only)}  so fraca={len(edges_weak_only)}")
    print(f"  cruzamento articulacoes: fraca+forte={len(nodes_both)}  "
          f"so forte={len(nodes_strong_only)}")
    print(f"Tempo: {t_forte*1000:.1f} ms")
    metrics["gargalos_estruturais_dirigidos"] = {
        "nucleo_n": len(gset),
        "pontes_fortes": len(core_breaking_edges),
        "articulacoes_fortes": len(core_breaking_nodes),
        "pontes_fraca_e_forte": len(edges_both),
        "pontes_so_forte": len(edges_strong_only),
        "pontes_so_fraca_fora_do_nucleo": len(edges_weak_only),
        "articulacoes_fraca_e_forte": len(nodes_both),
        "articulacoes_so_forte": len(nodes_strong_only),
        "tempo_ms": round(t_forte * 1000, 2),
    }
    viz.fig_strong_gargalos(data, gl, edges_both, edges_strong_only,
                             edges_weak_only, nodes_both, nodes_strong_only,
                             os.path.join(OUT, "07_gargalos_dirigidos_categorizado.png"))

    # ---- escolhe origem (O) e destino (D) extremos da peninsula -----------
    # O = interseccao mais ao norte/leste (grade residencial)
    # D = interseccao mais ao sul/oeste (saida em direcao a cidade)
    # nós bem conectados (grau >= 3) da CFC gigante, para que O e D nao sejam
    # cul-de-sacs locais e o corte minimo reflita o "pescoço" do bairro.
    inner = [u for u in gset if deg[u] >= 3] or list(gset)
    O = max(inner, key=lambda u: G.coords[u][0] + G.coords[u][1])
    D = min(inner, key=lambda u: G.coords[u][0] + G.coords[u][1])

    # ---------------------------------------------- gargalo por fluxo/corte
    banner("(C.2) GARGALOS POR FLUXO MAXIMO / CORTE MINIMO (Edmonds-Karp)")
    cap = mf.unit_capacity_network(data["undirected_edges"])
    t0 = time.perf_counter()
    fmax, flow, reach, cut = mf.edmonds_karp(nodes, cap, O, D)
    t_flow = time.perf_counter() - t0
    print(f"Origem O={O}  Destino D={D}")
    print(f"Fluxo maximo (rotas por ruas distintas): {int(fmax)}")
    print(f"Corte minimo (ruas que isolam O de D): {len(cut)}")
    print(f"  -> {cut}")
    print(f"Tempo Edmonds-Karp: {t_flow*1000:.1f} ms")

    # a rota fisica de O a D pode ter, alem do corte relatado pelo Edmonds-
    # Karp, outros trechos que, isoladamente, tambem sao corte de valor 1
    # (pontos unicos de falha em serie na mesma rota; ver Secao 4.4).
    rota_od, _ = sp.shortest_path(G, O, D)
    rota_arestas = list(zip(rota_od, rota_od[1:])) if rota_od else []
    adj_und = cc._undirected_adjacency(nodes, edges_u)
    reportado = {frozenset(e) for e in cut}
    alt_cut_edges = []
    for (u, v) in rota_arestas:
        if frozenset((u, v)) in reportado:
            continue
        comps_sem = cc._count_components(nodes, adj_und, skip_edge={u, v})
        comps_base = cc._count_components(nodes, adj_und)
        if comps_sem > comps_base:
            # confirma que O e D ficam em componentes diferentes sem essa rua
            seen = {O}
            stack = [O]
            while stack:
                x = stack.pop()
                for w in adj_und[x]:
                    if w in seen or frozenset((x, w)) == frozenset((u, v)):
                        continue
                    seen.add(w); stack.append(w)
            if D not in seen:
                alt_cut_edges.append((u, v))
    print(f"Rota fisica O->D: {len(rota_arestas)} rua(s); outros pontos "
          f"unicos de falha na mesma rota: {alt_cut_edges}")

    metrics["gargalo_corte_minimo"] = {
        "origem": O, "destino": D,
        "fluxo_maximo": int(fmax),
        "corte_minimo": len(cut),
        "ruas_do_corte": [list(e) for e in cut],
        "outros_pontos_unicos_de_falha_na_rota": [list(e) for e in alt_cut_edges],
        "tempo_ms": round(t_flow * 1000, 2),
    }
    viz.fig_mincut(data, O, D, cut, reach, fmax,
                   os.path.join(OUT, "04_corte_minimo.png"),
                   alt_cut_edges=alt_cut_edges)

    # ---------------------------------------------------- rotas alternativas
    banner("(B) ROTAS ALTERNATIVAS (Dijkstra)")
    # par O-D DENTRO da grade residencial (onde a malha oferece redundancia),
    # para demonstrar de fato uma rota alternativa.
    grid = [u for u in giant if G.coords[u][1] > 150] or list(giant)
    Or = max(grid, key=lambda u: G.coords[u][0])
    Dr = min(grid, key=lambda u: G.coords[u][0])
    t0 = time.perf_counter()
    main_route, main_cost = sp.shortest_path(G, Or, Dr)
    t_dij = time.perf_counter() - t0
    # verificacao independente com Bellman-Ford
    t0 = time.perf_counter()
    bf_dist, _ = sp.bellman_ford(G, Or)
    t_bf = time.perf_counter() - t0
    bf_cost = bf_dist.get(Dr, math.inf)
    confere = abs(bf_cost - main_cost) < 1e-6

    # bloqueia um trecho da rota principal (preferindo uma ponte/corte) e
    # recalcula -> rota alternativa
    # Para DEMONSTRAR uma rota alternativa, bloqueia um trecho da rota que NAO
    # seja ponte (assim existe desvio pela malha). Trechos do meio primeiro.
    bridge_set = {frozenset(e) for e in brs}
    route_pairs = list(zip(main_route, main_route[1:])) if main_route else []
    order = sorted(range(len(route_pairs)),
                   key=lambda i: abs(i - len(route_pairs) / 2))
    blocked_edge = None
    for i in order:
        a, b = route_pairs[i]
        if frozenset((a, b)) not in bridge_set:
            blocked_edge = (a, b)
            break
    # quantas pontes a rota atravessa (trechos sem alternativa)
    route_bridges = [pair for pair in route_pairs
                     if frozenset(pair) in bridge_set]
    blocked = {blocked_edge, (blocked_edge[1], blocked_edge[0])} if blocked_edge else set()
    alt_route, alt_cost = sp.alternative_route(G, Or, Dr, blocked)

    print(f"Rota principal: {main_cost/60:.2f} min, {len(main_route)} intersecoes")
    print(f"Verificacao Bellman-Ford: {bf_cost/60:.2f} min "
          f"({'confere' if confere else 'DIVERGE'}); "
          f"Dijkstra {t_dij*1000:.1f} ms vs Bellman-Ford {t_bf*1000:.1f} ms")
    print(f"Origem Or={Or}  Destino Dr={Dr}  (dentro da grade residencial)")
    if alt_route:
        extra = 100.0 * (alt_cost - main_cost) / main_cost
        print(f"Trecho (nao-ponte) bloqueado: {blocked_edge}")
        print(f"Rota alternativa: {alt_cost/60:.2f} min  ({extra:+.1f}% vs principal)")
    else:
        print(f"Sem rota alternativa ao bloquear {blocked_edge}.")
    print(f"A rota atravessa {len(route_bridges)} ponte(s) — trechos SEM "
          f"alternativa (fechá-los desconecta a rota).")
    metrics["rotas_alternativas"] = {
        "origem": Or, "destino": Dr,
        "rota_principal_min": round(main_cost / 60, 2),
        "intersecoes_rota": len(main_route),
        "bellman_ford_confere": confere,
        "tempo_dijkstra_ms": round(t_dij * 1000, 2),
        "tempo_bellman_ford_ms": round(t_bf * 1000, 2),
        "trecho_bloqueado": list(blocked_edge) if blocked_edge else None,
        "rota_alternativa_min": (round(alt_cost / 60, 2)
                                 if alt_route else None),
        "acrescimo_pct": (round(100.0 * (alt_cost - main_cost) / main_cost, 1)
                          if alt_route else None),
        "pontes_na_rota": len(route_bridges),
    }
    viz.fig_routes(data, main_route, alt_route, Or, Dr, blocked,
                   os.path.join(OUT, "05_rotas.png"))

    # ------------------------------------------------------------ resiliencia
    banner("(C.3) RESILIENCIA: impacto EXAUSTIVO de cada ponte/articulacao "
           "forte sobre o nucleo")
    t0 = time.perf_counter()
    all_pairs = [(a, b) for a in gl for b in gl if a != b]
    print(f"Pares origem-destino exaustivos no nucleo: {len(all_pairs)}")

    def custos(blocked_edges=None, blocked_node=None):
        # Quando blocked_node=u, um par (a,b) com b==u e' contado como
        # desconectado (o Dijkstra nao encontra o destino bloqueado); um par
        # com a==u usa o proprio Dijkstra com blocked_nodes, que so bloqueia
        # a ENTRADA no no removido, nao a saida dele.
        out = {}
        blocked_nodes = {blocked_node} if blocked_node is not None else None
        for a, b in all_pairs:
            if blocked_node is not None and b == blocked_node:
                out[(a, b)] = math.inf
                continue
            _, c = sp.shortest_path(G, a, b, blocked_edges=blocked_edges,
                                     blocked_nodes=blocked_nodes)
            out[(a, b)] = c
        return out

    base_costs = custos()

    def resumo(valores):
        vals = sorted(valores)
        n = len(vals)
        med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        return {"min": vals[0], "mediana": med, "max": vals[-1]}

    impacto_pontes = []
    deltas_min_todos = []
    n_binarias = 0
    for (u, v) in core_breaking_edges:
        novo = custos(blocked_edges={(u, v), (v, u)})
        desconectados = sum(1 for k in base_costs
                             if base_costs[k] != math.inf and novo[k] == math.inf)
        deltas = [(novo[k] - base_costs[k]) / 60 for k in base_costs
                  if base_costs[k] != math.inf and novo[k] != math.inf
                  and novo[k] > base_costs[k] + 1e-9]
        impacto_pontes.append(desconectados)
        if deltas:
            deltas_min_todos.extend(deltas)
        else:
            n_binarias += 1

    impacto_nos = []
    for u in core_breaking_nodes:
        novo = custos(blocked_node=u)
        desconectados = sum(1 for k in base_costs
                             if base_costs[k] != math.inf and novo[k] == math.inf)
        impacto_nos.append(desconectados)

    t_res = time.perf_counter() - t0
    resumo_pontes = resumo(impacto_pontes)
    resumo_nos = resumo(impacto_nos)
    resumo_deltas = resumo(deltas_min_todos) if deltas_min_todos else None

    print(f"Pontes fortes, pares desconectados: min={resumo_pontes['min']} "
          f"mediana={resumo_pontes['mediana']} max={resumo_pontes['max']}")
    print(f"  binarias (sem desvio parcial): {n_binarias}  "
          f"com desvio parcial: {len(core_breaking_edges) - n_binarias}")
    if resumo_deltas:
        print(f"  desvio parcial ({len(deltas_min_todos)} pares): "
              f"min={resumo_deltas['min']:.2f} min "
              f"mediana={resumo_deltas['mediana']:.2f} min "
              f"max={resumo_deltas['max']:.2f} min")
    print(f"Articulacoes fortes, pares desconectados: min={resumo_nos['min']} "
          f"mediana={resumo_nos['mediana']} max={resumo_nos['max']}")
    print(f"Tempo: {t_res*1000:.1f} ms")

    metrics["resiliencia"] = {
        "n_pares_nucleo": len(all_pairs),
        "pontes_fortes": {
            "n": len(core_breaking_edges),
            "pares_desconectados": resumo_pontes,
            "binarias": n_binarias,
            "com_desvio_parcial": len(core_breaking_edges) - n_binarias,
            "n_pares_com_desvio_parcial": len(deltas_min_todos),
            "acrescimo_min": resumo_deltas,
        },
        "articulacoes_fortes": {
            "n": len(core_breaking_nodes),
            "pares_desconectados": resumo_nos,
        },
        "tempo_ms": round(t_res * 1000, 2),
    }

    # ------------------------------------------------------------------ saida
    metrics["tempo_total_s"] = round(time.perf_counter() - t0_all, 2)
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    banner("CONCLUIDO")
    print(f"Figuras e metricas em: {OUT}")
    print(f"Tempo total: {metrics['tempo_total_s']} s")


if __name__ == "__main__":
    main()