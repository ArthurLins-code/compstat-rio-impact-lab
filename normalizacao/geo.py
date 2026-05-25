"""Helpers geográficos: parsing de WKT, correção de coordenadas, bbox e point-in-polygon."""
import numpy as np
import shapefile  # pyshp
import shapely
from shapely import STRtree

from . import config as C


def load_area_polygons():
    """Lê o shapefile das 8 áreas FM. Retorna (fids, nomes, polygons, STRtree)."""
    sf = shapefile.Reader(str(C.F_SHP))
    field_names = [f[0] for f in sf.fields[1:]]
    fids, nomes, polys = [], [], []
    for sr in sf.shapeRecords():
        rec = dict(zip(field_names, list(sr.record)))
        fids.append(int(rec["fid"]))
        nomes.append(rec["nome_subar"])
        polys.append(shapely.geometry.shape(sr.shape.__geo_interface__))
    tree = STRtree(polys)
    return fids, nomes, polys, tree


def in_bbox(lon, lat):
    """Máscara booleana vetorizada: ponto dentro do bounding box do Rio."""
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    return (
        (lon >= C.LON_MIN) & (lon <= C.LON_MAX)
        & (lat >= C.LAT_MIN) & (lat <= C.LAT_MAX)
    )


def parse_wkt_points(series):
    """Extrai (lon, lat) de uma série de WKT POINT. Vazios/inválidos viram NaN."""
    s = series.map(lambda v: v if (isinstance(v, str) and v.strip()) else None)
    geoms = shapely.from_wkt(s.values, on_invalid="ignore")
    lon = shapely.get_x(geoms)
    lat = shapely.get_y(geoms)
    return lon, lat


def fix_decimal_shift(values):
    """Corrige coordenadas que perderam o ponto decimal (ex.: -22901 -> -22.901).

    Divide por 10 repetidamente até cair numa faixa plausível de grau.
    Retorna (corrigido, foi_reparado_mask).
    """
    v = np.asarray(values, dtype="float64").copy()
    repaired = np.zeros(v.shape, dtype=bool)
    finite = np.isfinite(v)
    # Latitude/longitude do Rio têm |valor| < 90; valores maiores perderam o ponto.
    for _ in range(6):
        big = finite & (np.abs(v) > 90)
        if not big.any():
            break
        v[big] = v[big] / 10.0
        repaired |= big
    return v, repaired


def assign_area_fm(lon, lat, tree, fids):
    """Point-in-polygon: para cada ponto, o fid da área FM que o contém (ou None).

    Usa STRtree do shapely 2.0 com predicate 'within'. Pontos com coord inválida
    recebem None.
    """
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    n = len(lon)
    out = np.full(n, None, dtype=object)

    valid = np.isfinite(lon) & np.isfinite(lat)
    if not valid.any():
        return out

    idx_valid = np.flatnonzero(valid)
    pts = shapely.points(lon[idx_valid], lat[idx_valid])
    # query retorna pares (input_idx, tree_idx) onde ponto.within(poligono)
    input_idx, tree_idx = tree.query(pts, predicate="within")
    fids_arr = np.asarray(fids)
    for ii, ti in zip(input_idx, tree_idx):
        out[idx_valid[ii]] = int(fids_arr[ti])
    return out
