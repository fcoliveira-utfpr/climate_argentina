# -*- coding: utf-8 -*-
"""Baixa e recorta para a Argentina os arquivos mensais do CHELSA V2.1 (tas, pr, pet), 1991-2020.

Lê só a janela do bbox (via /vsicurl/ e o tiling COG dos arquivos remotos) e grava o recorte
no tipo original (uint16), guardando escala, deslocamento e nodata nas tags -- a conversão para
unidades físicas fica em config.ler_mensal. Grava também um manifesto com os meses faltantes
(a ETP não existe na fonte de mai/2019 a dez/2020).
"""
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import rasterio
import requests
from rasterio.windows import from_bounds
from tqdm import tqdm

import config as C

MAX_TENTATIVAS = 4
N_THREADS = 8


def existe_remoto(url):
    for t in range(MAX_TENTATIVAS + 2):
        try:
            r = requests.head(url, timeout=30)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
        except requests.RequestException:
            pass
        time.sleep(2 * (t + 1))
    raise RuntimeError(f"Não foi possível verificar {url}")


def recortar(var, ano, mes, url):
    destino = C.caminho_mensal(var, ano, mes)
    if destino.exists():
        return "ja_existe"
    for t in range(MAX_TENTATIVAS):
        try:
            with rasterio.open("/vsicurl/" + url) as src:
                janela = from_bounds(C.OESTE, C.SUL, C.LESTE, C.NORTE, transform=src.transform)
                janela = janela.round_offsets().round_lengths()
                dados = src.read(1, window=janela)
                transform = src.window_transform(janela)
                tags = {"scale": src.scales[0], "offset": src.offsets[0], "nodata": src.nodata}
            destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_suffix(".tmp.tif")
            perfil = dict(driver="GTiff", height=dados.shape[0], width=dados.shape[1], count=1,
                          dtype=dados.dtype, crs="EPSG:4326", transform=transform,
                          nodata=tags["nodata"], compress="deflate", predictor=2,
                          tiled=True, blockxsize=512, blockysize=512)
            with rasterio.open(tmp, "w", **perfil) as dst:
                dst.write(dados, 1)
                dst.update_tags(**{k: str(v) for k, v in tags.items()}, var=var, ano=ano, mes=mes)
            tmp.replace(destino)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            if t == MAX_TENTATIVAS - 1:
                return f"erro:{exc}"
            time.sleep(3 * (t + 1))
    return "erro"


def main():
    tarefas = [(v, a, m, C.BASE_URL.format(var=v, ano=a, mes=m))
               for v in C.VARIAVEIS for a in C.ANOS for m in range(1, 13)]
    pendentes = [t for t in tarefas if not C.caminho_mensal(*t[:3]).exists()]
    print(f"{len(tarefas)} arquivos; {len(pendentes)} pendentes")

    manifesto = []
    disponiveis = []
    with ThreadPoolExecutor(N_THREADS) as ex:
        fut = {ex.submit(existe_remoto, t[3]): t for t in pendentes}
        for f in tqdm(as_completed(fut), total=len(fut), desc="Checando URLs", mininterval=10):
            t = fut[f]
            ok = f.result()
            manifesto.append(dict(variavel=t[0], ano=t[1], mes=t[2], encontrado=ok, url=t[3]))
            if ok:
                disponiveis.append(t)

    C.BRUTOS.mkdir(parents=True, exist_ok=True)
    arq_man = C.BRUTOS / "manifesto_chelsa.csv"
    antigos = []
    if arq_man.exists():
        with open(arq_man, encoding="utf-8") as f:
            antigos = [r for r in csv.DictReader(f)
                       if (r["variavel"], int(r["ano"]), int(r["mes"])) not in
                       {(m["variavel"], m["ano"], m["mes"]) for m in manifesto}]
    todos = sorted(antigos + manifesto, key=lambda r: (r["variavel"], int(r["ano"]), int(r["mes"])))
    with open(arq_man, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["variavel", "ano", "mes", "encontrado", "url"])
        w.writeheader()
        w.writerows(todos)
    faltam = [(m["variavel"], m["ano"], m["mes"]) for m in manifesto if not m["encontrado"]]
    print(f"Faltantes na fonte: {len(faltam)} -> {faltam[:30]}")

    erros = []
    with ThreadPoolExecutor(N_THREADS) as ex:
        fut = {ex.submit(recortar, *t): t for t in disponiveis}
        for f in tqdm(as_completed(fut), total=len(fut), desc="Recortando", mininterval=30):
            s = f.result()
            if s.startswith("erro"):
                erros.append((fut[f][:3], s))
    print(f"Concluído. Erros: {len(erros)}")
    for e in erros:
        print("  ", e)


if __name__ == "__main__":
    main()
