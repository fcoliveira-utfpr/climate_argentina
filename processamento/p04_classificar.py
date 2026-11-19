# -*- coding: utf-8 -*-
"""Classificações de Köppen-Geiger, Thornthwaite (CAD 100 mm, ETP Penman-Monteith do CHELSA) e
Holdridge (ETP de Holdridge = 58,93 x biotemperatura) sobre a normal 1991-2020, pixel a pixel,
dentro da Argentina. Grava dados_brutos/classificacoes/*.tif (sem filtro de moda) e
pixels.npz (índices dos pixels, latitude e todas as saídas como vetores, para as etapas seguintes).
"""
import time

import numpy as np
import rasterio

import classif as K
import config as C


def ler_vetores(mask):
    out = {}
    for v in C.VARIAVEIS:
        a = C.ler_normal(v)
        out[v] = a[:, mask]
        del a
    return out


def gravar(nome, bandas, mask, transform, crs, dtype="float32"):
    shape = mask.shape
    nodata = 0 if dtype == "uint8" else np.nan
    perfil = dict(driver="GTiff", height=shape[0], width=shape[1], count=len(bandas), dtype=dtype,
                  crs=crs, transform=transform, nodata=nodata, compress="deflate",
                  tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(C.CLASSES_DIR / f"{nome}.tif", "w", **perfil) as dst:
        for i, (k, v) in enumerate(bandas.items(), 1):
            g = np.full(shape, nodata, dtype=dtype)
            g[mask] = v
            dst.write(g, i)
            dst.set_band_description(i, k)


def main():
    t0 = time.time()
    C.CLASSES_DIR.mkdir(parents=True, exist_ok=True)
    transform, crs, shape = C.grade()
    with rasterio.open(C.GADM_DIR / "unidades.tif") as src:
        unid = src.read(1)
    mask = unid > 0
    X = ler_vetores(mask)
    ok = K.mascara_valida(X["tas"], X["pr"], X["pet"])
    print(f"pixels no país: {mask.sum()}, com dados completos: {ok.sum()}")
    # pixels sem dado (lagoas/costa) saem da máscara
    l0, c0 = np.where(mask)
    mask[l0[~ok], c0[~ok]] = False
    T, P, PET = X["tas"][:, ok], X["pr"][:, ok], X["pet"][:, ok]
    lin, col = np.where(mask)
    lat = (transform.f + transform.e * (lin + 0.5)).astype("float32")
    area = np.cos(np.radians(lat)).astype("float32")

    kp = K.koppen(T, P, lat)
    print(f"Köppen ok ({time.time() - t0:.0f}s)")
    th = K.thornthwaite(P, PET, lat)
    print(f"Thornthwaite ok ({time.time() - t0:.0f}s)")
    hd = K.holdridge(T, P, lat)
    print(f"Holdridge ok ({time.time() - t0:.0f}s)")
    va = K.variaveis(T, P, PET)

    gravar("koppen", {"koppen": kp}, mask, transform, crs, "uint8")
    gravar("thornthwaite_classes", {k: th[k] for k in K.TH_CODIGOS}, mask, transform, crs, "uint8")
    gravar("thornthwaite_indices", {k: th[k] for k in K.TH_VARS}, mask, transform, crs)
    gravar("holdridge", {"zona": hd["id"]}, mask, transform, crs, "uint8")
    gravar("holdridge_indices", {k: hd[k] for k in K.HD_VARS}, mask, transform, crs)
    gravar("variaveis", va, mask, transform, crs)

    np.savez_compressed(
        C.CLASSES_DIR / "pixels.npz", lin=lin.astype("int32"), col=col.astype("int32"), lat=lat,
        area=area, unidade=unid[mask].astype("int16"),
        koppen=kp, **{f"th_{k}": v for k, v in th.items()},
        holdridge=hd["id"], **{f"hd_{k}": v for k, v in hd.items() if k != "id"},
        **{f"v_{k}": v.astype("float32") for k, v in va.items()},
        tas=T.astype("float32"), pr=P.astype("float32"), pet=PET.astype("float32"),
    )

    def resumo(nome, cod, nomes=None):
        s = {}
        for c in np.unique(cod):
            s[c] = area[cod == c].sum() / area.sum() * 100
        s = sorted(s.items(), key=lambda x: -x[1])
        print(nome, " · ".join(f"{(nomes or {}).get(c, c)} {p:.1f}%" for c, p in s if p >= 0.1))

    from agrometeorologiapy.classificacao_climatica import KOPPEN_CLASSES, HOLDRIDGE_ZONAS_EN
    resumo("Köppen:", kp, KOPPEN_CLASSES)
    resumo("Th umidade:", th["umidade"])
    resumo("Th térmica:", th["termica"])
    resumo("Holdridge:", hd["id"], HOLDRIDGE_ZONAS_EN)
    print(f"Concluído em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
