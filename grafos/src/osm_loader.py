"""
Carrega a rede viária REAL de um bairro a partir do OpenStreetMap (OSM).

Faz o que bibliotecas como o OSMnx fazem, porém de forma enxuta e transparente:

  1. Baixa as vias (`highway`) do bairro pela Overpass API do OSM.
  2. Monta o grafo dirigido completo (respeitando ruas de mão única).
  3. SIMPLIFICA a topologia: contrai as sequências de pontos de forma
     (vértices de grau 2 que são apenas "dobras" da rua) em uma única aresta
     entre interseções de verdade — exatamente como o OSMnx faz. Sem isso, cada
     curva da rua viraria um falso ponto de articulação.
  4. Projeta as coordenadas (lat/lon) para metros, para medir distâncias e
     desenhar o mapa.

Os dados brutos são salvos em data/<bairro>.json (cache), de modo que a análise
é reprodutível e não depende de acesso à rede após o primeiro download.

Fonte: © OpenStreetMap contributors (ODbL).
"""

from __future__ import annotations
import json
import math
import os
import urllib.request
import urllib.parse

from graph import Graph

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# tipos de via "dirigíveis" (carro)
DRIVE = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
         "living_street|road|motorway_link|trunk_link|primary_link|"
         "secondary_link|tertiary_link")

# velocidade default (km/h) por tipo de via, quando o OSM não traz maxspeed
DEFAULT_SPEED = {
    "motorway": 90, "trunk": 80, "primary": 60, "secondary": 50,
    "tertiary": 40, "unclassified": 40, "residential": 30,
    "living_street": 20, "road": 30,
    "motorway_link": 60, "trunk_link": 50, "primary_link": 40,
    "secondary_link": 40, "tertiary_link": 30,
}


# ---------------------------------------------------------------------------
# Download (Overpass)
# ---------------------------------------------------------------------------
def _overpass(bbox: str) -> dict:
    s, w, n, e = bbox.split(",")
    q = (f"[out:json][timeout:120];"
         f'way[highway~"^({DRIVE})$"]({s},{w},{n},{e})->.w;'
         f"(.w; .w >;); out body;")
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter", data=data,
        headers={"User-Agent": "grafos-academic/1.0 (trabalho academico)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def fetch_osm(name: str, bbox: str, use_cache: bool = True) -> dict:
    """Baixa (ou lê do cache) os elementos OSM do bairro."""
    cache = os.path.join(DATA_DIR, f"{name}.json")
    if use_cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    raw = _overpass(bbox)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(raw, f)
    return raw


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _oneway_dir(tags: dict) -> int:
    """Retorna +1 (no sentido dos nós), -1 (invertido) ou 0 (mão dupla)."""
    ow = str(tags.get("oneway", "")).lower()
    if ow in ("yes", "true", "1"):
        return 1
    if ow in ("-1", "reverse"):
        return -1
    if tags.get("junction") == "roundabout":
        return 1
    if tags.get("highway") in ("motorway", "motorway_link", "trunk_link"):
        return 1  # convenção OSM
    return 0


def _speed(tags: dict) -> float:
    ms = tags.get("maxspeed")
    if ms:
        try:
            return float(str(ms).split()[0])
        except (ValueError, IndexError):
            pass
    return DEFAULT_SPEED.get(tags.get("highway", "residential"), 30)


# ---------------------------------------------------------------------------
# Construção e simplificação do grafo
# ---------------------------------------------------------------------------
def load_neighborhood(name: str, bbox: str, use_cache: bool = True) -> dict:
    raw = fetch_osm(name, bbox, use_cache)
    nodes_ll = {}      # id -> (lat, lon)
    ways = []          # (lista de node ids, tags)
    for el in raw["elements"]:
        if el["type"] == "node":
            nodes_ll[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "way" and "nodes" in el:
            ways.append((el["nodes"], el.get("tags", {})))

    # --- arcos dirigidos completos + segmentos não-dirigidos ----------------
    arcs: set[tuple[int, int]] = set()
    segments = []      # (a, b, length, speed)
    undir_adj: dict[int, list[tuple[int, int]]] = {}   # node -> [(segid, other)]

    def add_seg(a, b, length, speed):
        sid = len(segments)
        segments.append((a, b, length, speed))
        undir_adj.setdefault(a, []).append((sid, b))
        undir_adj.setdefault(b, []).append((sid, a))

    for node_ids, tags in ways:
        d = _oneway_dir(tags)
        sp = _speed(tags)
        for a, b in zip(node_ids, node_ids[1:]):
            if a not in nodes_ll or b not in nodes_ll:
                continue
            la, lo = nodes_ll[a]
            lb, lob = nodes_ll[b]
            length = _haversine(la, lo, lb, lob)
            if length == 0:
                continue
            add_seg(a, b, length, sp)
            if d == 0:
                arcs.add((a, b)); arcs.add((b, a))
            elif d == 1:
                arcs.add((a, b))
            else:
                arcs.add((b, a))

    # --- interseções (endpoints): grau != 2 -------------------------------
    def degree(u):
        return len(undir_adj.get(u, []))
    endpoints = {u for u in undir_adj if degree(u) != 2}
    # caso degenerado: nenhum endpoint (anel isolado) -> escolhe um nó
    if not endpoints and undir_adj:
        endpoints = {next(iter(undir_adj))}

    # --- contrai cadeias de grau 2 entre interseções ----------------------
    used = set()       # segids consumidos
    chains = []        # cada cadeia: lista de node ids c0..ck

    def walk(start, first_seg, first_other):
        seq = [start]
        seg, other = first_seg, first_other
        prev = start
        while True:
            used.add(seg)
            seq.append(other)
            if other in endpoints:
                break
            # nó de grau 2: segue para o próximo segmento
            nxt = [(s, o) for (s, o) in undir_adj[other] if s != seg]
            if len(nxt) != 1:
                break
            seg, nxtother = nxt[0]
            if seg in used:
                break
            prev, other = other, nxtother
        return seq

    for u in endpoints:
        for seg, other in undir_adj[u]:
            if seg in used:
                continue
            chains.append(walk(u, seg, other))

    # --- projeção para metros (equirretangular) ---------------------------
    lats = [ll[0] for ll in nodes_ll.values()]
    lons = [ll[1] for ll in nodes_ll.values()]
    lat0 = sum(lats) / len(lats)
    lon0 = sum(lons) / len(lons)
    kx = math.cos(math.radians(lat0)) * 111320.0
    ky = 110540.0

    def xy(nid):
        la, lo = nodes_ll[nid]
        return ((lo - lon0) * kx, (la - lat0) * ky)

    # --- monta o grafo dirigido simplificado ------------------------------
    G = Graph()
    core_nodes = set()
    for ch in chains:
        core_nodes.add(ch[0]); core_nodes.add(ch[-1])
    for nid in core_nodes:
        x, y = xy(nid)
        G.add_node(nid, x, y)

    undirected_edges = []   # (u, v, length, geometry) permitindo paralelas
    for ch in chains:
        u, v = ch[0], ch[-1]
        if u == v:
            continue  # laço (rotatória fechada) — ignora para a análise
        length = sum(_haversine(*nodes_ll[a], *nodes_ll[b])
                     for a, b in zip(ch, ch[1:]))
        # velocidade média ponderada pelo comprimento
        tot_t = 0.0
        for a, b in zip(ch, ch[1:]):
            seg = next((segments[s] for s, o in undir_adj[a] if o == b), None)
            if seg:
                tot_t += seg[2] / (seg[3] * 1000 / 3600)
        fwd = all((a, b) in arcs for a, b in zip(ch, ch[1:]))
        bwd = all((b, a) in arcs for a, b in zip(ch, ch[1:]))
        geom = [xy(n) for n in ch]
        if fwd:
            G.add_directed_explicit(u, v, length, tot_t)
        if bwd:
            G.add_directed_explicit(v, u, length, tot_t)
        if fwd or bwd:
            undirected_edges.append((u, v, length, geom))

    return {
        "graph": G,
        "name": name,
        "undirected_edges": undirected_edges,   # interseções, com geometria
        "n_raw_nodes": len(nodes_ll),
        "n_ways": len(ways),
        "lat0": lat0, "lon0": lon0,
    }
