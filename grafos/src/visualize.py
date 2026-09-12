"""
Visualizacoes da rede de ruas real (Urca/RJ) e dos resultados das analises.

Usa a geometria real das ruas (polilinhas do OpenStreetMap) para desenhar o
mapa. Backend 'Agg' para funcionar sem interface grafica.
"""

from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

# fontes maiores para boa leitura na impressao do artigo
plt.rcParams.update({
    "font.size": 13,
    "axes.titlesize": 15,
    "legend.fontsize": 12,
})


def _geom_lookup(data):
    """frozenset(u,v) -> geometria (lista de pontos), na ordem u->v."""
    lut = {}
    for (u, v, length, geom) in data["undirected_edges"]:
        lut[(u, v)] = geom
    return lut


def _route_segments(route, lut, G):
    """Lista de polilinhas (uma por arco do caminho)."""
    segs = []
    for a, b in zip(route, route[1:]):
        if (a, b) in lut:
            segs.extend(zip(lut[(a, b)], lut[(a, b)][1:]))
        elif (b, a) in lut:
            g = lut[(b, a)]
            segs.extend(zip(g, g[1:]))
        else:
            segs.append((G.coords[a], G.coords[b]))
    return segs


def draw_base(data, ax, color="#c2c7d0", lw=1.0, node_color="#9aa3b2"):
    G = data["graph"]
    segs = []
    for (u, v, length, geom) in data["undirected_edges"]:
        segs.extend(zip(geom, geom[1:]))
    ax.add_collection(LineCollection(segs, colors=color, linewidths=lw, zorder=1))
    xs = [c[0] for c in G.coords.values()]
    ys = [c[1] for c in G.coords.values()]
    ax.scatter(xs, ys, s=6, c=node_color, zorder=2)
    ax.set_aspect("equal"); ax.margins(0.04)
    ax.set_xticks([]); ax.set_yticks([])


def fig_overview(data, path):
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    draw_base(data, ax)
    G = data["graph"]
    ax.set_title(f"Bairro da Urca (RJ) — rede de ruas do OpenStreetMap\n"
                 f"{G.n} interseções, {len(data['undirected_edges'])} trechos "
                 f"(de {data['n_raw_nodes']} pontos OSM)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_scc(data, sccs, path):
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    draw_base(data, ax, color="#dfe3ea")
    G = data["graph"]
    cmap = plt.get_cmap("tab10")

    # componentes nao triviais (>1 no) recebem cor propria e tem suas ruas
    # internas grifadas; componentes triviais (1 no) sao ruas de mao unica
    # sem nenhuma aresta interna por definicao, e por isso so aparecem como
    # marcador neutro, sem grifar rua nenhuma.
    non_trivial = sorted([c for c in sccs if len(c) > 1], key=len, reverse=True)
    trivial = [c[0] for c in sccs if len(c) == 1]

    # ruas cujos dois extremos estao na mesma componente nao trivial: grifadas
    # na cor da componente. As demais (inclusive as que tocam nos isolados)
    # permanecem cinza de fundo, o que por si so mostra quais ruas "cruzam"
    # entre componentes.
    for i, comp in enumerate(non_trivial):
        cset = set(comp)
        segs = []
        for (u, v, length, geom) in data["undirected_edges"]:
            if u in cset and v in cset:
                segs.extend(zip(geom, geom[1:]))
        if segs:
            ax.add_collection(LineCollection(segs, colors=cmap(i % 10),
                                              linewidths=2.4, zorder=3))

    for i, comp in enumerate(non_trivial):
        xs = [G.coords[u][0] for u in comp]
        ys = [G.coords[u][1] for u in comp]
        ax.scatter(xs, ys, s=28, color=cmap(i % 10), zorder=5,
                   label=f"CFC {i+1} ({len(comp)} nós)")
    if trivial:
        xs = [G.coords[u][0] for u in trivial]
        ys = [G.coords[u][1] for u in trivial]
        ax.scatter(xs, ys, s=34, color="#333333", marker="x", zorder=5,
                   label=f"interseções isoladas ({len(trivial)})")

    ax.legend(loc="upper left", fontsize=11, framealpha=0.9)
    ax.set_title("Componentes fortemente conexas (alcançabilidade de carro)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_critical(data, br, ap, path):
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    draw_base(data, ax, color="#dfe3ea")
    G = data["graph"]
    lut = _geom_lookup(data)
    if br:
        segs = []
        for (u, v) in br:
            g = lut.get((u, v)) or lut.get((v, u))
            if g:
                segs.extend(zip(g, g[1:]))
            else:
                segs.append((G.coords[u], G.coords[v]))
        ax.add_collection(LineCollection(segs, colors="#e6194b",
                                         linewidths=3.2, zorder=4))
        ax.plot([], [], color="#e6194b", lw=3, label=f"pontes ({len(br)})")
    if ap:
        ax.scatter([G.coords[u][0] for u in ap],
                   [G.coords[u][1] for u in ap],
                   s=70, facecolors="none", edgecolors="#ff8c00",
                   linewidths=2.0, zorder=6,
                   label=f"articulações ({len(ap)})")
    ax.legend(loc="upper left", fontsize=12, framealpha=0.9)
    ax.set_title("Gargalos estruturais: pontes e pontos de articulação")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _edge_segments(edges, lut, G):
    """Concatena as polilinhas de uma lista de arestas (u, v, ...)."""
    segs = []
    for e in edges:
        u, v = e[0], e[1]
        g = lut.get((u, v)) or lut.get((v, u))
        if g:
            segs.extend(zip(g, g[1:]))
        else:
            segs.append((G.coords[u], G.coords[v]))
    return segs


def fig_strong_gargalos(data, core_nodes, edges_both, edges_strong_only,
                         edges_weak_only, nodes_both, nodes_strong_only, path):
    """Gargalos estruturais dirigidos (Secao 4.3), com pontes e articulacoes
    classificadas cruzando fraca x forte (Tabelas tab:pontes-fortes e
    tab:articulacoes-fortes):
      edges_both        -> ponte fraca E forte (6)
      edges_strong_only -> so forte, nao fraca (31 segmentos / 29 pares de
                            nos, ha 2 pares com rua dupla/paralela)
      edges_weak_only    -> so fraca, nao fragmenta o nucleo forte (3)
      nodes_both         -> articulacao fraca E forte (6)
      nodes_strong_only  -> so forte, nao fraca (22)
    Ruas/interseccoes que nao caem em nenhuma categoria ficam no cinza de
    fundo (49 ruas, 9 interseccoes do nucleo), sem cor propria.
    """
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    draw_base(data, ax, color="#dfe3ea")
    G = data["graph"]
    lut = _geom_lookup(data)
    core_set = set(core_nodes)

    # nucleo fortemente conexo (37 nos), como referencia de fundo
    cxs = [G.coords[u][0] for u in core_set]
    cys = [G.coords[u][1] for u in core_set]
    ax.scatter(cxs, cys, s=34, color="#9ecae1", zorder=2,
               label=f"núcleo fortemente conexo ({len(core_set)} nós)")

    # ruas: 3 categorias de cor, "nem uma nem outra" fica cinza (implícito)
    if edges_weak_only:
        ax.add_collection(LineCollection(
            _edge_segments(edges_weak_only, lut, G), colors="#807dba",
            linewidths=3.0, zorder=3))
        ax.plot([], [], color="#807dba", lw=3,
                label=f"ponte só fraca, não fragmenta o núcleo ({len(edges_weak_only)})")
    if edges_strong_only:
        ax.add_collection(LineCollection(
            _edge_segments(edges_strong_only, lut, G), colors="#fb6a4a",
            linewidths=3.2, zorder=4))
        ax.plot([], [], color="#fb6a4a", lw=3,
                label=f"ponte só forte, nova em relação à fraca ({len(edges_strong_only)})")
    if edges_both:
        ax.add_collection(LineCollection(
            _edge_segments(edges_both, lut, G), colors="#a50f15",
            linewidths=3.6, zorder=5))
        ax.plot([], [], color="#a50f15", lw=3,
                label=f"ponte fraca e forte ({len(edges_both)})")

    # interseccoes do nucleo: 2 categorias (a 3a celula da tabela, fraca
    # fora do nucleo, nao se aplica aqui por definicao)
    if nodes_strong_only:
        ax.scatter([G.coords[u][0] for u in nodes_strong_only],
                   [G.coords[u][1] for u in nodes_strong_only],
                   s=85, facecolors="none", edgecolors="#ff8c00",
                   linewidths=2.2, zorder=6,
                   label=f"articulação só forte ({len(nodes_strong_only)})")
    if nodes_both:
        ax.scatter([G.coords[u][0] for u in nodes_both],
                   [G.coords[u][1] for u in nodes_both],
                   s=85, facecolors="#ff8c00", edgecolors="#7a3d00",
                   linewidths=1.6, zorder=7,
                   label=f"articulação fraca e forte ({len(nodes_both)})")

    ax.legend(loc="upper left", fontsize=11, framealpha=0.9)
    ax.set_title("Gargalos estruturais dirigidos\n"
                 "(fragmentam o núcleo fortemente conexo de 37 interseções)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_mincut(data, source, sink, cut_edges, reachable, maxflow, path,
               alt_cut_edges=None):
    """alt_cut_edges: outras arestas da mesma rota O-D que, isoladamente,
    tambem sao corte de valor 1 (pontos unicos de falha em serie), alem da
    encontrada pelo Edmonds-Karp em cut_edges. Ver Secao 4.4 do artigo."""
    alt_cut_edges = alt_cut_edges or []
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    G = data["graph"]
    lut = _geom_lookup(data)
    # ruas, coloridas conforme o lado do corte
    segs_s, segs_t = [], []
    for (u, v, length, geom) in data["undirected_edges"]:
        pts = list(zip(geom, geom[1:]))
        if u in reachable and v in reachable:
            segs_s.extend(pts)
        else:
            segs_t.extend(pts)
    ax.add_collection(LineCollection(segs_s, colors="#9ecae1", linewidths=1.4, zorder=1))
    ax.add_collection(LineCollection(segs_t, colors="#cbd2dc", linewidths=1.4, zorder=1))
    # arestas do corte minimo reportado (Edmonds-Karp)
    csegs = []
    for (u, v) in cut_edges:
        g = lut.get((u, v)) or lut.get((v, u))
        if g:
            csegs.extend(zip(g, g[1:]))
        else:
            csegs.append((G.coords[u], G.coords[v]))
    ax.add_collection(LineCollection(csegs, colors="#e6194b", linewidths=3.6, zorder=5))
    ax.plot([], [], color="#e6194b", lw=3,
            label=f"corte mínimo reportado ({len(cut_edges)} rua)")
    # outras ruas da mesma rota que, isoladamente, tambem seriam corte de
    # valor 1 (pontos unicos de falha em serie, nao unicidade do corte)
    if alt_cut_edges:
        asegs = []
        for (u, v) in alt_cut_edges:
            g = lut.get((u, v)) or lut.get((v, u))
            if g:
                asegs.extend(zip(g, g[1:]))
            else:
                asegs.append((G.coords[u], G.coords[v]))
        ax.add_collection(LineCollection(asegs, colors="#f4a300",
                                          linewidths=3.6, linestyles="--",
                                          zorder=5))
        ax.plot([], [], color="#f4a300", lw=3, ls="--",
                label=f"outros pontos únicos de falha na mesma rota "
                      f"({len(alt_cut_edges)})")
    for node, lbl, col in [(source, "O", "#1a7d1a"), (sink, "D", "#000")]:
        x, y = G.coords[node]
        ax.scatter([x], [y], s=160, color=col, zorder=8)
        ax.text(x, y, lbl, color="white", ha="center", va="center",
                fontsize=12, fontweight="bold", zorder=9)
    ax.scatter([], [], color="#9ecae1", label="lado da origem (O)")
    ax.set_aspect("equal"); ax.margins(0.04)
    ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc="upper left", fontsize=11, framealpha=0.9)
    n_total = len(cut_edges) + len(alt_cut_edges)
    ax.set_title(f"Gargalo por fluxo máximo / corte mínimo\n"
                 f"fluxo máximo = {int(maxflow)} rota distinta; "
                 f"{n_total} rua(s) seriam, isoladamente, corte de valor 1")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_routes(data, main_route, alt_route, s, t, blocked, path):
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    draw_base(data, ax, color="#dfe3ea")
    G = data["graph"]
    lut = _geom_lookup(data)
    if main_route:
        ax.add_collection(LineCollection(
            _route_segments(main_route, lut, G), colors="#e6194b",
            linewidths=3.4, zorder=5, label="rota principal (Dijkstra)"))
    if alt_route:
        ax.add_collection(LineCollection(
            _route_segments(alt_route, lut, G), colors="#4363d8",
            linewidths=3.0, linestyles="dashed", zorder=4,
            label="rota alternativa (trecho bloqueado)"))
    if blocked:
        for (u, v) in blocked:
            g = lut.get((u, v)) or lut.get((v, u))
            if g:
                ax.add_collection(LineCollection(list(zip(g, g[1:])),
                                  colors="#000", linewidths=2.0, zorder=6))
        ax.plot([], [], color="#000", lw=2, label="trecho bloqueado")
    for node, lbl in [(s, "O"), (t, "D")]:
        x, y = G.coords[node]
        ax.scatter([x], [y], s=150, color="#000", zorder=8)
        ax.text(x, y, lbl, color="white", ha="center", va="center",
                fontsize=12, fontweight="bold", zorder=9)
    ax.legend(loc="upper left", fontsize=12, framealpha=0.9)
    ax.set_title("Rotas alternativas (Dijkstra)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)