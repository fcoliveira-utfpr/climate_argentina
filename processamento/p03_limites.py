# -*- coding: utf-8 -*-
"""Limites administrativos (GADM 4.1): departamentos/partidos (nível 2, 502) e províncias (nível 1, 24).

Grava:
  dados/departamentos.geojson  (geometria simplificada ~300 m; id = GID_2, provincia, departamento)
  dados/provincias.geojson     (só desenho)
  dados_brutos/gadm/unidades.tif   (índice 1..N do departamento por pixel da grade CHELSA; 0 = fora)
  dados_brutos/gadm/unidades.csv   (índice -> id, provincia, departamento)
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

import config as C

GPKG = C.GADM_DIR / "gadm41_ARG.gpkg"
TOL = 0.003   # graus (~300 m), simplificação para o site


def corrigir(nome):
    # GADM 4.1 grafa "Rió" (Rió Cuarto, Rió Grande...) em vez de "Río" e divide o partido de
    # San Fernando (Buenos Aires) em duas partes: (1) islas del Delta e (2) sección continental
    return (nome.replace("Rió ", "Río ").replace("San Fernando (1)", "San Fernando (islas)")
            .replace("San Fernando (2)", "San Fernando (continental)"))


def geojson_leve(gdf, campos, arq):
    g = gdf[campos + ["geometry"]].copy()
    g["geometry"] = g.geometry.simplify(TOL, preserve_topology=True)
    texto = g.to_json(drop_id=True, ensure_ascii=False)
    js = json.loads(texto)

    def arred(c):
        return [arred(x) for x in c] if isinstance(c[0], list) else [round(c[0], 4), round(c[1], 4)]
    for f in js["features"]:
        f["geometry"]["coordinates"] = arred(f["geometry"]["coordinates"])
    arq.write_text(json.dumps(js, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{arq.name}: {arq.stat().st_size / 1e6:.2f} MB")


def main():
    C.SITE_DADOS.mkdir(parents=True, exist_ok=True)
    g2 = gpd.read_file(GPKG, layer="ADM_ADM_2")
    g2["id"] = g2["GID_2"]
    g2["provincia"] = g2["NAME_1"].map(corrigir)
    g2["departamento"] = g2["NAME_2"].map(corrigir)
    g2 = g2.sort_values(["provincia", "departamento"]).reset_index(drop=True)
    g2["indice"] = np.arange(1, len(g2) + 1)

    g1 = gpd.read_file(GPKG, layer="ADM_ADM_1")
    g1["id"] = g1["GID_1"]
    g1["provincia"] = g1["NAME_1"].map(corrigir)

    geojson_leve(g2, ["id", "provincia", "departamento"], C.SITE_DADOS / "departamentos.geojson")
    geojson_leve(g1, ["id", "provincia"], C.SITE_DADOS / "provincias.geojson")

    transform, crs, shape = C.grade()
    idx = rasterize(zip(g2.geometry, g2.indice), out_shape=shape, transform=transform,
                    fill=0, dtype="int16")
    # unidades pequenas sem nenhum centro de pixel: usa all_touched só para elas
    faltam = sorted(set(g2.indice) - set(np.unique(idx)))
    if faltam:
        sub = g2[g2.indice.isin(faltam)]
        extra = rasterize(zip(sub.geometry, sub.indice), out_shape=shape, transform=transform,
                          fill=0, dtype="int16", all_touched=True)
        idx = np.where((idx == 0) & (extra > 0), extra, idx)
        print("Rasterizadas com all_touched:", list(sub.departamento))
    perfil = dict(driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="int16",
                  crs=crs, transform=transform, nodata=0, compress="deflate")
    with rasterio.open(C.GADM_DIR / "unidades.tif", "w", **perfil) as dst:
        dst.write(idx, 1)
    contagem = pd.Series(idx[idx > 0]).value_counts()
    tab = g2[["indice", "id", "provincia", "departamento"]].copy()
    tab["n_pixels"] = tab.indice.map(contagem).fillna(0).astype(int)
    tab.to_csv(C.GADM_DIR / "unidades.csv", index=False, encoding="utf-8")
    print(f"{len(tab)} departamentos; pixels por unidade: mín {tab.n_pixels.min()}, "
          f"mediana {tab.n_pixels.median():.0f}; total {tab.n_pixels.sum()}")
    print(tab.nsmallest(5, "n_pixels").to_string())


if __name__ == "__main__":
    main()
