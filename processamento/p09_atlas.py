# -*- coding: utf-8 -*-
"""Atlas: figuras nacionais (classificações, variáveis, validação, estabilidade e sensibilidade) em
espanhol, português e inglês, e atlas/atlas.json com as legendas das figuras."""
import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap, BoundaryNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

import config as C  # noqa: E402

LEG = json.loads((C.RAIZ / "processamento" / "legendas_base.json").read_text(encoding="utf-8"))
DPI = 200
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

T = {  # textos das figuras
    "es": dict(lon="Longitud", lat="Latitud", fonte="CHELSA V2.1, 1991–2020 · ClimaTec AR", area="del área",
               estaciones="Sesgo CHELSA − estación (°C)", beck="Beck et al. (2023)", este="Este trabajo",
               concorda="Concuerda", discorda="No concuerda", cambia="% del área que cambia de clase",
               estab="% de años en la clase de la normal", tc="TerraClimate (~4 km)"),
    "pt": dict(lon="Longitude", lat="Latitude", fonte="CHELSA V2.1, 1991–2020 · ClimaTec AR", area="da área",
               estaciones="Viés CHELSA − estação (°C)", beck="Beck et al. (2023)", este="Este trabalho",
               concorda="Concorda", discorda="Não concorda", cambia="% da área que muda de classe",
               estab="% de anos na classe da normal", tc="TerraClimate (~4 km)"),
    "en": dict(lon="Longitude", lat="Latitude", fonte="CHELSA V2.1, 1991–2020 · ClimaTec AR", area="of the area",
               estaciones="CHELSA − station bias (°C)", beck="Beck et al. (2023)", este="This work",
               concorda="Agrees", discorda="Disagrees", cambia="% of the area changing class",
               estab="% of years in the normal's class", tc="TerraClimate (~4 km)"),
}


class Base:
    def __init__(self):
        self.px = np.load(C.CLASSES_DIR / "pixels.npz")
        transform, _, shape = C.grade()
        l0, l1 = self.px["lin"].min(), self.px["lin"].max() + 1
        c0, c1 = self.px["col"].min(), self.px["col"].max() + 1
        self.l0, self.c0, self.sh = l0, c0, (l1 - l0, c1 - c0)
        self.ext = [transform.c + c0 * transform.a, transform.c + c1 * transform.a,
                    transform.f + l1 * transform.e, transform.f + l0 * transform.e]
        self.prov = gpd.read_file(C.SITE_DADOS / "provincias.geojson")
        self.vizinhos = None

    def grade(self, v, fill=np.nan, dtype="float32"):
        g = np.full(self.sh, fill, dtype)
        g[self.px["lin"] - self.l0, self.px["col"] - self.c0] = v
        return g

    def eixo(self, ax, lg):
        self.prov.boundary.plot(ax=ax, color="#222", linewidth=0.35)
        ax.set_xlim(self.ext[0], self.ext[1])
        ax.set_ylim(self.ext[2], self.ext[3])
        ax.set_aspect(1 / np.cos(np.radians(38)))
        ax.set_xlabel(T[lg]["lon"], fontsize=7)
        ax.set_ylabel(T[lg]["lat"], fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(color="#bbb", lw=0.3, ls=":")


def salvar(fig, nome, lg):
    d = C.SITE_ATLAS / lg
    d.mkdir(parents=True, exist_ok=True)
    fig.savefig(d / nome, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def nome_classe(camada, c, lg):
    return LEG[camada + "_todas"][str(int(c))]["nome"][lg]


def mapa_classes(B, cod, camada, titulo, nome, lg, contorno=None):
    presentes = [int(c) for c in np.unique(cod) if c > 0]
    area = B.px["area"]
    pct = {c: 100 * area[cod == c].sum() / area[cod > 0].sum() for c in presentes}
    cores = ["#ffffff"] * 256
    for c in presentes:
        cores[c] = LEG[camada + "_todas"][str(c)]["cor"]
    g = B.grade(cod, 0, "uint8").astype(float)
    g[g == 0] = np.nan
    fig, ax = plt.subplots(figsize=(7.5, 9.5))
    ax.imshow(g, extent=B.ext, cmap=ListedColormap(cores), norm=BoundaryNorm(np.arange(257) - 0.5, 256),
              interpolation="nearest")
    if contorno is not None:
        contorno.boundary.plot(ax=ax, color="#000", linewidth=0.6, linestyle="--")
    B.eixo(ax, lg)
    ax.set_title(titulo, fontsize=11, fontweight="bold")
    h = [Patch(facecolor=cores[c], edgecolor="#333", lw=0.4,
               label=f"{nome_classe(camada, c, lg)} ({pct[c]:.1f}%)") for c in presentes if pct[c] >= 0.05]
    ax.legend(handles=h, loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=7, frameon=False,
              title=T[lg]["fonte"], title_fontsize=6)
    salvar(fig, nome, lg)
    dom = max(pct, key=pct.get)
    return dom, pct[dom]


def mapa_continuo(B, v, titulo, unidade, cmap, nome, lg, vmin=None, vmax=None, norm=None):
    g = B.grade(v)
    fig, ax = plt.subplots(figsize=(6.2, 9.5))
    q = np.nanpercentile(v, [1, 99])
    im = ax.imshow(g, extent=B.ext, cmap=cmap, vmin=vmin if vmin is not None else q[0],
                   vmax=vmax if vmax is not None else q[1], norm=norm, interpolation="nearest")
    B.eixo(ax, lg)
    ax.set_title(titulo, fontsize=11, fontweight="bold")
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label(unidade)
    ax.text(0.99, 0.01, T[lg]["fonte"], transform=ax.transAxes, ha="right", fontsize=6, color="#555")
    salvar(fig, nome, lg)


def letra(camada, c):
    return LEG[camada + "_todas"][str(int(c))]["nome"]["es"].split(" — ")[0]


def main():
    B = Base()
    px = B.px
    val = json.loads((C.CLASSES_DIR / "validacao.json").read_text(encoding="utf-8"))
    est = np.load(C.CLASSES_DIR / "estabilidade.npz")
    vpx = np.load(C.CLASSES_DIR / "validacao_pixels.npz")
    eco = gpd.read_file(C.CLASSES_DIR / "ecorregioes_arg.gpkg")
    area = px["area"]
    media_est = {k: float(np.nansum(est[k] * area) / area[np.isfinite(est[k])].sum()) for k in ("koppen", "umidade", "zona")}
    anos = {k: (int(est[f"anos_{k}"][0]), int(est[f"anos_{k}"][-1])) for k in ("koppen", "umidade", "zona")}

    titulos = {
        "koppen": {"es": "Köppen-Geiger", "pt": "Köppen-Geiger", "en": "Köppen-Geiger"},
        "th_umidade": {"es": "Thornthwaite — humedad (CAD 100 mm)", "pt": "Thornthwaite — umidade (CAD 100 mm)", "en": "Thornthwaite — moisture (AWC 100 mm)"},
        "th_subtipo": {"es": "Thornthwaite — variación estacional", "pt": "Thornthwaite — variação sazonal", "en": "Thornthwaite — seasonal variation"},
        "th_termica": {"es": "Thornthwaite — eficiencia térmica", "pt": "Thornthwaite — eficiência térmica", "en": "Thornthwaite — thermal efficiency"},
        "th_concentracao": {"es": "Thornthwaite — concentración estival", "pt": "Thornthwaite — concentração estival", "en": "Thornthwaite — summer concentration"},
        "holdridge": {"es": "Zonas de vida de Holdridge", "pt": "Zonas de vida de Holdridge", "en": "Holdridge life zones"},
    }
    cont = {  # nome, chave, título (es, pt, en), unidade, cmap, vmin, vmax
        "fig_p_anual.png": ("v_p_anual", ("Precipitación anual", "Precipitação anual", "Annual precipitation"), "mm", "YlGnBu", 0, 2000),
        "fig_p_mes_seco.png": ("v_p_mes_seco", ("Precipitación del mes más seco", "Precipitação do mês mais seco", "Driest-month precipitation"), "mm", "YlGnBu", 0, 100),
        "fig_t_anual.png": ("v_t_anual", ("Temperatura media anual", "Temperatura média anual", "Mean annual temperature"), "°C", "RdYlBu_r", None, None),
        "fig_t_mes_frio.png": ("v_t_mes_frio", ("Temperatura del mes más frío", "Temperatura do mês mais frio", "Coldest-month temperature"), "°C", "RdYlBu_r", None, None),
        "fig_th_im.png": ("th_Im", ("Índice de humedad (Im)", "Índice de umidade (Im)", "Moisture index (Im)"), "%", "BrBG", -100, 100),
        "fig_th_def.png": ("th_DEF_anual", ("Déficit hídrico anual", "Deficiência hídrica anual", "Annual water deficit"), "mm", "YlOrRd", 0, None),
        "fig_th_exc.png": ("th_EXC_anual", ("Exceso hídrico anual", "Excedente hídrico anual", "Annual water surplus"), "mm", "Blues", 0, None),
        "fig_pet_anual.png": ("v_pet_anual", ("ETP anual (Penman-Monteith)", "ETP anual (Penman-Monteith)", "Annual PET (Penman-Monteith)"), "mm", "YlOrBr", None, None),
        "fig_biotemp.png": ("hd_biotemperatura", ("Biotemperatura", "Biotemperatura", "Biotemperature"), "°C", "RdYlBu_r", None, None),
        "fig_razao_etp.png": ("hd_razao_ETP", ("Razón ETP/P (Holdridge)", "Razão ETP/P (Holdridge)", "PET/P ratio (Holdridge)"), "", "BrBG_r", 0, 8),
    }
    dom = {}
    for i, lg in enumerate(C.IDIOMAS):
        for camada, chave in (("koppen", "koppen"), ("th_umidade", "th_umidade"), ("th_subtipo", "th_subtipo"),
                              ("th_termica", "th_termica"), ("th_concentracao", "th_concentracao"),
                              ("holdridge", "holdridge")):
            nome = "fig_" + camada.replace("umidade", "umidade") + ".png"
            dom[camada] = mapa_classes(B, px[chave], camada, titulos[camada][lg], nome, lg)
        for nome, (k, tit, un, cm, vmin, vmax) in cont.items():
            mapa_continuo(B, px[k], tit[i], un, cm, nome, lg, vmin, vmax)

        # --- validação: estações
        st = pd.read_csv(C.CLASSES_DIR / "estacoes.csv")
        sp = pd.read_csv(C.CLASSES_DIR / "estacoes_precip.csv")
        fig, axs = plt.subplots(1, 2, figsize=(10.5, 8.5))
        tit_p = {"es": "Sesgo relativo de la precipitación anual (%)", "pt": "Viés relativo da precipitação anual (%)",
                 "en": "Relative bias of annual precipitation (%)"}[lg]
        for ax, df, col, lim, cm_, tit, un in (
                (axs[0], st, "vies", max(2, np.ceil(st.vies.abs().quantile(0.95))), "RdBu_r",
                 f"{T[lg]['estaciones']} — GHCN-Daily (n = {len(st)})", "°C"),
                (axs[1], sp, "vies_rel", 40, "BrBG", f"{tit_p} — GSOD (n = {len(sp)})", "%")):
            ax.imshow(B.grade(px["v_t_anual"]), extent=B.ext, cmap="Greys", alpha=0.3, interpolation="nearest")
            sc = ax.scatter(df.lon, df.lat, c=df[col], cmap=cm_, vmin=-lim, vmax=lim, s=30, edgecolor="k", lw=0.5, zorder=5)
            B.eixo(ax, lg)
            ax.set_title(tit, fontsize=9, fontweight="bold")
            fig.colorbar(sc, ax=ax, shrink=0.55, pad=0.02, extend="both").set_label(un)
        salvar(fig, "fig_val_estaciones.png", lg)

        # --- Beck: dois painéis
        fig, axs = plt.subplots(1, 2, figsize=(10, 8.5))
        cores = ["#ffffff"] * 256
        for c in range(1, 32):
            cores[c] = LEG["koppen_todas"][str(c)]["cor"]
        cm = ListedColormap(cores)
        nm = BoundaryNorm(np.arange(257) - 0.5, 256)
        gb = B.grade(vpx["beck"], 0, "uint8").astype(float)
        gb[gb == 0] = np.nan
        axs[0].imshow(gb, extent=B.ext, cmap=cm, norm=nm, interpolation="nearest")
        conc = (vpx["beck"] == px["koppen"]).astype(float)
        conc[vpx["beck"] == 0] = np.nan
        axs[1].imshow(B.grade(conc), extent=B.ext, cmap=ListedColormap(["#d7301f", "#9ecae1"]), vmin=0, vmax=1,
                      interpolation="nearest")
        for ax in axs:
            B.eixo(ax, lg)
        axs[0].set_title(T[lg]["beck"] + " — 1991–2020", fontsize=10, fontweight="bold")
        axs[1].set_title(f"{T[lg]['beck']} × {T[lg]['este']}", fontsize=10, fontweight="bold")
        axs[1].legend(handles=[Patch(color="#9ecae1", label=T[lg]["concorda"]), Patch(color="#d7301f", label=T[lg]["discorda"])],
                      loc="lower right", fontsize=7)
        pres = [int(c) for c in np.unique(vpx["beck"]) if c > 0]
        axs[0].legend(handles=[Patch(facecolor=cores[c], edgecolor="#333", lw=0.4, label=nome_classe("koppen", c, lg).split(" — ")[0]) for c in pres],
                      loc="lower right", fontsize=6, ncol=2)
        salvar(fig, "fig_val_beck.png", lg)

        # --- TerraClimate (Köppen)
        tit_tc = {"es": "Köppen-Geiger con TerraClimate", "pt": "Köppen-Geiger com TerraClimate", "en": "Köppen-Geiger with TerraClimate"}[lg]
        mapa_classes(B, vpx["tc_koppen"], "koppen", tit_tc, "fig_val_terraclimate.png", lg)

        # --- estabilidade
        tit_est = {"koppen": {"es": "Estabilidad interanual — Köppen-Geiger", "pt": "Estabilidade interanual — Köppen-Geiger", "en": "Interannual stability — Köppen-Geiger"},
                   "umidade": {"es": "Estabilidad interanual — Thornthwaite (humedad)", "pt": "Estabilidade interanual — Thornthwaite (umidade)", "en": "Interannual stability — Thornthwaite (moisture)"},
                   "zona": {"es": "Estabilidad interanual — Holdridge", "pt": "Estabilidade interanual — Holdridge", "en": "Interannual stability — Holdridge"}}
        for k in ("koppen", "umidade", "zona"):
            mapa_continuo(B, est[k], tit_est[k][lg], T[lg]["estab"], "viridis", f"fig_estabilidad_{k}.png", lg, 0, 100)

        # --- ecorregiões
        tit_eco = {"es": "Holdridge y ecorregiones (RESOLVE 2017)", "pt": "Holdridge e ecorregiões (RESOLVE 2017)", "en": "Holdridge and ecoregions (RESOLVE 2017)"}[lg]
        mapa_classes(B, px["holdridge"], "holdridge", tit_eco, "fig_ecorregiones.png", lg, contorno=eco)

        # --- sensibilidade
        s = val["sensibilidade"]
        cenarios = list(s)
        vs = f"{s['T_vies']['dT']:+.2f}".replace(".", ",")
        rot = {lg_: {"T-0.5": "T −0,5 °C", "T+0.5": "T +0,5 °C", "T_vies": f"T {vs} °C",
                     "P-10%": "P −10%", "P+10%": "P +10%", "CAD50": cad + " 50 mm", "CAD150": cad + " 150 mm",
                     "ETP+10%": etp + " +10%", "ETP_metodo": met, "TC": "TerraClimate"}
               for lg_, cad, etp, met in (("es", "CAD", "ETP", "Método de la ETP"), ("pt", "CAD", "ETP", "Método da ETP"),
                                          ("en", "AWC", "PET", "PET method"))}[lg]
        tc = val["terraclimate"]
        dados = {c: {k: v for k, v in s[c].items() if k != 'dT'} for c in cenarios}
        dados["TC"] = dict(koppen=100 - tc["koppen"], umidade=100 - tc["umidade"], zona=100 - tc["zona"])
        sist = [("koppen", "Köppen-Geiger", "#2563eb"), ("umidade", "Thornthwaite", "#0891b2"), ("zona", "Holdridge", "#dc2626")]
        fig, ax = plt.subplots(figsize=(8, 6))
        y = np.arange(len(dados))
        for j, (k, nm_, cor) in enumerate(sist):
            vals = [dados[c].get(k, np.nan) for c in dados]
            ax.barh(y + (j - 1) * 0.27, vals, 0.27, color=cor, label=nm_)
            for yy, v in zip(y + (j - 1) * 0.27, vals):
                if np.isfinite(v):
                    ax.text(v + 0.3, yy, f"{v:.1f}", va="center", fontsize=6)
        ax.set_yticks(y, [rot[c] for c in dados])
        ax.invert_yaxis()
        ax.set_xlabel(T[lg]["cambia"])
        ax.legend(fontsize=8)
        ax.grid(axis="x", ls=":", lw=0.4)
        salvar(fig, "fig_sensibilidad.png", lg)
        print(lg, "ok")

    # ---------------- legendas (atlas.json)
    def leg3(fmt):
        return {lg: fmt(lg) for lg in C.IDIOMAS}
    nomep = lambda camada, lg: nome_classe(camada, dom[camada][0], lg)
    pr = lambda camada: dom[camada][1]
    pal = {"es": ("Predomina", "del área"), "pt": ("Predomina", "da área"), "en": ("prevails", "of the area")}

    def pred(camada, lg):
        a, b = pal[lg]
        return (f"{nomep(camada, lg)} {a} ({pr(camada):.1f}% {b})." if lg == "en"
                else f"{a} {nomep(camada, lg)} ({pr(camada):.1f}% {b}).")
    ep = val["estacoes_precip"]
    e, b_, tcv, sv, ec = val["estacoes"], val["beck"], val["terraclimate"], val["sensibilidade"], val["ecorregioes"]
    eco_top = ec["tabela"][:4]
    zn = lambda z, lg: nome_classe("holdridge", z, lg)

    def eco_txt(lg):
        return "; ".join(f"{r['ecorregiao']} → {zn(r['zona'], lg).lower()} ({r['pct_zona_na_eco']:.0f}%)" for r in eco_top)
    G = []
    G.append(dict(id="koppen", titulo=leg3(lambda lg: "Köppen-Geiger"), figuras=[
        dict(arquivo="fig_koppen.png", largo=True, legenda=leg3(lambda lg: {
            "es": "Clasificación climática de Köppen-Geiger (Alvares et al., 2013). ",
            "pt": "Classificação climática de Köppen-Geiger (Alvares et al., 2013). ",
            "en": "Köppen-Geiger climate classification (Alvares et al., 2013). "}[lg] + pred("koppen", lg))),
        dict(arquivo="fig_p_anual.png", legenda=dict(es="Precipitación media anual (mm).", pt="Precipitação média anual (mm).", en="Mean annual precipitation (mm).")),
        dict(arquivo="fig_p_mes_seco.png", legenda=dict(es="Precipitación del mes más seco (mm).", pt="Precipitação do mês mais seco (mm).", en="Precipitation of the driest month (mm).")),
        dict(arquivo="fig_t_anual.png", legenda=dict(es="Temperatura media anual (°C).", pt="Temperatura média anual (°C).", en="Mean annual temperature (°C).")),
        dict(arquivo="fig_t_mes_frio.png", legenda=dict(es="Temperatura media del mes más frío (°C).", pt="Temperatura média do mês mais frio (°C).", en="Mean temperature of the coldest month (°C).")),
    ]))
    G.append(dict(id="thornthwaite", titulo=dict(es="Thornthwaite (1948)", pt="Thornthwaite (1948)", en="Thornthwaite (1948)"), figuras=[
        dict(arquivo="fig_th_umidade.png", largo=True, legenda=leg3(lambda lg: {"es": "Clase de humedad de Thornthwaite (CAD = 100 mm). ", "pt": "Classe de umidade de Thornthwaite (CAD = 100 mm). ", "en": "Thornthwaite moisture class (AWC = 100 mm). "}[lg] + pred("th_umidade", lg))),
        dict(arquivo="fig_th_subtipo.png", legenda=leg3(lambda lg: {"es": "Variación estacional de la humedad (subtipo de Thornthwaite). ", "pt": "Variação sazonal da umidade (subtipo de Thornthwaite). ", "en": "Seasonal variation of moisture (Thornthwaite subtype). "}[lg] + pred("th_subtipo", lg))),
        dict(arquivo="fig_th_termica.png", legenda=leg3(lambda lg: {"es": "Eficiencia térmica (ETP anual). ", "pt": "Eficiência térmica (ETP anual). ", "en": "Thermal efficiency (annual PET). "}[lg] + pred("th_termica", lg))),
        dict(arquivo="fig_th_concentracao.png", legenda=leg3(lambda lg: {"es": "Concentración estival de la eficiencia térmica. ", "pt": "Concentração estival da eficiência térmica. ", "en": "Summer concentration of thermal efficiency. "}[lg] + pred("th_concentracao", lg))),
        dict(arquivo="fig_th_im.png", legenda=dict(es="Índice de humedad (Im = Ih − 0,6 Ia).", pt="Índice de umidade (Im = Ih − 0,6 Ia).", en="Moisture index (Im = Ih − 0.6 Ia).")),
        dict(arquivo="fig_th_def.png", legenda=dict(es="Déficit hídrico anual (mm), balance hídrico de Thornthwaite y Mather (1955).", pt="Deficiência hídrica anual (mm), balanço hídrico de Thornthwaite e Mather (1955).", en="Annual water deficit (mm), Thornthwaite and Mather (1955) water balance.")),
        dict(arquivo="fig_th_exc.png", legenda=dict(es="Exceso hídrico anual (mm).", pt="Excedente hídrico anual (mm).", en="Annual water surplus (mm).")),
        dict(arquivo="fig_pet_anual.png", legenda=dict(es="Evapotranspiración potencial anual (mm), Penman-Monteith (CHELSA).", pt="Evapotranspiração potencial anual (mm), Penman-Monteith (CHELSA).", en="Annual potential evapotranspiration (mm), Penman-Monteith (CHELSA).")),
    ]))
    G.append(dict(id="holdridge", titulo=dict(es="Zonas de vida de Holdridge", pt="Zonas de vida de Holdridge", en="Holdridge life zones"), figuras=[
        dict(arquivo="fig_holdridge.png", largo=True, legenda=leg3(lambda lg: {"es": "Zonas de vida de Holdridge (ETP de Holdridge = 58,93 × biotemperatura). ", "pt": "Zonas de vida de Holdridge (ETP de Holdridge = 58,93 × biotemperatura). ", "en": "Holdridge life zones (Holdridge PET = 58.93 × biotemperature). "}[lg] + pred("holdridge", lg))),
        dict(arquivo="fig_biotemp.png", legenda=dict(es="Biotemperatura media anual (°C).", pt="Biotemperatura média anual (°C).", en="Mean annual biotemperature (°C).")),
        dict(arquivo="fig_razao_etp.png", legenda=dict(es="Razón de evapotranspiración potencial (ETP de Holdridge / P).", pt="Razão de evapotranspiração potencial (ETP de Holdridge / P).", en="Potential evapotranspiration ratio (Holdridge PET / P).")),
    ]))
    a = anos
    G.append(dict(id="validacion", titulo=dict(es="Validación e incertidumbre", pt="Validação e incerteza", en="Validation and uncertainty"), figuras=[
        dict(arquivo="fig_val_estaciones.png", largo=True, legenda=dict(
            es=f"Izquierda: sesgo medio de la temperatura mensual de CHELSA respecto a {e['n']} estaciones (GHCN-Daily, 1991–2020, mismos meses): {e['vies_medio']:+.2f} °C en promedio (error absoluto medio {e['mae_medio']:.2f} °C); CHELSA es más frío en {e['n_mais_frio']} de las {e['n']} estaciones. Derecha: sesgo relativo de la precipitación anual respecto a {ep['n']} estaciones sinópticas (NOAA GSOD; días con total completo o sin lluvia registrada, meses con ≥ 27 días): mediana {ep['vies_rel_mediano']:+.1f}%, {ep['n_dentro_10']} estaciones dentro de ±10%; correlación mensual media {ep['r_mensal_medio']:.2f}.",
            pt=f"Esquerda: viés médio da temperatura mensal do CHELSA em relação a {e['n']} estações (GHCN-Daily, 1991–2020, mesmos meses): {e['vies_medio']:+.2f} °C em média (erro absoluto médio {e['mae_medio']:.2f} °C); o CHELSA é mais frio em {e['n_mais_frio']} das {e['n']} estações. Direita: viés relativo da precipitação anual em relação a {ep['n']} estações sinóticas (NOAA GSOD; dias com total completo ou sem chuva registrada, meses com ≥ 27 dias): mediana {ep['vies_rel_mediano']:+.1f}%, {ep['n_dentro_10']} estações dentro de ±10%; correlação mensal média {ep['r_mensal_medio']:.2f}.",
            en=f"Left: mean bias of CHELSA monthly temperature against {e['n']} stations (GHCN-Daily, 1991–2020, same months): {e['vies_medio']:+.2f} °C on average (mean absolute error {e['mae_medio']:.2f} °C); CHELSA is colder at {e['n_mais_frio']} of the {e['n']} stations. Right: relative bias of annual precipitation against {ep['n']} synoptic stations (NOAA GSOD; days with a complete total or no recorded rain, months with ≥ 27 days): median {ep['vies_rel_mediano']:+.1f}%, {ep['n_dentro_10']} stations within ±10%; mean monthly correlation {ep['r_mensal_medio']:.2f}.")),
        dict(arquivo="fig_val_beck.png", largo=True, legenda=dict(
            es=f"Köppen-Geiger 1991–2020 de Beck et al. (2023), V2, 1 km. Concordancia con el mapa de este trabajo: {b_['concordancia']:.1f}% del área ({b_['concordancia_grupos']:.1f}% en los grupos principales).",
            pt=f"Köppen-Geiger 1991–2020 de Beck et al. (2023), V2, 1 km. Concordância com o mapa deste trabalho: {b_['concordancia']:.1f}% da área ({b_['concordancia_grupos']:.1f}% nos grupos principais).",
            en=f"Köppen-Geiger 1991–2020 from Beck et al. (2023), V2, 1 km. Agreement with this work's map: {b_['concordancia']:.1f}% of the area ({b_['concordancia_grupos']:.1f}% for the main groups).")),
        dict(arquivo="fig_val_terraclimate.png", legenda=dict(
            es=f"Köppen-Geiger calculado con las normales 1991–2020 de TerraClimate (~4 km). Concordancia con CHELSA: Köppen {tcv['koppen']:.1f}%, Thornthwaite (humedad) {tcv['umidade']:.1f}%, Holdridge {tcv['zona']:.1f}% del área.",
            pt=f"Köppen-Geiger calculado com as normais 1991–2020 do TerraClimate (~4 km). Concordância com o CHELSA: Köppen {tcv['koppen']:.1f}%, Thornthwaite (umidade) {tcv['umidade']:.1f}%, Holdridge {tcv['zona']:.1f}% da área.",
            en=f"Köppen-Geiger computed from the 1991–2020 TerraClimate normals (~4 km). Agreement with CHELSA: Köppen {tcv['koppen']:.1f}%, Thornthwaite (moisture) {tcv['umidade']:.1f}%, Holdridge {tcv['zona']:.1f}% of the area.")),
        *[dict(arquivo=f"fig_estabilidad_{k}.png", legenda=dict(
            es=f"Estabilidad interanual de la clase, {nm['es']} ({a[k][0]}–{a[k][1]}): porcentaje de años clasificados en la misma clase de la normal 1991–2020 (media {media_est[k]:.0f}%).",
            pt=f"Estabilidade interanual da classe, {nm['pt']} ({a[k][0]}–{a[k][1]}): porcentagem de anos classificados na mesma classe da normal 1991–2020 (média {media_est[k]:.0f}%).",
            en=f"Interannual class stability, {nm['en']} ({a[k][0]}–{a[k][1]}): percentage of years classified in the same class as the 1991–2020 normal (mean {media_est[k]:.0f}%)."))
          for k, nm in (("koppen", dict(es="Köppen-Geiger", pt="Köppen-Geiger", en="Köppen-Geiger")),
                        ("umidade", dict(es="Thornthwaite (humedad)", pt="Thornthwaite (umidade)", en="Thornthwaite (moisture)")),
                        ("zona", dict(es="Holdridge", pt="Holdridge", en="Holdridge")))],
        dict(arquivo="fig_ecorregiones.png", largo=True, legenda=dict(
            es=f"Zonas de vida de Holdridge y límites de las ecorregiones RESOLVE (2017). Zona dominante en las mayores ecorregiones: {eco_txt('es')}. Asignando a cada ecorregión su zona dominante, la correspondencia es del {ec['concordancia']:.1f}% del área.",
            pt=f"Zonas de vida de Holdridge e limites das ecorregiões RESOLVE (2017). Zona dominante nas maiores ecorregiões: {eco_txt('pt')}. Atribuindo a cada ecorregião sua zona dominante, a correspondência é de {ec['concordancia']:.1f}% da área.",
            en=f"Holdridge life zones and RESOLVE (2017) ecoregion boundaries. Dominant zone in the largest ecoregions: {eco_txt('en')}. Assigning each ecoregion its dominant zone, the correspondence is {ec['concordancia']:.1f}% of the area.")),
        dict(arquivo="fig_sensibilidad.png", legenda=dict(
            es="Sensibilidad de las clasificaciones: porcentaje del área del país que cambia de clase al perturbar la temperatura (±0,5 °C y la corrección del sesgo medio frente a las estaciones), la precipitación (±10%), la CAD (50 y 150 mm), la ETP (+10%) o el método de la ETP (Thornthwaite 1948 en lugar de Penman-Monteith; Penman-Monteith en lugar de la ETP de Holdridge), y al usar TerraClimate.",
            pt="Sensibilidade das classificações: porcentagem da área do país que muda de classe ao perturbar a temperatura (±0,5 °C e a correção do viés médio frente às estações), a precipitação (±10%), a CAD (50 e 150 mm), a ETP (+10%) ou o método da ETP (Thornthwaite 1948 em vez de Penman-Monteith; Penman-Monteith em vez da ETP de Holdridge), e ao usar o TerraClimate.",
            en="Sensitivity of the classifications: percentage of the country's area changing class when perturbing temperature (±0.5 °C and the correction of the mean bias against stations), precipitation (±10%), the AWC (50 and 150 mm), PET (+10%) or the PET method (Thornthwaite 1948 instead of Penman-Monteith; Penman-Monteith instead of Holdridge PET), and when using TerraClimate.")),
    ]))
    (C.SITE_ATLAS / "atlas.json").write_text(json.dumps({"grupos": G}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("atlas.json ok")


if __name__ == "__main__":
    main()
