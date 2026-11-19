# -*- coding: utf-8 -*-
"""Análises e figuras do artigo (Meteorologica), na mesma linha do artigo do Paraguai.

Calcula: cidades de referência; validação nas estações (ME, MAE, RMSE, r, d, c) do CHELSA e do
TerraClimate (temperatura: GHCN-Daily; precipitação: NOAA GSOD); classificação das estações;
comparação com Beck et al. (2023) e com o TerraClimate; ecorregiões e V de Cramér; estabilidade por
classe e série anual de áreas com tendência; normais 1991-2005 x 2006-2020; composição por
província/departamento. Grava artigo/resultados_artigo.json e artigo/figuras/Figura_N.png.
"""
import gzip
import json
import re
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import requests  # noqa: E402
from matplotlib.colors import ListedColormap, BoundaryNorm, TwoSlopeNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from rasterio.features import rasterize  # noqa: E402
from rasterio.warp import reproject, Resampling  # noqa: E402
from scipy import stats  # noqa: E402

import classif as K  # noqa: E402
import config as C  # noqa: E402
from agrometeorologiapy.classificacao_climatica import KOPPEN_CLASSES  # noqa: E402

ART = C.RAIZ / "artigo"
FIG = ART / "figuras"
EXT = C.EXTERNOS_DIR
CACHE = C.BRUTOS / "artigo_cache"
LEG = json.loads((C.RAIZ / "processamento" / "legendas_base.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
DPI = 300
R = {}   # resultados para o texto

CIDADES = [  # nome, lat, lon
    ("La Quiaca", -22.10, -65.60), ("Salta", -24.85, -65.48), ("Posadas", -27.39, -55.97),
    ("Resistencia", -27.45, -59.05), ("Córdoba", -31.32, -64.21), ("Mendoza", -32.83, -68.78),
    ("Buenos Aires", -34.58, -58.48), ("Bahía Blanca", -38.73, -62.17), ("Neuquén", -38.95, -68.13),
    ("S. C. de Bariloche", -41.15, -71.16), ("Comodoro Rivadavia", -45.78, -67.50), ("Ushuaia", -54.80, -68.32),
]
REGIOES = {"NOA": ["Jujuy", "Salta", "Tucumán", "Catamarca", "Santiago del Estero", "La Rioja"],
           "NEA": ["Misiones", "Corrientes", "Chaco", "Formosa"],
           "Cuyo": ["Mendoza", "San Juan", "San Luis"],
           "Pampeana": ["Buenos Aires", "Ciudad de Buenos Aires", "Córdoba", "Santa Fe", "Entre Ríos", "La Pampa"],
           "Patagonia": ["Neuquén", "Río Negro", "Chubut", "Santa Cruz", "Tierra del Fuego"]}
COR_REG = {"NOA": "#f4d6a0", "NEA": "#bfe3b4", "Cuyo": "#f2b8a2", "Pampeana": "#fdf3b0", "Patagonia": "#c9dcf0"}


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------
def metricas(est, obs):
    est, obs = np.asarray(est, float), np.asarray(obs, float)
    ok = np.isfinite(est) & np.isfinite(obs)
    e, o = est[ok], obs[ok]
    me = np.mean(e - o)
    mae = np.mean(np.abs(e - o))
    rmse = np.sqrt(np.mean((e - o) ** 2))
    r = np.corrcoef(e, o)[0, 1]
    om = o.mean()
    d = 1 - np.sum((e - o) ** 2) / np.sum((np.abs(e - om) + np.abs(o - om)) ** 2)
    return dict(n=int(ok.sum()), ME=me, MAE=mae, RMSE=rmse, r=r, d=d, c=r * d)


def desempenho(c):
    for lim, nome in ((0.85, "Óptimo"), (0.75, "Muy bueno"), (0.65, "Bueno"), (0.60, "Mediano"),
                      (0.50, "Tolerable"), (0.40, "Malo")):
        if c > lim:
            return nome
    return "Pésimo"


def nome_classe(camada, c, lg="es"):
    return LEG[camada + "_todas"][str(int(c))]["nome"][lg]


def letra(camada, c):
    return nome_classe(camada, c).split(" — ")[0]


def area_pct(cod, area, mask=None):
    m = np.ones(len(cod), bool) if mask is None else mask
    tot = area[m & (cod > 0)].sum()
    v = np.bincount(cod[m].astype(int), weights=area[m], minlength=256)
    v[0] = 0
    return {int(c): 100 * v[c] / tot for c in np.argsort(-v) if v[c] > 0}


def cramer_v(a, b, w):
    ua, ia = np.unique(a, return_inverse=True)
    ub, ib = np.unique(b, return_inverse=True)
    tab = np.zeros((len(ua), len(ub)))
    np.add.at(tab, (ia, ib), w)
    tab = tab / tab.sum() * len(a)   # contagem equivalente em pixels
    chi2 = stats.chi2_contingency(tab, correction=False)[0]
    return float(np.sqrt(chi2 / (len(a) * (min(tab.shape) - 1))))


class Mapa:
    def __init__(self, px):
        self.px = px
        transform, _, shape = C.grade()
        self.tr = transform
        l0, l1 = px["lin"].min(), px["lin"].max() + 1
        c0, c1 = px["col"].min(), px["col"].max() + 1
        self.l0, self.c0, self.sh = l0, c0, (l1 - l0, c1 - c0)
        self.ext = [transform.c + c0 * transform.a, transform.c + c1 * transform.a,
                    transform.f + l1 * transform.e, transform.f + l0 * transform.e]
        self.prov = gpd.read_file(C.SITE_DADOS / "provincias.geojson")

    def grade(self, v, fill=np.nan):
        g = np.full(self.sh, fill, "float32")
        g[self.px["lin"] - self.l0, self.px["col"] - self.c0] = v
        return g

    def eixo(self, ax, letra_=None, titulo=None):
        self.prov.boundary.plot(ax=ax, color="#333", linewidth=0.3)
        ax.set_xlim(self.ext[0], self.ext[1])
        ax.set_ylim(self.ext[2], self.ext[3])
        ax.set_aspect(1 / np.cos(np.radians(38)))
        ax.tick_params(labelsize=6)
        ax.set_xticks([-70, -65, -60, -55])
        ax.set_xticklabels(["70° O", "65° O", "60° O", "55° O"])
        ax.set_yticks(range(-55, -20, 5))
        ax.set_yticklabels([f"{-y}° S" for y in range(-55, -20, 5)])
        ax.grid(color="#bbb", lw=0.3, ls=":")
        if letra_ or titulo:
            ax.set_title(f"({letra_}) {titulo}" if letra_ else titulo, fontsize=8, fontweight="bold", loc="left")

    def classes(self, ax, cod, camada, letra_=None, titulo=None, leg_min=0.3, ncol=1, leg_fs=5.5, loc="lower right",
                nomes_curtos=False, abaixo=False):
        cores = ["#ffffff"] * 256
        pct = area_pct(cod, self.px["area"])
        for c in pct:
            cores[c] = LEG[camada + "_todas"][str(c)]["cor"]
        g = self.grade(cod.astype("float32"), np.nan)
        g[g == 0] = np.nan
        ax.imshow(g, extent=self.ext, cmap=ListedColormap(cores), norm=BoundaryNorm(np.arange(257) - 0.5, 256),
                  interpolation="nearest")
        self.eixo(ax, letra_, titulo)
        h = []
        for c in sorted(pct):
            if pct[c] >= leg_min:
                n = letra(camada, c) if nomes_curtos else nome_classe(camada, c)
                h.append(Patch(facecolor=cores[c], edgecolor="#333", lw=0.3, label=f"{n} ({pct[c]:.1f}%)".replace(".", ",")))
        if abaixo:
            ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=leg_fs, ncol=ncol,
                      frameon=False, handlelength=1, handleheight=0.8, labelspacing=0.3, columnspacing=0.8)
        else:
            ax.legend(handles=h, loc=loc, fontsize=leg_fs, ncol=ncol, frameon=True, framealpha=0.9,
                      handlelength=1, handleheight=0.8, borderpad=0.3, labelspacing=0.25)
        return pct

    def continuo(self, ax, v, cmap, un, letra_=None, titulo=None, vmin=None, vmax=None, norm=None, contorno=None,
                 abaixo=False):
        g = self.grade(v)
        im = ax.imshow(g, extent=self.ext, cmap=cmap, vmin=None if norm else vmin, vmax=None if norm else vmax,
                       norm=norm, interpolation="nearest")
        if contorno is not None:
            ax.contour(g, levels=[contorno], colors="k", linewidths=0.6,
                       extent=[self.ext[0], self.ext[1], self.ext[3], self.ext[2]], origin="upper")
        self.eixo(ax, letra_, titulo)
        cb = (plt.colorbar(im, ax=ax, orientation="horizontal", shrink=0.8, pad=0.05, aspect=25) if abaixo
              else plt.colorbar(im, ax=ax, shrink=0.55, pad=0.02))
        cb.set_label(un, fontsize=7)
        cb.ax.tick_params(labelsize=6)
        return im


def salvar(fig, n):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"Figura_{n}.png", dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def pixel_proximo(px, lat, lon, transform):
    inv = ~transform
    c, l = inv * (lon, lat)
    d = (px["lin"] - int(l)) ** 2 + (px["col"] - int(c)) ** 2
    i = int(np.argmin(d))
    return i, float(np.sqrt(d[i]))


# ---------------------------------------------------------------------------
# estações
# ---------------------------------------------------------------------------
def series_ghcn():
    pasta = EXT / "ghcn"
    st = pd.read_fwf(pasta / "ghcnd-stations.txt", colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (41, 71)],
                     names=["id", "lat", "lon", "elev", "nome"]).set_index("id")
    out = {}
    for arq in sorted(pasta.glob("AR*.csv.gz")):
        i = arq.name[:11]
        with gzip.open(arq, "rt") as f:
            d = pd.read_csv(f, header=None, usecols=[1, 2, 3, 5], names=["data", "el", "v", "q"], dtype=str)
        d = d[d.el.isin(["TAVG", "TMAX", "TMIN"]) & d.q.isna() & d.data.between("19910101", "20201231")]
        if d.empty:
            continue
        d["v"] = d.v.astype(float) / 10
        p = d.pivot_table(index="data", columns="el", values="v", aggfunc="first")
        t = p["TAVG"] if "TAVG" in p else pd.Series(np.nan, index=p.index)
        if "TMAX" in p and "TMIN" in p:
            t = t.fillna((p["TMAX"] + p["TMIN"]) / 2)
        t = t.dropna()
        idx = pd.to_datetime(t.index, format="%Y%m%d")
        g = t.groupby([idx.year, idx.month])
        m = g.mean()[g.count() >= 20]                       # >= 20 dias (Beck et al., 2023)
        if len(m) >= 60:
            out[i] = dict(serie=m, nome=st.loc[i, "nome"].strip().title(), lat=float(st.loc[i, "lat"]),
                          lon=float(st.loc[i, "lon"]), elev=float(st.loc[i, "elev"]), wmo=i[-5:])
    return out


def series_gsod():
    pasta = EXT / "gsod"
    h = pd.read_csv(pasta / "isd-history.csv", dtype=str)
    h = h[(h.CTRY == "AR") & (h.END >= "20150101") & (h.BEGIN <= "19960101")]
    out = {}
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
        seco = (oc.str[1] == "0") & (oc.str[2] == "0")
        d = d[(d.p < 99) & (fl.isin(["D", "E", "F", "G"]) | ((fl == "I") & seco))]
        if d.empty:
            continue
        dt = pd.to_datetime(d.DATE)
        g = (d.p * 25.4).groupby([dt.dt.year, dt.dt.month])
        n, s = g.count(), g.sum()
        dias = pd.Series([pd.Period(f"{a}-{m:02d}").days_in_month for a, m in n.index], index=n.index)
        m = (s / n * dias)[n >= 27]
        if len(m) >= 60:
            out[i] = dict(serie=m, nome=r["STATION NAME"].title(), lat=float(r.LAT), lon=float(r.LON),
                          elev=float(r["ELEV(M)"]), wmo=r.USAF[:5])
    return out


TC_LAT0, TC_LON0, TC_RES = 81.51652777766667, -179.98347222222134, 1 / 30


def tc_ponto(var, ano, lat, lon):
    arq = CACHE / "tc" / f"{var}_{ano}_{lat:.3f}_{lon:.3f}.txt"
    if arq.exists():
        return [float(x) for x in arq.read_text().split()]
    r = int(round((TC_LAT0 - lat) / TC_RES))
    c = int(round((lon - TC_LON0) / TC_RES))
    url = (f"http://thredds.northwestknowledge.net:8080/thredds/dodsC/TERRACLIMATE_ALL/data/"
           f"TerraClimate_{var}_{ano}.nc.ascii?{var}%5B0:11%5D%5B{r}%5D%5B{c}%5D")
    for _ in range(4):
        try:
            t = requests.get(url, timeout=60).text
            vals = [int(x) for x in re.findall(r"\]\[0\], (-?\d+)", t)][:12]
            if len(vals) == 12:
                break
        except requests.RequestException:
            pass
    else:
        vals = [None] * 12
    esc, off, fill = {"tmax": (0.01, -99, -32768), "tmin": (0.01, -99, -32768), "ppt": (0.1, 0, -2147483648)}[var]
    out = [np.nan if (v is None or v == fill) else v * esc + off for v in vals]
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(" ".join(str(x) for x in out))
    return out


def tc_series(estacoes, vars_):
    tarefas = [(v, a, e["lat"], e["lon"]) for e in estacoes.values() for v in vars_ for a in C.ANOS]
    with ThreadPoolExecutor(12) as ex:
        res = dict(zip(tarefas, ex.map(lambda t: tc_ponto(*t), tarefas)))
    out = {}
    for k, e in estacoes.items():
        s = {}
        for a in C.ANOS:
            for m in range(12):
                vals = [res[(v, a, e["lat"], e["lon"])][m] for v in vars_]
                s[(a, m + 1)] = np.mean(vals) if len(vars_) == 2 else vals[0]
        out[k] = pd.Series(s)
    return out


def chelsa_series(estacoes, var):
    transform, _, shape = C.grade()
    inv = ~transform
    pos = {}
    for k, e in estacoes.items():
        c, l = inv * (e["lon"], e["lat"])
        pos[k] = (int(l), int(c))
    out = {k: {} for k in estacoes}
    for a in C.ANOS:
        for m in range(1, 13):
            g = C.ler_mensal(var, a, m)
            for k, (l, c) in pos.items():
                out[k][(a, m)] = g[l, c] if 0 <= l < shape[0] and 0 <= c < shape[1] else np.nan
    return {k: pd.Series(v) for k, v in out.items()}


def climatologia(s, minimo=3):
    mes = s.index.get_level_values(1)
    g = s.groupby(mes)
    c = g.mean()
    c[g.count() < minimo] = np.nan
    return c.reindex(range(1, 13))


def validacao_estacoes(px):
    import pickle
    cache = CACHE / "estacoes.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    T = series_ghcn()
    P = series_gsod()
    print(f"  estações T: {len(T)}, P: {len(P)}")
    chT, chP = chelsa_series(T, "tas"), chelsa_series(P, "pr")
    tcT, tcP = tc_series(T, ["tmax", "tmin"]), tc_series(P, ["ppt"])
    out = dict(T=T, P=P, chT=chT, chP=chP, tcT=tcT, tcP=tcP)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(out))
    return out


# ---------------------------------------------------------------------------
def main():
    px = dict(np.load(C.CLASSES_DIR / "pixels.npz"))
    est = dict(np.load(C.CLASSES_DIR / "estabilidade.npz"))
    vpx = dict(np.load(C.CLASSES_DIR / "validacao_pixels.npz"))
    val = json.loads((C.CLASSES_DIR / "validacao.json").read_text(encoding="utf-8"))
    transform, crs, shape = C.grade()
    M = Mapa(px)
    area = px["area"].astype("float64")
    km2 = (111.32 / 120) ** 2 * area      # área do pixel (km²), Eq. 18
    R["area_pais_km2"] = float(km2.sum())
    R["n_pixels"] = int(len(area))
    R["grade"] = dict(linhas=int(shape[0]), colunas=int(shape[1]))
    nac = {k: area_pct(px[c], area) for k, c in (("koppen", "koppen"), ("umidade", "th_umidade"),
           ("subtipo", "th_subtipo"), ("termica", "th_termica"), ("concentracao", "th_concentracao"),
           ("holdridge", "holdridge"))}
    R["nacional"] = {k: {letra({"koppen": "koppen", "umidade": "th_umidade", "subtipo": "th_subtipo",
                                "termica": "th_termica", "concentracao": "th_concentracao"}.get(k, "holdridge"), c)
                         if k != "holdridge" else nome_classe("holdridge", c): round(p, 1) for c, p in v.items()}
                     for k, v in nac.items()}

    # ------------------------------------------------ variáveis
    for k in ("v_p_anual", "v_t_anual", "v_pet_anual", "v_p_mes_seco", "v_t_mes_frio", "hd_biotemperatura",
              "hd_razao_ETP", "th_Im", "th_DEF_anual", "th_EXC_anual"):
        v = px[k]
        R[k] = dict(min=float(np.nanmin(v)), max=float(np.nanmax(v)), mediana=float(np.nanmedian(v)),
                    p1=float(np.nanpercentile(v, 1)), p99=float(np.nanpercentile(v, 99)))
    R["pct_P_menor_ETP"] = float(100 * area[px["v_p_anual"] < px["v_pet_anual"]].sum() / area.sum())
    R["pct_P_menor_300"] = float(100 * area[px["v_p_anual"] < 300].sum() / area.sum())

    # ------------------------------------------------ regiões
    tab = pd.read_csv(C.GADM_DIR / "unidades.csv")
    prov_de = dict(zip(tab.indice, tab.provincia))
    reg_de_prov = {p: r for r, ps in REGIOES.items() for p in ps}
    mapa_prov = np.array([""] + [prov_de.get(u, "") for u in range(1, int(px["unidade"].max()) + 1)], dtype=object)
    prov_px = mapa_prov[px["unidade"]]
    mapa_reg = np.array([reg_de_prov.get(p, "?") for p in mapa_prov], dtype=object)
    reg_px = mapa_reg[px["unidade"]]
    R["regioes"] = {}
    for rg in REGIOES:
        m = reg_px == rg
        R["regioes"][rg] = dict(
            pct_pais=float(100 * area[m].sum() / area.sum()),
            koppen={letra("koppen", c): round(p, 1) for c, p in list(area_pct(px["koppen"], area, m).items())[:5]},
            umidade={letra("th_umidade", c): round(p, 1) for c, p in list(area_pct(px["th_umidade"], area, m).items())[:5]},
            holdridge={nome_classe("holdridge", c): round(p, 1) for c, p in list(area_pct(px["holdridge"], area, m).items())[:5]},
            p_anual=float(np.average(px["v_p_anual"][m], weights=area[m])),
            t_anual=float(np.average(px["v_t_anual"][m], weights=area[m])))

    # ------------------------------------------------ cidades
    cid = []
    for nome, la, lo in CIDADES:
        i, dist = pixel_proximo(px, la, lo, transform)
        cid.append(dict(nome=nome, lat=la, lon=lo, dist_px=dist, i=i,
                        tas=px["tas"][:, i].tolist(), pr=px["pr"][:, i].tolist(), pet=px["pet"][:, i].tolist(),
                        T=float(px["v_t_anual"][i]), P=float(px["v_p_anual"][i]), ETP=float(px["v_pet_anual"][i]),
                        Tfrio=float(px["v_t_mes_frio"][i]), Pseco=float(px["v_p_mes_seco"][i]),
                        koppen=letra("koppen", px["koppen"][i]),
                        tipo_th=letra("th_umidade", px["th_umidade"][i]) + letra("th_subtipo", px["th_subtipo"][i])
                        + letra("th_termica", px["th_termica"][i]) + letra("th_concentracao", px["th_concentracao"][i]),
                        Im=float(px["th_Im"][i]), DEF=float(px["th_DEF_anual"][i]), EXC=float(px["th_EXC_anual"][i]),
                        holdridge=nome_classe("holdridge", px["holdridge"][i]),
                        biot=float(px["hd_biotemperatura"][i]), razao=float(px["hd_razao_ETP"][i]),
                        prov=prov_px[i]))
    R["cidades"] = [{k: v for k, v in c.items() if k not in ("i",)} for c in cid]
    CI = {c["nome"]: c for c in cid}

    # ------------------------------------------------ estabilidade por classe e série anual
    anos_cls = {a: dict(np.load(C.ANUAL_DIR / f"classes_{a}.npz")) for a in C.ANOS}
    estab = {}
    for k, ref, chave in (("koppen", px["koppen"], "koppen"), ("umidade", px["th_umidade"], "umidade"),
                          ("zona", px["holdridge"], "zona")):
        e = est[k]
        ok = np.isfinite(e)
        porc = {}
        for c, p in area_pct(ref, area).items():
            m = (ref == c) & ok
            if p >= 1:
                porc[c] = float(np.average(e[m], weights=area[m]))
        anos_k = [a for a in C.ANOS if chave in anos_cls[a]]
        pilha = np.stack([anos_cls[a][chave] for a in anos_k])
        # classe mais frequente nos anos
        maxc = int(pilha.max()) + 1
        cont = np.zeros((maxc, pilha.shape[1]), np.int16)
        for a in range(len(anos_k)):
            cont[pilha[a], np.arange(pilha.shape[1])] += 1
        moda = cont.argmax(0)
        serie = {}
        for c in np.unique(pilha):
            if c == 0:
                continue
            s = [100 * area[pilha[a] == c].sum() / area.sum() for a in range(len(anos_k))]
            serie[int(c)] = s
        tend = {}
        for c, s in serie.items():
            if np.mean(s) >= 3:
                lr = stats.linregress(anos_k, s)
                tend[int(c)] = dict(media=float(np.mean(s)), min=float(np.min(s)), max=float(np.max(s)),
                                    decada=float(lr.slope * 10), p=float(lr.pvalue))
        estab[k] = dict(media=float(np.average(e[ok], weights=area[ok])),
                        pct_ge80=float(100 * area[ok & (e >= 80)].sum() / area[ok].sum()),
                        pct_lt50=float(100 * area[ok & (e < 50)].sum() / area[ok].sum()),
                        moda_igual=float(100 * area[moda == ref].sum() / area.sum()),
                        por_classe=porc, tendencia=tend, anos=anos_k, serie=serie)
    camada_de = {"koppen": "koppen", "umidade": "th_umidade", "zona": "holdridge"}
    R["estabilidade"] = {k: dict(media=v["media"], pct_ge80=v["pct_ge80"], pct_lt50=v["pct_lt50"],
                                 moda_igual=v["moda_igual"],
                                 por_classe={(letra(camada_de[k], c) if k != "zona" else nome_classe("holdridge", c)): round(p, 1)
                                             for c, p in v["por_classe"].items()},
                                 tendencia={(letra(camada_de[k], c) if k != "zona" else nome_classe("holdridge", c)): t
                                            for c, t in v["tendencia"].items()})
                         for k, v in estab.items()}
    print("estabilidade ok")

    # ------------------------------------------------ normais de 15 anos
    lin, col = px["lin"], px["col"]
    metades = {}
    anterior = ART / "resultados_artigo.json"
    sem_mensal = not C.caminho_mensal("tas", 1991, 1).exists()
    if sem_mensal and anterior.exists():   # recortes mensais só no Release: reaproveita o resultado anterior
        R["metades"] = json.loads(anterior.read_text(encoding="utf-8"))["metades"]
        print("metades: reaproveitadas de resultados_artigo.json")
    for nome, anos in ((() if sem_mensal else (("1991-2005", range(1991, 2006)), ("2006-2020", range(2006, 2021))))):
        acc = {}
        for v in C.VARIAVEIS:
            soma = np.zeros((12, len(lin)))
            n = np.zeros((12, len(lin)))
            for a in anos:
                for m in range(1, 13):
                    d = C.ler_mensal(v, a, m)
                    if d is None:
                        continue
                    x = d[lin, col]
                    ok = np.isfinite(x)
                    soma[m - 1, ok] += x[ok]
                    n[m - 1, ok] += 1
            acc[v] = (soma / np.maximum(n, 1)).astype("float32")
        Tm, Pm, Em = acc["tas"], acc["pr"], acc["pet"]
        metades[nome] = dict(T=Tm.mean(0), P=Pm.sum(0), kp=K.koppen(Tm, Pm, px["lat"]),
                             um=K.thornthwaite(Pm, Em, px["lat"], so_umidade=True)["umidade"],
                             hd=K.holdridge(Tm, Pm, px["lat"], so_id=True)["id"])

    def transicoes(x1, x2, cam, n=6):
        m = x1 != x2
        pares = pd.Series(area[m], index=pd.MultiIndex.from_arrays([x1[m], x2[m]])).groupby(level=[0, 1]).sum()
        pares = (100 * pares / area.sum()).sort_values(ascending=False).head(n)
        f = (lambda c: letra(cam, c)) if cam != "holdridge" else (lambda c: nome_classe("holdridge", c))
        return {f"{f(a)} → {f(b)}": round(float(p), 2) for (a, b), p in pares.items()}
    grupo = lambda x: np.array([KOPPEN_CLASSES.get(int(c), "?")[0] for c in range(32)])[x]
    if not sem_mensal:
        a1, a2 = metades["1991-2005"], metades["2006-2020"]
        R["metades"] = dict(
            dT=float(np.average(a2["T"] - a1["T"], weights=area)), dP=float(np.average(a2["P"] - a1["P"], weights=area)),
            koppen=float(100 * area[a1["kp"] != a2["kp"]].sum() / area.sum()),
            umidade=float(100 * area[a1["um"] != a2["um"]].sum() / area.sum()),
            holdridge=float(100 * area[a1["hd"] != a2["hd"]].sum() / area.sum()),
            grupos={g: [float(100 * area[grupo(a1["kp"]) == g].sum() / area.sum()),
                        float(100 * area[grupo(a2["kp"]) == g].sum() / area.sum())] for g in "ABCDE"},
            trans_koppen=transicoes(a1["kp"], a2["kp"], "koppen"),
            trans_umidade=transicoes(a1["um"], a2["um"], "th_umidade"),
            trans_holdridge=transicoes(a1["hd"], a2["hd"], "holdridge"))
    print("metades ok")

    # ------------------------------------------------ Beck: 1961-1990 x 1991-2020
    import zipfile
    zf = EXT / "beck" / "koppen_geiger_tif.zip"
    alvo = EXT / "beck" / "1961_1990" / "koppen_geiger_0p00833333.tif"
    if not alvo.exists():
        with zipfile.ZipFile(zf) as z:
            z.extract("1961_1990/koppen_geiger_0p00833333.tif", EXT / "beck")
    from p08_validacao import BECK, KOPPEN_ID
    conv = np.zeros(256, np.uint8)
    for k_, v_ in BECK.items():
        conv[k_] = KOPPEN_ID[v_]
    g = np.full(shape, np.nan, np.float32)
    with rasterio.open(alvo) as src:
        reproject(rasterio.band(src, 1), g, dst_transform=transform, dst_crs=crs, resampling=Resampling.nearest,
                  dst_nodata=np.nan)
    b61 = conv[np.nan_to_num(g[lin, col], nan=0).astype(np.uint8)]
    b91 = vpx["beck"]
    ok = (b61 > 0) & (b91 > 0)
    R["beck"] = dict(val["beck"])
    R["beck"]["mudanca_6190_9120"] = float(100 * area[ok & (b61 != b91)].sum() / area[ok].sum())
    R["beck"]["trans_6190_9120"] = transicoes(np.where(ok, b61, 0), np.where(ok, b91, 0), "koppen", 5)
    R["beck"]["area_beck"] = {letra("koppen", c): round(p, 1) for c, p in list(area_pct(b91, area).items())[:8]}

    # ------------------------------------------------ TerraClimate (normal): todas as camadas
    tc_norm = {}
    for v in ("ppt", "tmax", "tmin", "pet"):
        arq = f"netcdf:{EXT / 'terraclimate' / f'TerraClimate_19912020_{v}.nc'}:{v}"
        meses = []
        with rasterio.open(arq) as src:
            esc, off = src.scales[0], src.offsets[0]
            for m in range(1, 13):
                out = np.full(shape, np.nan, np.float32)
                reproject(rasterio.band(src, m), out, src_crs=src.crs or "EPSG:4326", dst_transform=transform,
                          dst_crs=crs, resampling=Resampling.nearest, dst_nodata=np.nan)
                meses.append(out[lin, col] * esc + off)
        tc_norm[v] = np.stack(meses)
    Ttc = (tc_norm["tmax"] + tc_norm["tmin"]) / 2
    Ptc, Etc = tc_norm["ppt"], tc_norm["pet"]
    okt = K.mascara_valida(Ttc, Ptc, Etc)
    n = len(lin)
    tc = {k: np.zeros(n, np.uint8) for k in ("kp", "um", "sub", "ter", "hd")}
    tc["kp"][okt] = K.koppen(Ttc[:, okt], Ptc[:, okt], px["lat"][okt])
    th_tc = K.thornthwaite(Ptc[:, okt], Etc[:, okt], px["lat"][okt])
    tc["um"][okt], tc["sub"][okt], tc["ter"][okt] = th_tc["umidade"], th_tc["subtipo"], th_tc["termica"]
    tc["hd"][okt] = K.holdridge(Ttc[:, okt], Ptc[:, okt], px["lat"][okt], so_id=True)["id"]
    a_ok = area * okt
    conc = lambda a, b: float(100 * a_ok[a == b].sum() / a_ok.sum())
    Pa_tc = Ptc.sum(0)
    R["terraclimate"] = dict(
        koppen=conc(tc["kp"], px["koppen"]), umidade=conc(tc["um"], px["th_umidade"]),
        subtipo=conc(tc["sub"], px["th_subtipo"]), termica=conc(tc["ter"], px["th_termica"]),
        holdridge=conc(tc["hd"], px["holdridge"]),
        dP_mm=float(np.average((Pa_tc - px["v_p_anual"])[okt], weights=area[okt])),
        dP_pct=float(100 * np.average((Pa_tc - px["v_p_anual"])[okt], weights=area[okt]) /
                     np.average(px["v_p_anual"][okt], weights=area[okt])),
        r_P=float(np.corrcoef(Pa_tc[okt], px["v_p_anual"][okt])[0, 1]),
        dTfrio=float(np.average((Ttc.min(0) - px["v_t_mes_frio"])[okt], weights=area[okt])),
        rmse_Tfrio=float(np.sqrt(np.average(((Ttc.min(0) - px["v_t_mes_frio"]) ** 2)[okt], weights=area[okt]))),
        dPET=float(np.average((Etc.sum(0) - px["v_pet_anual"])[okt], weights=area[okt])),
        area_kp={letra("koppen", c): round(p, 1) for c, p in list(area_pct(tc["kp"], area, okt).items())[:8]},
        area_um={letra("th_umidade", c): round(p, 1) for c, p in area_pct(tc["um"], area, okt).items()},
        area_ter={letra("th_termica", c): round(p, 1) for c, p in area_pct(tc["ter"], area, okt).items()},
        trans_koppen=transicoes(np.where(okt, px["koppen"], 0), tc["kp"], "koppen", 5))
    print("terraclimate ok")

    # ------------------------------------------------ ecorregiões e V de Cramér
    eco = gpd.read_file(f"zip://{EXT / 'resolve' / 'Ecoregions2017.zip'}!Ecoregions2017.shp",
                        bbox=(C.OESTE, C.SUL, C.LESTE, C.NORTE)).reset_index(drop=True)
    eco["cod"] = np.arange(1, len(eco) + 1)
    ge = rasterize(zip(eco.geometry, eco.cod), out_shape=shape, transform=transform, fill=0, dtype="int16")
    e_px = ge[lin, col]
    eco_tab = []
    for _, r in eco.iterrows():
        m = e_px == r.cod
        if area[m].sum() / area.sum() < 0.02:
            continue
        zh = area_pct(px["holdridge"], area, m)
        zu = area_pct(px["th_umidade"], area, m)
        z1 = list(zh.items())[:2]
        u1 = list(zu.items())[:2]
        eco_tab.append(dict(eco=r.ECO_NAME, pct_pais=float(100 * area[m].sum() / area.sum()),
                            holdridge=[(nome_classe("holdridge", c), round(p, 1)) for c, p in z1],
                            umidade=[(letra("th_umidade", c), round(p, 1)) for c, p in u1]))
    R["ecorregioes"] = dict(tabela=sorted(eco_tab, key=lambda x: -x["pct_pais"]),
                            concordancia=val["ecorregioes"]["concordancia"])
    am = np.random.default_rng(0).choice(n, size=min(n, 600_000), replace=False)
    R["cramer"] = dict(kp_hd=cramer_v(px["koppen"][am], px["holdridge"][am], area[am]),
                       th_hd=cramer_v(px["th_umidade"][am], px["holdridge"][am], area[am]),
                       kp_th=cramer_v(px["koppen"][am], px["th_umidade"][am], area[am]))
    print("ecorregiões ok", R["cramer"])

    # ------------------------------------------------ composição por departamento e província
    comp = json.loads((C.SITE_DADOS / "composicao_departamentos.json").read_text(encoding="utf-8"))
    n5 = {k: sum(1 for d in comp.values() if sum(1 for c, p in d[k] if p >= 5) >= 2)
          for k in ("koppen", "th_umidade", "holdridge")}
    R["deptos"] = dict(n=len(comp), multi5=n5,
                       max_classes={k: max(sum(1 for c, p in d[k] if p >= 5) for d in comp.values())
                                    for k in ("koppen", "th_umidade", "holdridge")})
    provs = sorted(set(prov_px), key=lambda p: -np.average(px["lat"][prov_px == p]))
    R["provincias"] = {p: dict(koppen={letra("koppen", c): round(v, 1) for c, v in list(area_pct(px["koppen"], area, prov_px == p).items())[:4]},
                               umidade={letra("th_umidade", c): round(v, 1) for c, v in list(area_pct(px["th_umidade"], area, prov_px == p).items())[:4]},
                               n_kp5=sum(1 for v in area_pct(px["koppen"], area, prov_px == p).values() if v >= 5),
                               n_um5=sum(1 for v in area_pct(px["th_umidade"], area, prov_px == p).values() if v >= 5))
                       for p in provs}

    # ------------------------------------------------ validação nas estações
    V = validacao_estacoes(px)
    T, P, chT, chP, tcT, tcP = V["T"], V["P"], V["chT"], V["chP"], V["tcT"], V["tcP"]
    pares = {"T": {"ch": ([], []), "tc": ([], [])}, "P": {"ch": ([], []), "tc": ([], [])}}
    clim = {"T": {"ch": ([], []), "tc": ([], [])}, "P": {"ch": ([], []), "tc": ([], [])}}
    vies_T, vies_P = [], []
    for nomev, E, CH, TC in (("T", T, chT, tcT), ("P", P, chP, tcP)):
        for k, e in E.items():
            s = e["serie"]
            ch = CH[k].reindex(s.index)
            tcs = TC[k].reindex(s.index)
            ok = ch.notna() & tcs.notna() & s.notna()
            if ok.sum() < 24:
                continue
            for prod, serie in (("ch", ch), ("tc", tcs)):
                pares[nomev][prod][0].extend(serie[ok])
                pares[nomev][prod][1].extend(s[ok])
                cs, co = climatologia(serie[ok]), climatologia(s[ok])
                okc = cs.notna() & co.notna()
                clim[nomev][prod][0].extend(cs[okc])
                clim[nomev][prod][1].extend(co[okc])
            if nomev == "T":
                vies_T.append(dict(id=k, nome=e["nome"], lat=e["lat"], lon=e["lon"], elev=e["elev"], n=int(ok.sum()),
                                   ch=float((ch[ok] - s[ok]).mean()), tc=float((tcs[ok] - s[ok]).mean())))
            else:
                so, co_, to = climatologia(s[ok]), climatologia(ch[ok]), climatologia(tcs[ok])
                if so.notna().all() and so.sum() > 50:
                    vies_P.append(dict(id=k, nome=e["nome"], lat=e["lat"], lon=e["lon"], elev=e["elev"], n=int(ok.sum()),
                                       Pest=float(so.sum()), ch=float(100 * (co_.sum() - so.sum()) / so.sum()),
                                       tc=float(100 * (to.sum() - so.sum()) / so.sum())))
    vT, vP = pd.DataFrame(vies_T), pd.DataFrame(vies_P)
    met = {}
    for nomev in ("T", "P"):
        for prod in ("ch", "tc"):
            met[f"{nomev}_{prod}_mensal"] = metricas(*pares[nomev][prod])
            met[f"{nomev}_{prod}_clim"] = metricas(*clim[nomev][prod])
    R["validacao"] = dict(
        n_T=len(vT), n_P=len(vP), metricas={k: {m: float(x) for m, x in v.items()} for k, v in met.items()},
        vies_T_ch=float(vT.ch.mean()), vies_T_tc=float(vT.tc.mean()), n_T_frio=int((vT.ch < 0).sum()),
        vies_T_min=float(vT.ch.min()), vies_T_max=float(vT.ch.max()),
        r_vies_elev=float(np.corrcoef(vT.ch, vT.elev)[0, 1]), r_vies_lat=float(np.corrcoef(vT.ch, vT.lat)[0, 1]),
        r_vies_lon=float(np.corrcoef(vT.ch, vT.lon)[0, 1]),
        vies_T_alto=float(vT[vT.elev > 1000].ch.mean()) if (vT.elev > 1000).any() else None,
        n_T_alto=int((vT.elev > 1000).sum()),
        P_ch_mediana=float(vP.ch.median()), P_tc_mediana=float(vP.tc.median()),
        P_ch_10=int((vP.ch.abs() <= 10).sum()), P_tc_10=int((vP.tc.abs() <= 10).sum()),
        pares_T=len(pares["T"]["ch"][0]), pares_P=len(pares["P"]["ch"][0]),
        piores_T=vT.sort_values("ch").head(4)[["nome", "elev", "ch"]].to_dict("records"),
        piores_P=vP.reindex(vP.ch.abs().sort_values(ascending=False).index).head(4)[["nome", "ch"]].to_dict("records"))
    # classificação das estações com T (GHCN) e P (GSOD) do mesmo código OMM
    pw = {e["wmo"]: k for k, e in P.items()}
    cls = []
    for k, e in T.items():
        if e["wmo"] not in pw:
            continue
        kp_ = pw[e["wmo"]]
        ts, ps = e["serie"], P[kp_]["serie"]
        tc_, pc_ = climatologia(ts), climatologia(ps)
        if tc_.isna().any() or pc_.isna().any():
            continue
        lat_ = np.array([e["lat"]])
        Ts, Ps = tc_.values[:, None], pc_.values[:, None]
        k_est = K.koppen(Ts, Ps, lat_)[0]
        h_est = K.holdridge(Ts, Ps, lat_, so_id=True)["id"][0]
        i, _ = pixel_proximo(px, e["lat"], e["lon"], transform)
        cls.append(dict(nome=e["nome"], k_est=letra("koppen", k_est), k_ch=letra("koppen", px["koppen"][i]),
                        k_tc=letra("koppen", tc["kp"][i]) if tc["kp"][i] else "-",
                        h_est=int(h_est), h_ch=int(px["holdridge"][i]), h_tc=int(tc["hd"][i])))
    cl = pd.DataFrame(cls)
    R["classif_estacoes"] = dict(
        n=len(cl), kp_ch=int((cl.k_est == cl.k_ch).sum()), kp_tc=int((cl.k_est == cl.k_tc).sum()),
        grp_ch=int((cl.k_est.str[0] == cl.k_ch.str[0]).sum()), grp_tc=int((cl.k_est.str[0] == cl.k_tc.str[0]).sum()),
        hd_ch=int((cl.h_est == cl.h_ch).sum()), hd_tc=int((cl.h_est == cl.h_tc).sum()),
        discordantes=cl[cl.k_est != cl.k_ch][["nome", "k_est", "k_ch"]].to_dict("records"))
    # razão anual TC/CHELSA da precipitação nos pixels das estações de P
    raz = {}
    for a in C.ANOS:
        s_tc = sum(np.nansum([tcP[k].get((a, m), np.nan) for m in range(1, 13)]) for k in P)
        s_ch = sum(np.nansum([chP[k].get((a, m), np.nan) for m in range(1, 13)]) for k in P)
        raz[a] = float(s_tc / s_ch)
    lr = stats.linregress(list(raz), list(raz.values()))
    R["razao_tc_ch"] = dict(anos=raz, decada=float(lr.slope * 10), p=float(lr.pvalue))
    print("estações ok", R["validacao"]["n_T"], R["validacao"]["n_P"])

    # ================================================= FIGURAS
    # 1 – área de estudo
    fig, ax = plt.subplots(figsize=(4.6, 7.6))
    pr = M.prov.copy()
    pr["reg"] = pr.provincia.map(reg_de_prov)
    for rg, cor in COR_REG.items():
        pr[pr.reg == rg].plot(ax=ax, color=cor, edgecolor="#444", linewidth=0.4)
    for c in cid:
        ax.plot(c["lon"], c["lat"], "o", ms=3.5, color="#b91c1c", mec="k", mew=0.4, zorder=5)
        ax.annotate(c["nome"], (c["lon"], c["lat"]), xytext=(4, 2), textcoords="offset points", fontsize=6)
    M.eixo(ax)
    ax.legend(handles=[Patch(facecolor=v, edgecolor="#444", lw=0.4, label=k) for k, v in COR_REG.items()]
              + [plt.Line2D([], [], marker="o", ls="", color="#b91c1c", mec="k", ms=4, label="Ciudad de referencia")],
              loc="lower right", fontsize=6.5, title="Región", title_fontsize=7)
    salvar(fig, 1)

    # 2-4 – esquemas (mesmos do artigo do Paraguai)
    import shutil
    esq = C.BRUTOS / "tmp_tpl" / "py_fig"
    for n_, f in ((2, "F03_image13.png"), (3, "F04_image19.png"), (4, "F05_image21.png")):
        shutil.copy(esq / f, FIG / f"Figura_{n_}.png")

    # 5 – variáveis
    fig, axs = plt.subplots(1, 4, figsize=(11, 5.6))
    M.continuo(axs[0], px["v_p_anual"], "YlGnBu", "mm", "a", "Precipitación anual", 0, 2000)
    M.continuo(axs[1], px["v_t_anual"], "RdYlBu_r", "°C", "b", "Temperatura media anual", -5, 25)
    M.continuo(axs[2], px["v_pet_anual"], "YlOrBr", "mm año⁻¹", "c", "ETP anual (Penman-Monteith)", 400, 2000)
    M.continuo(axs[3], px["v_p_mes_seco"], "YlGnBu", "mm", "d", "Precipitación del mes más seco", 0, 80)
    salvar(fig, 5)

    # 6 – climogramas
    sel = ["Posadas", "Buenos Aires", "Mendoza", "Ushuaia"]
    meses = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    fig, axs = plt.subplots(2, 4, figsize=(11, 4.6), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.4]))
    for j, nm in enumerate(sel):
        c = CI[nm]
        axs[0, j].plot(range(12), c["tas"], "-o", color="#dc2626", ms=3)
        axs[0, j].set_title(f"{nm} — {c['koppen']}", fontsize=8, fontweight="bold")
        axs[0, j].set_ylabel("T (°C)" if j == 0 else "")
        axs[0, j].set_ylim(-5, 30)
        axs[1, j].bar(range(12), c["pr"], color="#60a5fa", label="P")
        axs[1, j].plot(range(12), c["pet"], "--", color="#16a34a", label="ETP")
        axs[1, j].set_xticks(range(12), meses)
        axs[1, j].set_ylim(0, 230)
        axs[1, j].set_ylabel("mm" if j == 0 else "")
        for a_ in axs[:, j]:
            a_.grid(ls=":", lw=0.4)
    axs[1, 0].legend(fontsize=7)
    salvar(fig, 6)

    # 7 – Köppen
    fig, ax = plt.subplots(figsize=(5.2, 8))
    M.classes(ax, px["koppen"], "koppen", leg_min=0.05, leg_fs=6.5, loc="upper left")
    ax.get_legend().set_bbox_to_anchor((1.02, 1))
    salvar(fig, 7)

    # 8 – % da área por classe nos três sistemas
    fig, axs = plt.subplots(1, 3, figsize=(11, 4.2))
    for ax, (cam, cod, tit) in zip(axs, (("koppen", px["koppen"], "(a) Köppen-Geiger"),
                                         ("th_umidade", px["th_umidade"], "(b) Thornthwaite (humedad)"),
                                         ("holdridge", px["holdridge"], "(c) Holdridge"))):
        p = {c: v for c, v in area_pct(cod, area).items() if v >= 0.5}
        nomes = [letra(cam, c) if cam != "holdridge" else nome_classe(cam, c) for c in p]
        ax.barh(range(len(p)), list(p.values()), color=[LEG[cam + "_todas"][str(c)]["cor"] for c in p], edgecolor="#333", lw=0.3)
        ax.set_yticks(range(len(p)), nomes, fontsize=6.5 if cam == "holdridge" else 7.5)
        ax.invert_yaxis()
        for y, v in enumerate(p.values()):
            ax.text(v + 0.3, y, f"{v:.1f}".replace(".", ","), va="center", fontsize=6)
        ax.set_title(tit, fontsize=8, fontweight="bold", loc="left")
        ax.set_xlabel("% del área del país")
        ax.grid(axis="x", ls=":", lw=0.4)
    plt.tight_layout()
    salvar(fig, 8)

    # 9 – Thornthwaite
    fig, axs = plt.subplots(1, 3, figsize=(11, 7.4))
    M.classes(axs[0], px["th_umidade"], "th_umidade", "a", "Clase de humedad", leg_min=0.05, leg_fs=6.5, abaixo=True)
    M.continuo(axs[1], px["th_Im"], "BrBG", "Iₘ (%)", "b", "Índice de humedad", norm=TwoSlopeNorm(0, -60, 100), abaixo=True)
    M.classes(axs[2], px["th_termica"], "th_termica", "c", "Eficiencia térmica", leg_min=0.05, leg_fs=6.5, abaixo=True)
    salvar(fig, 9)

    # 10 – balanço hídrico de três cidades
    import agrometeorologiapy as amp
    sel_bh = ["Mendoza", "Buenos Aires", "Posadas"]
    cores_bh = {"Mendoza": "#d97706", "Buenos Aires": "#16a34a", "Posadas": "#2563eb"}
    bhs = {}
    for nm in sel_bh:
        c = CI[nm]
        b = amp.balanco_hidrico_climatologico_grade(np.array(c["pr"])[:, None], np.array(c["pet"])[:, None], C.CAD)
        bhs[nm] = {k: np.asarray(v).ravel() for k, v in b.items()}
    R["bh_cidades"] = {nm: {k: [round(float(x), 1) for x in v] for k, v in b.items()} for nm, b in bhs.items()}
    fig, axs = plt.subplots(2, 2, figsize=(10, 6.4))
    x = np.arange(12)
    w = 0.27
    for j, nm in enumerate(sel_bh):
        b = bhs[nm]
        axs[0, 0].bar(x + (j - 1) * w, b["EXC"], w, color=cores_bh[nm], label=nm)
        axs[0, 0].bar(x + (j - 1) * w, -b["DEF"], w, color=cores_bh[nm], alpha=0.5)
        axs[0, 1].plot(x, b["ARM"], "-o", ms=3, color=cores_bh[nm], label=nm)
    axs[0, 0].axhline(0, color="k", lw=0.5)
    axs[0, 0].set_title("(a) Extracto del balance hídrico: EXC (+) y DEF (−)", fontsize=8, fontweight="bold", loc="left")
    axs[0, 1].axhline(C.CAD, color="k", ls="--", lw=0.6)
    axs[0, 1].set_title("(b) Almacenamiento (ARM) y CAD", fontsize=8, fontweight="bold", loc="left")
    b = bhs["Buenos Aires"]
    alt = np.asarray(b.get("ALT", np.diff(np.r_[b["ARM"][-1], b["ARM"]])))
    axs[1, 0].bar(x, np.where(alt < 0, alt, 0), color="#f59e0b", label="RET")
    axs[1, 0].bar(x, np.where(alt > 0, alt, 0), color="#3b82f6", label="REP")
    axs[1, 0].plot(x, b["EXC"], "-", color="#1e3a8a", label="EXC")
    axs[1, 0].plot(x, -b["DEF"], "-", color="#b91c1c", label="DEF")
    axs[1, 0].axhline(0, color="k", lw=0.5)
    axs[1, 0].set_title("(c) Retiradas y reposiciones — Buenos Aires", fontsize=8, fontweight="bold", loc="left")
    c = CI["Mendoza"]
    bm = bhs["Mendoza"]
    axs[1, 1].plot(x, c["pr"], "-o", ms=3, color="#2563eb", label="P")
    axs[1, 1].plot(x, c["pet"], "-", color="#16a34a", label="ETP")
    axs[1, 1].plot(x, bm["ETR"], "--", color="#7c3aed", label="ETR")
    axs[1, 1].fill_between(x, bm["ETR"], c["pet"], color="#fca5a5", alpha=0.5, label="DEF")
    axs[1, 1].set_title("(d) P, ETP y ETR — Mendoza", fontsize=8, fontweight="bold", loc="left")
    for a_ in axs.ravel():
        a_.set_xticks(x, meses)
        a_.grid(ls=":", lw=0.4)
        a_.legend(fontsize=6)
        a_.set_ylabel("mm")
    plt.tight_layout()
    salvar(fig, 10)

    # 11 – Holdridge
    fig, axs = plt.subplots(1, 2, figsize=(10, 9.2))
    M.classes(axs[0], px["holdridge"], "holdridge", "a", "Zonas de vida", leg_min=0.1, leg_fs=6, ncol=2, abaixo=True)
    M.continuo(axs[1], np.log2(np.clip(px["hd_razao_ETP"], 0.0625, 32)), "BrBG_r", "log₂(ETP/P)", "b",
               "Razón ETP de Holdridge / P", -4, 5, contorno=0, abaixo=True)
    salvar(fig, 11)

    # 12 – composição por província
    fig, axs = plt.subplots(1, 2, figsize=(11, 6.2), sharey=True)
    for ax, (cam, cod, tit) in zip(axs, (("koppen", px["koppen"], "(a) Köppen-Geiger"),
                                         ("th_umidade", px["th_umidade"], "(b) Thornthwaite (humedad)"))):
        usados = set()
        for y, p in enumerate(provs):
            esq_ = 0
            for c, v in sorted(area_pct(cod, area, prov_px == p).items()):
                ax.barh(y, v, left=esq_, color=LEG[cam + "_todas"][str(c)]["cor"], edgecolor="white", lw=0.2)
                esq_ += v
                if v >= 2:
                    usados.add(c)
        ax.set_yticks(range(len(provs)), provs, fontsize=6.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("% del área de la provincia")
        ax.set_title(tit, fontsize=8, fontweight="bold", loc="left")
        ax.legend(handles=[Patch(color=LEG[cam + "_todas"][str(c)]["cor"], label=letra(cam, c)) for c in sorted(usados)],
                  fontsize=6, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.07), frameon=False)
    plt.tight_layout()
    salvar(fig, 12)

    # 13 – validação nas estações
    fig = plt.figure(figsize=(11, 8.6))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 1.5])
    for j, (nomev, un, lim) in enumerate((("T", "°C", (-10, 32)), ("P", "mm", (0, 450)))):
        ax = fig.add_subplot(gs[0, 2 * j:2 * j + 2])
        for prod, cor, lab in (("tc", "#f59e0b", "TerraClimate"), ("ch", "#2563eb", "CHELSA")):
            e_, o_ = pares[nomev][prod]
            ax.scatter(o_, e_, s=2, alpha=0.25, color=cor, label=f"{lab} (c = {met[f'{nomev}_{prod}_mensal']['c']:.2f})".replace(".", ","))
        ax.plot(lim, lim, "k--", lw=0.6)
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_xlabel(f"Estación ({un})")
        ax.set_ylabel(f"Producto ({un})")
        ax.set_title(f"({'ab'[j]}) {'Temperatura media mensual' if nomev == 'T' else 'Precipitación mensual'}",
                     fontsize=8, fontweight="bold", loc="left")
        ax.legend(fontsize=7, markerscale=4)
        ax.grid(ls=":", lw=0.4)
    for j, (df, col, cm_, lim, tit, un) in enumerate((
            (vT, "ch", "RdBu_r", 3, "Sesgo de la temperatura\nCHELSA", "°C"),
            (vT, "tc", "RdBu_r", 3, "Sesgo de la temperatura\nTerraClimate", "°C"),
            (vP, "ch", "BrBG", 40, "Sesgo relativo de P anual\nCHELSA", "%"),
            (vP, "tc", "BrBG", 40, "Sesgo relativo de P anual\nTerraClimate", "%"))):
        ax = fig.add_subplot(gs[1, j])
        sc = ax.scatter(df.lon, df.lat, c=df[col], cmap=cm_, vmin=-lim, vmax=lim, s=26, edgecolor="k", lw=0.4, zorder=5)
        M.eixo(ax, "cdef"[j], tit)
        ax.title.set_fontsize(7)
        cb = plt.colorbar(sc, ax=ax, shrink=0.5, pad=0.02, extend="both")
        cb.set_label(un, fontsize=7)
        cb.ax.tick_params(labelsize=6)
    plt.tight_layout()
    salvar(fig, 13)

    # 14 – comparação com outros produtos
    fig, axs = plt.subplots(1, 4, figsize=(12, 8.6))
    tcr = R["terraclimate"]
    M.classes(axs[0], b91, "koppen", "a", f"Beck et al. (2023): {R['beck']['concordancia']:.1f}%".replace(".", ","),
              leg_min=0.5, leg_fs=6, nomes_curtos=True, abaixo=True, ncol=3)
    M.classes(axs[1], tc["kp"], "koppen", "b", f"Köppen (TerraClimate): {tcr['koppen']:.1f}%".replace(".", ","),
              leg_min=0.5, leg_fs=6, nomes_curtos=True, abaixo=True, ncol=3)
    M.classes(axs[2], tc["um"], "th_umidade", "c", f"Humedad (TerraClimate): {tcr['umidade']:.1f}%".replace(".", ","),
              leg_min=0.3, leg_fs=6, nomes_curtos=True, abaixo=True, ncol=3)
    M.classes(axs[3], tc["hd"], "holdridge", "d", f"Holdridge (TerraClimate): {tcr['holdridge']:.1f}%".replace(".", ","),
              leg_min=1.0, leg_fs=5.2, abaixo=True, ncol=1)
    salvar(fig, 14)

    # 15 – ecorregiões e sensibilidade
    fig = plt.figure(figsize=(10, 8.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.62], wspace=0.35)
    ax = fig.add_subplot(gs[0])
    M.classes(ax, px["holdridge"], "holdridge", "a", "Holdridge y ecorregiones RESOLVE 2017", leg_min=1.0, leg_fs=5.5,
              abaixo=True, ncol=2)
    pais = M.prov.union_all() if hasattr(M.prov, "union_all") else M.prov.unary_union
    eco_ar = gpd.clip(eco[eco.cod.isin(np.unique(e_px))].boundary, pais)   # limites só dentro do país
    eco_ar.plot(ax=ax, color="k", lw=0.7, ls="--")
    ax.set_xlim(M.ext[0], M.ext[1])
    ax.set_ylim(M.ext[2], M.ext[3])
    ax = fig.add_subplot(gs[1])
    s = val["sensibilidade"]
    rot = {"T-0.5": "T −0,5 °C", "T+0.5": "T +0,5 °C", "T_vies": f"T {s['T_vies']['dT']:+.2f} °C".replace(".", ","),
           "P-10%": "P −10%", "P+10%": "P +10%", "CAD50": "CAD 50 mm", "CAD150": "CAD 150 mm", "ETP+10%": "ETP +10%",
           "ETP_metodo": "Método de la ETP"}
    cen = [c_ for c_ in rot if c_ in s]
    sist = [("koppen", "Köppen-Geiger", "#2563eb"), ("umidade", "Thornthwaite", "#0891b2"), ("zona", "Holdridge", "#dc2626")]
    y = np.arange(len(cen))
    for j, (k_, nm, cor) in enumerate(sist):
        vals = [s[c_].get(k_, np.nan) for c_ in cen]
        ax.barh(y + (j - 1) * 0.27, vals, 0.27, color=cor, label=nm)
        for yy, v in zip(y + (j - 1) * 0.27, vals):
            if np.isfinite(v):
                ax.text(v + 0.4, yy, f"{v:.1f}".replace(".", ","), va="center", fontsize=6)
    ax.set_yticks(y, [rot[c_] for c_ in cen], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("% del área que cambia de clase")
    ax.set_title("(b) Sensibilidad", fontsize=8, fontweight="bold", loc="left")
    ax.set_xlim(0, max(v for c_ in cen for k_, v in s[c_].items() if k_ != "dT") * 1.15)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, frameon=False,
              handlelength=1, columnspacing=0.8)
    ax.grid(axis="x", ls=":", lw=0.4)
    salvar(fig, 15)

    # 16 – estabilidade
    fig, axs = plt.subplots(1, 3, figsize=(11, 6))
    for ax, (k_, tit) in zip(axs, (("koppen", "Köppen-Geiger (1991-2020)"), ("umidade", "Humedad de Thornthwaite (1991-2018)"),
                                   ("zona", "Holdridge (1991-2020)"))):
        M.continuo(ax, est[k_], "viridis", "% de años", "abc"["koppen umidade zona".split().index(k_)], tit, 0, 100)
    salvar(fig, 16)

    # 17 – série anual das áreas
    fig, axs = plt.subplots(1, 3, figsize=(12, 5.2))
    for ax, (k_, cam, tit) in zip(axs, (("koppen", "koppen", "(a) Köppen-Geiger"), ("umidade", "th_umidade", "(b) Humedad de Thornthwaite"),
                                        ("zona", "holdridge", "(c) Holdridge"))):
        e_ = estab[k_]
        for c, sr in e_["serie"].items():
            if np.mean(sr) < 3:
                continue
            nm = letra(cam, c) if cam != "holdridge" else nome_classe(cam, c)
            ax.plot(e_["anos"], sr, "-o", ms=2.5, lw=1, color=LEG[cam + "_todas"][str(c)]["cor"], label=nm,
                    mec="#333", mew=0.2)
        ax.set_ylabel("% del país")
        ax.set_xlabel("Año")
        ax.set_title(tit, fontsize=8, fontweight="bold", loc="left")
        ax.legend(fontsize=6, ncol=2 if cam == "holdridge" else 4, loc="upper center", bbox_to_anchor=(0.5, -0.13),
                  frameon=False, handlelength=1.5, columnspacing=0.8)
        ax.grid(ls=":", lw=0.4)
    plt.tight_layout()
    salvar(fig, 17)

    # 18 – plataforma (capturas do site; ver dados_brutos/capturas)
    from PIL import Image, ImageDraw, ImageFont
    cap = C.BRUTOS / "capturas"
    if (cap / "ficha.png").exists():
        ini, mp, fi = (Image.open(cap / f"{n_}.png").convert("RGB") for n_ in ("inicio", "mapa", "ficha"))
        W = 1400
        aj = lambda im: im.resize((W // 2 - 10, int(im.height * (W // 2 - 10) / im.width)), Image.LANCZOS)
        A, B, Cc, D = aj(ini), aj(mp), aj(fi.crop((390, 880, 1320, 1400))), aj(fi.crop((390, 1400, 1320, 1720)))
        h1, h2 = max(A.height, B.height), max(Cc.height, D.height)
        out = Image.new("RGB", (W, h1 + h2 + 30), "white")
        pos = {"A": (0, 0), "B": (W // 2 + 10, 0), "C": (0, h1 + 30), "D": (W // 2 + 10, h1 + 30)}
        dr = ImageDraw.Draw(out)
        fonte = ImageFont.truetype("arialbd.ttf", 34)
        for (k_, (x0, y0)), im in zip(pos.items(), (A, B, Cc, D)):
            out.paste(im, (x0, y0))
            x1, y1 = x0 + im.width - 46, y0 + im.height - 48       # canto inferior direito do painel
            dr.rectangle([x1, y1, x1 + 38, y1 + 42], fill="white", outline="black", width=2)
            dr.text((x1 + 9, y1 + 2), k_, fill="black", font=fonte)
        out.save(FIG / "Figura_18.png", dpi=(300, 300))

    (ART / "resultados_artigo.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("ok — figuras 1-17 e resultados_artigo.json")


if __name__ == "__main__":
    main()
