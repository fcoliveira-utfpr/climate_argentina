# -*- coding: utf-8 -*-
"""Classificações sobre vetores de pixels (12, N), em blocos, com as funções vetorizadas
da agrometeorologiapy (as mesmas usadas no Paraguai)."""
import numpy as np
import agrometeorologiapy as amp

import config as C

BLOCO = 400_000


def _blocos(n):
    for i in range(0, n, BLOCO):
        yield slice(i, min(i + BLOCO, n))


def koppen(T, P, lat):
    out = np.zeros(T.shape[1], np.uint8)
    for s in _blocos(T.shape[1]):
        out[s] = amp.classificacao_koppen_grade(T[:, s], P[:, s], lat[s])["id"]
    return out


TH_CODIGOS = ["umidade", "subtipo", "termica", "concentracao"]
TH_VARS = ["Im", "Ih", "Ia", "ETP_anual", "DEF_anual", "EXC_anual"]


def thornthwaite(P, PET, lat, cad=C.CAD, so_umidade=False):
    n = P.shape[1]
    out = {k: np.zeros(n, np.uint8) for k in TH_CODIGOS}
    if not so_umidade:
        out.update({k: np.full(n, np.nan, np.float32) for k in TH_VARS})
    cad = np.broadcast_to(np.asarray(cad, float), (n,))
    for s in _blocos(n):
        r = amp.classificacao_thornthwaite_grade(P[:, s], PET[:, s], lat[s], CAD=cad[s])
        for k in out:
            out[k][s] = r[k]
    return out


HD_VARS = ["biotemperatura", "P_anual", "ETP_anual", "razao_ETP"]


def holdridge(T, P, lat, PET=None, so_id=False):
    n = T.shape[1]
    out = {"id": np.zeros(n, np.uint8)}
    if not so_id:
        out.update({k: np.full(n, np.nan, np.float32) for k in HD_VARS})
    for s in _blocos(n):
        r = amp.classificacao_holdridge_grade(T[:, s], P[:, s], lat[s],
                                              ETP=None if PET is None else PET[:, s])
        for k in out:
            out[k][s] = r[k]
    return out


def variaveis(T, P, PET):
    return {
        "t_anual": T.mean(0), "t_mes_frio": T.min(0), "t_mes_quente": T.max(0),
        "p_anual": P.sum(0), "p_mes_seco": P.min(0), "pet_anual": PET.sum(0),
    }


def mascara_valida(*arrs):
    ok = None
    for a in arrs:
        v = np.all(np.isfinite(a), axis=0)
        ok = v if ok is None else ok & v
    return ok
