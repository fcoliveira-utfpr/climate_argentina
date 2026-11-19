# -*- coding: utf-8 -*-
"""Normal climatológica 1991-2020 (média mensal por pixel, tolerante a anos faltantes) de tas, pr e
pet, em GeoTIFFs de 12 bandas. A ETP (Penman-Monteith) não existe na fonte de mai/2019 a dez/2020:
sua normal usa 28-29 anos."""
import numpy as np
import rasterio

import config as C


def main():
    C.NORMAL_DIR.mkdir(parents=True, exist_ok=True)
    ref = C.caminho_mensal("tas", C.ANO_INICIO, 1)
    with rasterio.open(ref) as src:
        perfil = dict(driver="GTiff", height=src.height, width=src.width, count=12, dtype="float32",
                      crs=src.crs, transform=src.transform, nodata=np.nan, compress="deflate",
                      predictor=3, tiled=True, blockxsize=512, blockysize=512)
    for var in C.VARIAVEIS:
        destino = C.caminho_normal(var)
        with rasterio.open(destino, "w", **perfil) as dst:
            for mes in range(1, 13):
                soma = np.zeros((perfil["height"], perfil["width"]), "float64")
                n = np.zeros(soma.shape, "int16")
                anos = 0
                for ano in C.ANOS:
                    d = C.ler_mensal(var, ano, mes)
                    if d is None:
                        continue
                    ok = np.isfinite(d)
                    soma[ok] += d[ok]
                    n += ok
                    anos += 1
                media = np.where(n > 0, soma / np.maximum(n, 1), np.nan).astype("float32")
                dst.write(media, mes)
                dst.set_band_description(mes, f"{var}_{mes:02d}")
                print(f"{var} mês {mes:02d}: {anos} anos")
        print("->", destino)


if __name__ == "__main__":
    main()
