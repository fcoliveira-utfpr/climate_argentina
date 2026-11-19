# -*- coding: utf-8 -*-
"""Validação e incerteza:
  1. Estações GHCN-Daily (Argentina, 1991-2020): viés da temperatura mensal do CHELSA nos mesmos meses.
  2. Köppen-Geiger 1991-2020 de Beck et al. (2023, V2, 1 km): concordância com o mapa deste trabalho.
  3. TerraClimate 1991-2020 (~4 km): as três classificações com outra base de dados.
  4. Sensibilidade: % da área do país que muda de classe ao perturbar T, P, CAD e o método da ETP.
  5. Ecorregiões RESOLVE (2017) x zonas de vida de Holdridge.
Grava dados_brutos/classificacoes/validacao.json, estacoes.csv e validacao_pixels.npz (para o atlas).
"""
import gzip
import io
import json
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling

import classif as K
import config as C
from agrometeorologiapy.classificacao_climatica import KOPPEN_CLASSES

EXT = C.EXTERNOS_DIR
KOPPEN_ID = {v: k for k, v in KOPPEN_CLASSES.items()}
BECK = {1: "Af", 2: "Am", 3: "Aw", 4: "BWh", 5: "BWk", 6: "BSh", 7: "BSk", 8: "Csa", 9: "Csb", 10: "Csc",
        11: "Cwa", 12: "Cwb", 13: "Cwc", 14: "Cfa", 15: "Cfb", 16: "Cfc", 17: "Dsa", 18: "Dsb", 19: "Dsc",
        20: "Dsd", 21: "Dwa", 22: "Dwb", 23: "Dwc", 24: "Dwd", 25: "Dfa", 26: "Dfb", 27: "Dfc", 28: "Dfd",
        29: "ET", 30: "EF"}


def pct_area(igual, area):
    return float(100 * area[igual].sum() / area.sum())


def na_grade(src_path, banda, transform, crs, shape, resampling=Resampling.nearest):
    with rasterio.open(src_path) as src:
        out = np.full(shape, np.nan, np.float32)
        reproject(rasterio.band(src, banda), out, dst_transform=transform, dst_crs=crs,
                  resampling=resampling, dst_nodata=np.nan)
    return out


# ---------------------------------------------------------------------------
# 1. Estações
# ---------------------------------------------------------------------------
def estacoes(lin_lon_lat):
    pasta = EXT / "ghcn"
    st = pd.read_fwf(pasta / "ghcnd-stations.txt", colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (41, 71)],
                     names=["id", "lat", "lon", "elev", "nome"])
    inv = pd.read_fwf(pasta / "ghcnd-inventory.txt", colspecs=[(0, 11), (12, 20), (21, 30), (31, 35), (36, 40), (41, 45)],
                      names=["id", "lat", "lon", "el", "ini", "fim"])
    inv = inv[inv.id.str.startswith("AR") & inv.el.isin(["TAVG", "TMAX", "TMIN"])
              & (inv.ini <= 2015) & (inv.fim >= 1996)]
    ids = sorted(set(inv.id))

    def baixar(i):
        arq = pasta / f"{i}.csv.gz"
        if not arq.exists():
            r = requests.get(f"https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{i}.csv.gz", timeout=120)
            r.raise_for_status()
            arq.write_bytes(r.content)
        return arq
    with ThreadPoolExecutor(8) as ex:
        arqs = list(ex.map(baixar, ids))

    mensais = {}
    for i, arq in zip(ids, arqs):
        with gzip.open(arq, "rt") as f:
            d = pd.read_csv(f, header=None, usecols=[1, 2, 3, 5], names=["data", "el", "v", "q"],
                            dtype={"data": str, "el": str, "v": float, "q": str})
        d = d[d.el.isin(["TAVG", "TMAX", "TMIN"]) & d.q.isna() & d.data.between("19910101", "20201231")]
        if d.empty:
            continue
        p = d.pivot_table(index="data", columns="el", values="v", aggfunc="first") / 10
        tavg = p["TAVG"] if "TAVG" in p else pd.Series(np.nan, index=p.index)
        if "TMAX" in p and "TMIN" in p:
            tavg = tavg.fillna((p["TMAX"] + p["TMIN"]) / 2)
        tavg = tavg.dropna()
        idx = pd.to_datetime(tavg.index, format="%Y%m%d")
        g = tavg.groupby([idx.year, idx.month])
        m = g.mean()[g.count() >= 25]          # mês com >= 25 dias válidos
        if len(m) >= 120:                      # >= 10 anos de meses completos
            mensais[i] = m
    st = st.set_index("id").loc[list(mensais)]
    print(f"Estações com >= 120 meses completos: {len(mensais)}")

    transform, _, shape = C.grade()
    inv_t = ~transform
    pos = {}
    for i, r in st.iterrows():
        c, l = inv_t * (r.lon, r.lat)
        pos[i] = (int(l), int(c))
    chelsa = {i: {} for i in mensais}
    for ano in C.ANOS:
        for mes in range(1, 13):
            g = C.ler_mensal("tas", ano, mes)
            for i, (l, c) in pos.items():
                if (ano, mes) in mensais[i].index and 0 <= l < shape[0] and 0 <= c < shape[1]:
                    chelsa[i][(ano, mes)] = g[l, c]
    linhas = []
    for i, m in mensais.items():
        ch = pd.Series(chelsa[i]).reindex(m.index)
        ok = ch.notna()
        if ok.sum() < 120:
            continue
        dif = ch[ok] - m[ok]
        linhas.append(dict(id=i, nome=st.loc[i, "nome"].title(), lat=st.loc[i, "lat"], lon=st.loc[i, "lon"],
                           elev=st.loc[i, "elev"], n_meses=int(ok.sum()), vies=round(float(dif.mean()), 2),
                           mae=round(float(dif.abs().mean()), 2),
                           r=round(float(np.corrcoef(ch[ok], m[ok])[0, 1]), 3)))
    tab = pd.DataFrame(linhas).sort_values("vies")
    tab.to_csv(C.CLASSES_DIR / "estacoes.csv", index=False, encoding="utf-8")
    return dict(n=len(tab), vies_medio=round(float(tab.vies.mean()), 2),
                vies_mediano=round(float(tab.vies.median()), 2), mae_medio=round(float(tab.mae.mean()), 2),
                n_mais_frio=int((tab.vies < 0).sum()), r_medio=round(float(tab.r.mean()), 3))


def estacoes_precip():
    """Precipitação: NOAA GSOD (rede sinótica do SMN). Só dias com total completo (flags D, E, F, G)
    ou sem relato (I) e sem ocorrência de chuva/neve no dia (FRSHTT) = 0 mm; mês válido com >= 27 dias completos (total escalado para o mês inteiro).
    Normal mensal da estação e do CHELSA nos MESMOS meses válidos; viés relativo do total anual."""
    pasta = EXT / "gsod"
    h = pd.read_csv(pasta / "isd-history.csv", dtype=str)
    h = h[(h.CTRY == "AR") & (h.END >= "20150101") & (h.BEGIN <= "19960101")]
    meses_val = {}
    meta = {}
    for _, r in h.iterrows():
        i = r.USAF + r.WBAN
        arqs = [pasta / str(a) / f"{i}.csv" for a in C.ANOS if (pasta / str(a) / f"{i}.csv").exists()]
        if not arqs:
            continue
        d = pd.concat([pd.read_csv(a, usecols=["DATE", "PRCP", "PRCP_ATTRIBUTES", "FRSHTT"], dtype=str)
                       for a in arqs], ignore_index=True)
        d["p"] = d.PRCP.astype(float)
        fl = d.PRCP_ATTRIBUTES.str.strip()
        oc = d.FRSHTT.str.zfill(6)
        seco = (oc.str[1] == "0") & (oc.str[2] == "0")      # sem chuva/garoa nem neve no dia
        d = d[(d.p < 99) & (fl.isin(["D", "E", "F", "G"]) | ((fl == "I") & seco))]
        if d.empty:
            continue
        dt = pd.to_datetime(d.DATE)
        g = (d.p * 25.4).groupby([dt.dt.year, dt.dt.month])
        n, s = g.count(), g.sum()
        dias = pd.Series([pd.Period(f"{a}-{m:02d}").days_in_month for a, m in n.index], index=n.index)
        ok = n >= 27
        m = (s / n * dias)[ok]
        if len(m) >= 60 and m.index.get_level_values(1).nunique() == 12:
            meses_val[i] = m
            meta[i] = dict(nome=r["STATION NAME"].title(), lat=float(r.LAT), lon=float(r.LON),
                           elev=float(r["ELEV(M)"]))
    transform, _, shape = C.grade()
    inv_t = ~transform
    pos = {}
    for i, mm in meta.items():
        c, l = inv_t * (mm["lon"], mm["lat"])
        pos[i] = (int(l), int(c))
    ch = {i: {} for i in meses_val}
    for ano in C.ANOS:
        for mes in range(1, 13):
            g = C.ler_mensal("pr", ano, mes)
            for i, (l, c) in pos.items():
                if (ano, mes) in meses_val[i].index and 0 <= l < shape[0] and 0 <= c < shape[1]:
                    ch[i][(ano, mes)] = g[l, c]
    linhas = []
    for i, m in meses_val.items():
        c = pd.Series(ch[i]).reindex(m.index)
        ok = c.notna()
        m, c = m[ok], c[ok]
        mes = m.index.get_level_values(1)
        if pd.Series(mes).value_counts().min() < 5:   # >= 5 anos válidos em cada mês do ano
            continue
        est_anual = m.groupby(mes).mean().sum()
        ch_anual = c.groupby(mes).mean().sum()
        if est_anual < 50:
            continue
        linhas.append(dict(id=i, **meta[i], n_meses=int(len(m)), p_estacao=round(float(est_anual), 1),
                           p_chelsa=round(float(ch_anual), 1),
                           vies_rel=round(float(100 * (ch_anual - est_anual) / est_anual), 1),
                           r_mensal=round(float(np.corrcoef(c, m)[0, 1]), 3)))
    tab = pd.DataFrame(linhas).sort_values("vies_rel")
    tab.to_csv(C.CLASSES_DIR / "estacoes_precip.csv", index=False, encoding="utf-8")
    return dict(n=len(tab), vies_rel_mediano=round(float(tab.vies_rel.median()), 1),
                vies_rel_abs_medio=round(float(tab.vies_rel.abs().mean()), 1),
                r_mensal_medio=round(float(tab.r_mensal.mean()), 3),
                n_dentro_10=int((tab.vies_rel.abs() <= 10).sum()), n_chelsa_maior=int((tab.vies_rel > 0).sum()))


# ---------------------------------------------------------------------------
# 2. Beck et al. (2023)
# ---------------------------------------------------------------------------
def beck(px, mask_grade):
    transform, crs, shape = C.grade()
    g = na_grade(EXT / "beck" / "1991_2020" / "koppen_geiger_0p00833333.tif", 1, transform, crs, shape)
    b = g[px["lin"], px["col"]]
    conv = np.zeros(256, np.uint8)
    for k, v in BECK.items():
        conv[k] = KOPPEN_ID[v]
    bk = conv[np.nan_to_num(b, nan=0).astype(np.uint8)]
    ok = bk > 0
    area = px["area"]
    kp = px["koppen"]
    grupo = lambda x: np.array([KOPPEN_CLASSES.get(int(c), "?")[0] for c in range(32)])[x]
    res = dict(concordancia=pct_area((bk == kp) & ok, area * ok) if ok.any() else None,
               concordancia_grupos=pct_area((grupo(bk) == grupo(kp)) & ok, area * ok))
    # matriz de confusão (área %, classes deste trabalho x Beck)
    conf = {}
    for a in np.unique(kp):
        for b_ in np.unique(bk[kp == a]):
            p = 100 * area[(kp == a) & (bk == b_)].sum() / area.sum()
            if p >= 0.5:
                conf[f"{KOPPEN_CLASSES[int(a)]}>{KOPPEN_CLASSES.get(int(b_), '-')}"] = round(float(p), 2)
    res["confusao"] = dict(sorted(conf.items(), key=lambda x: -x[1]))
    return res, bk


# ---------------------------------------------------------------------------
# 3. TerraClimate
# ---------------------------------------------------------------------------
def terraclimate(px):
    transform, crs, shape = C.grade()
    d = {}
    for v in ("ppt", "tmax", "tmin", "pet"):
        arq = f"netcdf:{EXT / 'terraclimate' / f'TerraClimate_19912020_{v}.nc'}:{v}"
        with rasterio.open(arq) as src:
            esc, off = src.scales[0], src.offsets[0]
            if src.crs is None:
                print("  aviso: TerraClimate sem CRS; assumindo EPSG:4326")
        meses = []
        for m in range(1, 13):
            with rasterio.open(arq) as src:
                out = np.full(shape, np.nan, np.float32)
                reproject(rasterio.band(src, m), out, src_crs=src.crs or "EPSG:4326", dst_transform=transform,
                          dst_crs=crs, resampling=Resampling.nearest, dst_nodata=np.nan)
            meses.append(out[px["lin"], px["col"]] * esc + off)
        d[v] = np.stack(meses)
    T = (d["tmax"] + d["tmin"]) / 2
    P, PET = d["ppt"], d["pet"]
    ok = K.mascara_valida(T, P, PET)
    lat = px["lat"]
    kp = np.zeros(len(lat), np.uint8)
    um = np.zeros(len(lat), np.uint8)
    hd = np.zeros(len(lat), np.uint8)
    kp[ok] = K.koppen(T[:, ok], P[:, ok], lat[ok])
    um[ok] = K.thornthwaite(P[:, ok], PET[:, ok], lat[ok], so_umidade=True)["umidade"]
    hd[ok] = K.holdridge(T[:, ok], P[:, ok], lat[ok], so_id=True)["id"]
    a = px["area"] * ok
    res = dict(koppen=pct_area(kp == px["koppen"], a), umidade=pct_area(um == px["th_umidade"], a),
               zona=pct_area(hd == px["holdridge"], a), cobertura=pct_area(ok, px["area"]),
               p_anual_dif_media=float(np.nanmean(P.sum(0)[ok] - px["v_p_anual"][ok])),
               t_anual_dif_media=float(np.nanmean(T.mean(0)[ok] - px["v_t_anual"][ok])))
    return res, kp


# ---------------------------------------------------------------------------
# 4. Sensibilidade
# ---------------------------------------------------------------------------
def etp_thornthwaite(T, lat):
    """ETP de Thornthwaite (1948), vetorizada, (12, N) -> (12, N) mm/mês."""
    dias = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])[:, None]
    dj = np.array([17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344])[:, None]
    Tp = np.maximum(T, 0)
    I = ((Tp / 5) ** 1.514).sum(0)
    a = 6.75e-7 * I ** 3 - 7.71e-5 * I ** 2 + 1.792e-2 * I + 0.49239
    etp = np.where(T > 0, 16 * (10 * Tp / np.maximum(I, 1e-6)) ** a, 0)
    etp = np.where(T >= 26.5, -415.85 + 32.24 * T - 0.43 * T ** 2, etp)
    dec = np.radians(23.45 * np.sin(np.radians(360 * (284 + dj) / 365)))
    ws = np.degrees(np.arccos(np.clip(-np.tan(np.radians(lat))[None] * np.tan(dec), -1, 1)))
    N = 2 / 15 * ws
    return etp * (N / 12) * (dias / 30)


def sensibilidade(px, vies_t=None):
    """Mesmos cenários do Paraguai: T ±0,5 °C e T corrigida pelo viés médio frente às estações,
    P ±10%, CAD 50 e 150 mm, ETP +10% e método da ETP."""
    T, P, PET, lat, area = px["tas"], px["pr"], px["pet"], px["lat"], px["area"]
    ref = dict(koppen=px["koppen"], umidade=px["th_umidade"], zona=px["holdridge"])
    muda = lambda k, novo: round(100 - pct_area(novo == ref[k], area), 2)
    r = {}
    cen_t = [("T-0.5", -0.5), ("T+0.5", 0.5)]
    if vies_t is not None:
        cen_t.append(("T_vies", -vies_t))   # viés = CHELSA − estação; corrigir = somar −viés
    for nome, dT in cen_t:
        r[nome] = dict(koppen=muda("koppen", K.koppen(T + dT, P, lat)),
                       zona=muda("zona", K.holdridge(T + dT, P, lat, so_id=True)["id"]), dT=round(dT, 2))
        print("  sensibilidade", nome, r[nome])
    r["ETP+10%"] = dict(umidade=muda("umidade", K.thornthwaite(P, PET * 1.1, lat, so_umidade=True)["umidade"]))
    for f in (0.9, 1.1):
        k = f"P{(f - 1) * 100:+.0f}%"
        r[k] = dict(koppen=muda("koppen", K.koppen(T, P * f, lat)),
                    umidade=muda("umidade", K.thornthwaite(P * f, PET, lat, so_umidade=True)["umidade"]),
                    zona=muda("zona", K.holdridge(T, P * f, lat, so_id=True)["id"]))
        print("  sensibilidade", k, r[k])
    for cad in (50, 150):
        r[f"CAD{cad}"] = dict(umidade=muda("umidade", K.thornthwaite(P, PET, lat, cad=cad, so_umidade=True)["umidade"]))
    r["ETP_metodo"] = dict(
        umidade=muda("umidade", K.thornthwaite(P, etp_thornthwaite(T, lat), lat, so_umidade=True)["umidade"]),
        zona=muda("zona", K.holdridge(T, P, lat, PET=PET, so_id=True)["id"]))
    print("  sensibilidade CAD/ETP", {k: r[k] for k in ("CAD50", "CAD150", "ETP+10%", "ETP_metodo")})
    return r


# ---------------------------------------------------------------------------
# 5. Ecorregiões
# ---------------------------------------------------------------------------
def ecorregioes(px):
    transform, crs, shape = C.grade()
    eco = gpd.read_file(f"zip://{EXT / 'resolve' / 'Ecoregions2017.zip'}!Ecoregions2017.shp",
                        bbox=(C.OESTE, C.SUL, C.LESTE, C.NORTE))
    eco = eco.reset_index(drop=True)
    eco["cod"] = np.arange(1, len(eco) + 1)
    g = rasterize(zip(eco.geometry, eco.cod), out_shape=shape, transform=transform, fill=0, dtype="int16")
    e = g[px["lin"], px["col"]]
    area, hd = px["area"], px["holdridge"]
    tot = area.sum()
    linhas = []
    for _, r in eco.iterrows():
        sel = e == r.cod
        a = area[sel].sum()
        if a / tot < 0.01:
            continue
        zonas = np.bincount(hd[sel], weights=area[sel], minlength=39)
        z = int(zonas.argmax())
        # quanto da zona dominante (no país) cai nesta ecorregião
        linhas.append(dict(ecorregiao=r.ECO_NAME, bioma=r.BIOME_NAME, pct_pais=round(100 * a / tot, 1),
                           zona=z, pct_zona_na_eco=round(100 * zonas[z] / a, 1),
                           pct_eco_na_zona=round(100 * zonas[z] / area[hd == z].sum(), 1)))
    tab = pd.DataFrame(linhas).sort_values("pct_pais", ascending=False)
    eco[eco.cod.isin(np.unique(e))][["ECO_NAME", "BIOME_NAME", "COLOR", "geometry"]].to_file(
        C.CLASSES_DIR / "ecorregioes_arg.gpkg", driver="GPKG")
    # concordância global: cada ecorregião "prevê" sua zona dominante
    mapa = {r.cod: 0 for _, r in eco.iterrows()}
    for _, r in eco.iterrows():
        sel = e == r.cod
        if sel.any():
            mapa[r.cod] = int(np.bincount(hd[sel], weights=area[sel], minlength=39).argmax())
    prev = np.vectorize(lambda c: mapa.get(c, 0))(e)
    return dict(tabela=tab.to_dict("records"), concordancia=pct_area((prev == hd) & (e > 0), area * (e > 0)))


def main():
    px = dict(np.load(C.CLASSES_DIR / "pixels.npz"))
    out = {}
    print("1. estações");       out["estacoes"] = estacoes(None); print(out["estacoes"])
    print("1b. estações (P)");  out["estacoes_precip"] = estacoes_precip(); print(out["estacoes_precip"])
    print("2. Beck");           out["beck"], bk = beck(px, None); print({k: v for k, v in out["beck"].items() if k != "confusao"})
    print("3. TerraClimate");   out["terraclimate"], tck = terraclimate(px); print(out["terraclimate"])
    print("4. sensibilidade");  out["sensibilidade"] = sensibilidade(px, out["estacoes"]["vies_medio"])
    print("5. ecorregiões");    out["ecorregioes"] = ecorregioes(px); print(pd.DataFrame(out["ecorregioes"]["tabela"]).to_string())
    np.savez_compressed(C.CLASSES_DIR / "validacao_pixels.npz", beck=bk, tc_koppen=tck)
    (C.CLASSES_DIR / "validacao.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
