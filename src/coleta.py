"""Etapa 1 - Coleta: baixa as 2 fontes (InfoDengue e Open-Meteo) para data/raw.

Os CSVs ja vem versionados no repositorio; este script so e necessario para
atualizar os dados (python src/coleta.py --force).
"""
import sys
import time

import pandas as pd
import requests

from config import ANO_FIM, ANO_INI, MUNICIPIOS, RAW

URL_DENGUE = "https://info.dengue.mat.br/api/alertcity"
URL_CLIMA = "https://archive-api.open-meteo.com/v1/archive"


def baixar_dengue(geocode, nome):
    params = dict(geocode=geocode, disease="dengue", format="csv",
                  ew_start=1, ew_end=53, ey_start=ANO_INI, ey_end=ANO_FIM)
    r = requests.get(URL_DENGUE, params=params, timeout=120)
    r.raise_for_status()
    destino = RAW / f"dengue_{geocode}.csv"
    destino.write_text(r.text, encoding="utf-8")
    print(f"[dengue] {nome}: {len(r.text.splitlines()) - 1} semanas")


def baixar_clima(geocode, nome, lat, lon):
    params = dict(latitude=lat, longitude=lon, start_date=f"{ANO_INI}-01-01",
                  end_date=f"{ANO_FIM}-12-31", timezone="America/Sao_Paulo",
                  daily="temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,relative_humidity_2m_mean")
    for tentativa in range(5):
        r = requests.get(URL_CLIMA, params=params, timeout=120)
        if r.status_code == 429:
            time.sleep(20 * (tentativa + 1))
            continue
        r.raise_for_status()
        break
    df = pd.DataFrame(r.json()["daily"]).rename(columns={"time": "data"})
    df.insert(0, "geocode", geocode)
    df.to_csv(RAW / f"clima_{geocode}.csv", index=False)
    print(f"[clima]  {nome}: {len(df)} dias")
    time.sleep(2)


def main(force=False):
    RAW.mkdir(parents=True, exist_ok=True)
    for geocode, nome, _, lat, lon in MUNICIPIOS:
        if force or not (RAW / f"dengue_{geocode}.csv").exists():
            baixar_dengue(geocode, nome)
        if force or not (RAW / f"clima_{geocode}.csv").exists():
            baixar_clima(geocode, nome, lat, lon)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
