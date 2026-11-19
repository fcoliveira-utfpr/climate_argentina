# -*- coding: utf-8 -*-
"""Camadas do mapa: classificação pixel a pixel com filtro de moda 3x3 (remove pixels isolados),
recortada pelo contorno do país, reprojetada para Web Mercator (vizinho mais próximo) e gravada como
PNG com transparência. Grava também dados/camadas.json (limites) e dados/legendas.json."""
import json

import numpy as np
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from scipy.ndimage import uniform_filter

import config as C

LEG = json.loads((C.RAIZ / "processamento" / "legendas_base.json").read_text(encoding="utf-8"))
CAMADAS = {"koppen": "koppen", "th_umidade": "th_umidade", "th_subtipo": "th_subtipo",
           "th_termica": "th_termica", "th_concentracao": "th_concentracao", "holdridge": "holdridge"}


def filtro_moda(g):
    """Moda 3x3 entre as classes > 0; empate mantém a classe original; fora (0) continua 0."""
    melhor_n = np.zeros(g.shape, np.float32)
    melhor_c = g.copy()
    n_orig = np.zeros(g.shape, np.float32)
    for c in np.unique(g[g > 0]):
        n = uniform_filter((g == c).astype(np.float32), size=3, mode="constant")
        maior = n > melhor_n + 1e-6
        melhor_c[maior] = c
        melhor_n[maior] = n[maior]
        n_orig[g == c] = n[g == c]
    saida = np.where(n_orig >= melhor_n - 1e-6, g, melhor_c)
    return np.where(g > 0, saida, 0).astype(np.uint8)


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def main():
    C.SITE_CAMADAS.mkdir(parents=True, exist_ok=True)
    px = np.load(C.CLASSES_DIR / "pixels.npz")
    transform, crs, shape = C.grade()
    lin, col = px["lin"], px["col"]

    # recorte justo da área com dados
    l0, l1, c0, c1 = lin.min(), lin.max() + 1, col.min(), col.max() + 1
    sub_shape = (l1 - l0, c1 - c0)
    sub_tr = transform * transform.translation(c0, l0)
    oeste, sul, leste, norte = array_bounds(*sub_shape, sub_tr)
    # mesma largura em pixels da grade original (altura proporcional)
    _, w0, h0 = calculate_default_transform("EPSG:4326", "EPSG:3857", sub_shape[1], sub_shape[0],
                                            oeste, sul, leste, norte)
    w, h = sub_shape[1], int(round(h0 * sub_shape[1] / w0))
    dst_tr, w, h = calculate_default_transform("EPSG:4326", "EPSG:3857", sub_shape[1], sub_shape[0],
                                               oeste, sul, leste, norte, dst_width=w, dst_height=h)
    b = array_bounds(h, w, dst_tr)
    lo0, la0, lo1, la1 = transform_bounds("EPSG:3857", "EPSG:4326", *b)

    chaves = {"koppen": "koppen", "th_umidade": "th_umidade", "th_subtipo": "th_subtipo",
              "th_termica": "th_termica", "th_concentracao": "th_concentracao", "holdridge": "holdridge"}
    camadas_json, legendas = {}, {}
    for camada, chave in chaves.items():
        g = np.zeros(sub_shape, np.uint8)
        g[lin - l0, col - c0] = px[chave]
        g = filtro_moda(g)
        merc = np.zeros((h, w), np.uint8)
        reproject(g, merc, src_transform=sub_tr, src_crs="EPSG:4326", dst_transform=dst_tr,
                  dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
        todas = LEG[camada + "_todas"]
        presentes = sorted(int(c) for c in np.unique(px[chave]) if c > 0)
        pal = [0, 0, 0] * 256
        for c in presentes:
            pal[3 * c:3 * c + 3] = hex_rgb(todas[str(c)]["cor"])
        img = Image.fromarray(merc, mode="P")
        img.putpalette(pal)
        arq = C.SITE_CAMADAS / f"{camada}.png"
        img.save(arq, optimize=True, transparency=0)
        camadas_json[camada] = {"png": f"dados/camadas/{camada}.png", "limites": [[la0, lo0], [la1, lo1]]}
        legendas[camada] = {str(c): todas[str(c)] for c in presentes}
        print(f"{camada}: {w}x{h}, {arq.stat().st_size / 1e6:.2f} MB, classes {presentes}")
    legendas.update(LEG)
    (C.SITE_DADOS / "camadas.json").write_text(json.dumps(camadas_json, indent=1), encoding="utf-8")
    (C.SITE_DADOS / "legendas.json").write_text(json.dumps(legendas, ensure_ascii=False, indent=1),
                                                encoding="utf-8")


if __name__ == "__main__":
    main()
