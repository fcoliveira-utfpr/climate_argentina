# -*- coding: utf-8 -*-
"""Roda a cadeia completa, em ordem. Uso: python executar_tudo.py [etapa_inicial]
(ex.: python executar_tudo.py p04 para recomeçar da classificação)."""
import runpy
import sys
import time

ETAPAS = ["p01_baixar_chelsa", "p02_normal", "p03_limites", "p04_classificar", "p05_estabilidade",
          "p06_unidades", "p07_camadas", "p08_validacao", "p09_atlas"]

inicio = sys.argv[1] if len(sys.argv) > 1 else "p01"
for e in ETAPAS[[i for i, x in enumerate(ETAPAS) if x.startswith(inicio)][0]:]:
    t = time.time()
    print(f"\n===== {e} =====", flush=True)
    runpy.run_module(e, run_name="__main__")
    print(f"----- {e}: {time.time() - t:.0f} s", flush=True)
