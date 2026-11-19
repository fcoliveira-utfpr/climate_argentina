# -*- coding: utf-8 -*-
"""Configuração comum do processamento ClimaTec AR (Argentina).

Mesma metodologia do ClimaTec PY (climate_paraguay): CHELSA V2.1 mensal 1991-2020,
classificações de Köppen-Geiger, Thornthwaite e Holdridge pixel a pixel (agrometeorologiapy),
resumo por departamento/partido (GADM nível 2) e por província (GADM nível 1).
"""
from pathlib import Path

import numpy as np
import rasterio

RAIZ = Path(__file__).resolve().parent.parent          # raiz do repositório (site)
BRUTOS = RAIZ / "dados_brutos"                         # não versionado (.gitignore)
MENSAL_DIR = BRUTOS / "chelsa_mensal"                  # recortes mensais (uint16 bruto)
NORMAL_DIR = BRUTOS / "normal_1991_2020"
CLASSES_DIR = BRUTOS / "classificacoes"
ANUAL_DIR = BRUTOS / "anual"                           # classificações ano a ano (estabilidade)
GADM_DIR = BRUTOS / "gadm"
EXTERNOS_DIR = BRUTOS / "externos"                     # Beck et al., estações, ecorregiões, TerraClimate

SITE_DADOS = RAIZ / "dados"
SITE_CAMADAS = SITE_DADOS / "camadas"
SITE_ATLAS = RAIZ / "atlas"

PAIS = "ARG"
VARIAVEIS = ["tas", "pr", "pet"]
ANO_INICIO, ANO_FIM = 1991, 2020
ANOS = list(range(ANO_INICIO, ANO_FIM + 1))

# Bbox da Argentina continental + Tierra del Fuego, com margem de 0,5° (como no Paraguai)
OESTE, SUL, LESTE, NORTE = -74.1, -55.6, -53.1, -21.3

CAD = 100.0           # mm, Thornthwaite
LIMIAR_COMPOSICAO = 0.5   # % mínimo de área para entrar na composição da unidade
IDIOMAS = ["es", "pt", "en"]

BASE_URL = ("https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/"
            "{var}/{ano}/CHELSA_{var}_{mes:02d}_{ano}_V.2.1.tif")


def caminho_mensal(var, ano, mes):
    return MENSAL_DIR / var / str(ano) / f"CHELSA_{var}_{mes:02d}_{ano}_arg.tif"


def caminho_normal(var):
    return NORMAL_DIR / f"chelsa_arg_{var}_normal_1991_2020.tif"


def ler_mensal(var, ano, mes):
    """Lê um recorte mensal em unidades físicas (tas °C, pr e pet mm/mês); NaN = sem dado.
    None se o arquivo não existe (pet tem meses faltantes na fonte)."""
    p = caminho_mensal(var, ano, mes)
    if not p.exists():
        return None
    with rasterio.open(p) as src:
        bruto = src.read(1)
        tags = src.tags()
    escala, desloc = float(tags["scale"]), float(tags["offset"])
    dados = bruto.astype("float32") * escala + desloc
    if var == "tas":
        dados -= 273.15
    dados[bruto == int(float(tags["nodata"]))] = np.nan
    return dados


def grade():
    """(transform, crs, shape) da grade CHELSA recortada (a partir da normal de tas)."""
    ref = caminho_normal("tas")
    if not ref.exists():
        ref = caminho_mensal("tas", ANO_INICIO, 1)
    with rasterio.open(ref) as src:
        return src.transform, src.crs, src.shape


def area_pixel(transform, shape):
    """Peso de área de cada pixel (cos da latitude), formato `shape`."""
    return np.cos(np.radians(latitudes(transform, shape))).astype("float32")


def latitudes(transform, shape):
    linhas = np.arange(shape[0]) + 0.5
    lat = transform.f + transform.e * linhas
    return np.broadcast_to(lat[:, None], shape)


def ler_normal(var):
    with rasterio.open(caminho_normal(var)) as src:
        return src.read().astype("float32")
