# -*- coding: utf-8 -*-
"""Resumo por departamento/partido: classe majoritária por área (pixels ponderados por cos(lat)),
composição (% da área de cada classe, >= 0,5%), médias das variáveis, normal mensal e estabilidade.

Saídas em dados/: departamentos_{koppen,thornthwaite,holdridge}.csv, composicao_departamentos.json,
mensal_departamentos.json e resumo_nacional.json (% da área do país por classe).
"""
import json

import numpy as np
import pandas as pd

import config as C

LEG = json.loads((C.RAIZ / "processamento" / "legendas_base.json").read_text(encoding="utf-8"))
CAMADAS = {"koppen": "koppen", "th_umidade": "th_umidade", "th_subtipo": "th_subtipo",
           "th_termica": "th_termica", "th_concentracao": "th_concentracao", "holdridge": "holdridge"}


def letra(camada, cod):
    return LEG[camada + "_todas"][str(int(cod))]["nome"]["es"].split(" — ")[0]


def composicao(unid, cod, area, n_unid):
    """matriz (n_unid+1, 256) de área por unidade e classe."""
    m = np.bincount(unid.astype(np.int64) * 256 + cod, weights=area, minlength=(n_unid + 1) * 256)
    return m.reshape(n_unid + 1, 256)


def media(unid, x, area, n_unid):
    ok = np.isfinite(x)
    s = np.bincount(unid[ok], weights=(x * area)[ok], minlength=n_unid + 1)
    w = np.bincount(unid[ok], weights=area[ok], minlength=n_unid + 1)
    return np.where(w > 0, s / np.maximum(w, 1e-12), np.nan)


def main():
    px = np.load(C.CLASSES_DIR / "pixels.npz")
    est = np.load(C.CLASSES_DIR / "estabilidade.npz")
    tab = pd.read_csv(C.GADM_DIR / "unidades.csv")
    n = int(tab.indice.max())
    unid, area = px["unidade"].astype(np.int64), px["area"].astype("float64")

    cods = {"koppen": px["koppen"], "th_umidade": px["th_umidade"], "th_subtipo": px["th_subtipo"],
            "th_termica": px["th_termica"], "th_concentracao": px["th_concentracao"],
            "holdridge": px["holdridge"]}
    comp_json, maj, pct, txt = {}, {}, {}, {}
    nacional = {}
    for camada, cod in cods.items():
        m = composicao(unid, cod.astype(np.int64), area, n)
        m[:, 0] = 0
        tot = m.sum(1, keepdims=True)
        p = np.where(tot > 0, 100 * m / np.maximum(tot, 1e-12), 0)
        maj[camada] = p.argmax(1)
        pct[camada] = p.max(1)
        nac = m.sum(0)
        nacional[camada] = {str(c): round(100 * nac[c] / nac.sum(), 2) for c in np.argsort(-nac) if nac[c] > 0}
        txt[camada] = {}
        for _, r in tab.iterrows():
            i = r.indice
            lista = [[int(c), round(float(p[i, c]), 1)] for c in np.argsort(-p[i]) if p[i, c] >= C.LIMIAR_COMPOSICAO]
            comp_json.setdefault(r.id, {})[camada] = lista
            nome = (lambda c: str(c)) if camada == "holdridge" else (lambda c, cam=camada: letra(cam, c))
            txt[camada][i] = " · ".join(f"{nome(c)} {pv:.1f}%" for c, pv in lista)

    med = {k: media(unid, px[k].astype("float64"), area, n) for k in px.files
           if k.startswith(("v_", "th_I", "th_ETP", "th_DEF", "th_EXC", "hd_"))}
    estab = {k: media(unid, est[k].astype("float64"), area, n) for k in ("koppen", "umidade", "zona")}

    base = tab[tab.n_pixels > 0].copy()
    ii = base.indice.values
    b = base[["id", "provincia", "departamento"]].reset_index(drop=True)
    r2 = lambda a: np.round(a[ii], 2)

    kp = b.copy()
    kp["koppen"] = [letra("koppen", c) for c in maj["koppen"][ii]]
    kp["koppen_id"] = maj["koppen"][ii]
    kp["pct_area"] = r2(pct["koppen"])
    for k in ("t_anual", "t_mes_frio", "t_mes_quente", "p_anual", "p_mes_seco", "pet_anual"):
        kp[k] = r2(med["v_" + k])
    kp["composicao"] = [txt["koppen"][i] for i in ii]
    kp["estabilidad"] = r2(estab["koppen"])
    kp.to_csv(C.SITE_DADOS / "departamentos_koppen.csv", index=False, encoding="utf-8")

    th = b.copy()
    for c, col in (("th_umidade", "umidade_id"), ("th_subtipo", "subtipo_id"),
                   ("th_termica", "termica_id"), ("th_concentracao", "concentracao_id")):
        th[col] = maj[c][ii]
    th["tipo"] = [letra("th_umidade", a) + letra("th_subtipo", s) + letra("th_termica", t)
                  + letra("th_concentracao", c) for a, s, t, c in
                  zip(th.umidade_id, th.subtipo_id, th.termica_id, th.concentracao_id)]
    th["pct_area"] = r2(pct["th_umidade"])
    for k in ("Im", "Ih", "Ia", "ETP_anual", "DEF_anual", "EXC_anual"):
        th[k] = r2(med["th_" + k])
    th["composicao_umidade"] = [txt["th_umidade"][i] for i in ii]
    th["estabilidad"] = r2(estab["umidade"])
    th.to_csv(C.SITE_DADOS / "departamentos_thornthwaite.csv", index=False, encoding="utf-8")

    hd = b.copy()
    hd["zona_id"] = maj["holdridge"][ii]
    hd["pct_area"] = r2(pct["holdridge"])
    for k in ("biotemperatura", "P_anual", "ETP_anual", "razao_ETP"):
        hd[k] = r2(med["hd_" + k])
    hd["composicao"] = [txt["holdridge"][i] for i in ii]
    hd["estabilidad"] = r2(estab["zona"])
    hd.to_csv(C.SITE_DADOS / "departamentos_holdridge.csv", index=False, encoding="utf-8")

    mensal = {}
    for v in ("tas", "pr", "pet"):
        X = px[v]
        for mes in range(12):
            mm = media(unid, X[mes].astype("float64"), area, n)
            for _, r in base.iterrows():
                mensal.setdefault(r.id, {}).setdefault(v, []).append(round(float(mm[r.indice]), 1))
    dump = dict(ensure_ascii=False, separators=(",", ":"))
    (C.SITE_DADOS / "mensal_departamentos.json").write_text(json.dumps(mensal, **dump), encoding="utf-8")
    comp_json = {k: v for k, v in comp_json.items() if k in set(b.id)}
    (C.SITE_DADOS / "composicao_departamentos.json").write_text(json.dumps(comp_json, **dump), encoding="utf-8")
    (C.CLASSES_DIR / "resumo_nacional.json").write_text(json.dumps(nacional, indent=1), encoding="utf-8")

    print(f"{len(b)} departamentos com dados")
    print(kp.koppen.value_counts().head(12).to_string())
    print(th.tipo.value_counts().head(8).to_string())
    for k, v in estab.items():
        print(k, "estabilidade média (deptos):", np.nanmean(v[ii]).round(1))


if __name__ == "__main__":
    main()
