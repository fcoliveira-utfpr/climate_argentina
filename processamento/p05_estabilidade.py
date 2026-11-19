# -*- coding: utf-8 -*-
"""Estabilidade interanual das classes: cada ano (12 meses) é classificado e comparado com a classe
da normal 1991-2020. Estabilidade = % de anos na mesma classe da normal.

Köppen e Holdridge (ETP de Holdridge, só T e P): 1991-2020. Thornthwaite (umidade; ETP do CHELSA):
anos com os 12 meses de ETP, 1991-2018.
"""
import time

import numpy as np

import classif as K
import config as C


def ler_ano(var, ano, lin, col):
    meses = []
    for m in range(1, 13):
        d = C.ler_mensal(var, ano, m)
        if d is None:
            return None
        meses.append(d[lin, col])
    return np.stack(meses).astype("float32")


def main():
    t0 = time.time()
    px = np.load(C.CLASSES_DIR / "pixels.npz")
    lin, col, lat = px["lin"], px["col"], px["lat"]
    n = len(lin)
    iguais = {k: np.zeros(n, np.int16) for k in ("koppen", "umidade", "zona")}
    validos = {k: np.zeros(n, np.int16) for k in iguais}
    anos_usados = {k: [] for k in iguais}
    C.ANUAL_DIR.mkdir(parents=True, exist_ok=True)
    for ano in C.ANOS:
        T = ler_ano("tas", ano, lin, col)
        P = ler_ano("pr", ano, lin, col)
        PET = ler_ano("pet", ano, lin, col)
        ok = K.mascara_valida(T, P)
        kp = K.koppen(T, P, lat)
        hd = K.holdridge(T, P, lat, so_id=True)["id"]
        for k, cls, ref in (("koppen", kp, px["koppen"]), ("zona", hd, px["holdridge"])):
            iguais[k] += ok & (cls == ref)
            validos[k] += ok
            anos_usados[k].append(ano)
        salvar = dict(koppen=kp, zona=hd)
        if PET is not None:
            okp = ok & K.mascara_valida(PET)
            um = K.thornthwaite(P, PET, lat, so_umidade=True)["umidade"]
            iguais["umidade"] += okp & (um == px["th_umidade"])
            validos["umidade"] += okp
            anos_usados["umidade"].append(ano)
            salvar["umidade"] = um
        np.savez_compressed(C.ANUAL_DIR / f"classes_{ano}.npz", **salvar)
        print(f"{ano}: ok ({time.time() - t0:.0f}s){'' if PET is not None else ' — sem ETP completa'}")

    est = {k: np.where(validos[k] > 0, 100 * iguais[k] / np.maximum(validos[k], 1), np.nan)
           .astype("float32") for k in iguais}
    area = px["area"]
    for k, v in est.items():
        m = np.nansum(v * area) / area[np.isfinite(v)].sum()
        print(f"{k}: anos {anos_usados[k][0]}-{anos_usados[k][-1]} ({len(anos_usados[k])}), "
              f"estabilidade média {m:.1f}%")
    np.savez_compressed(C.CLASSES_DIR / "estabilidade.npz", **est,
                        **{f"anos_{k}": np.array(v) for k, v in anos_usados.items()})


if __name__ == "__main__":
    main()
