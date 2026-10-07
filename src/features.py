"""Etapa 3 - Features: monta a base analitica a partir do PostgreSQL e cria as variaveis.

Alvo: surto_futuro = 1 se a incidencia (por 100 mil hab.) daqui a HORIZONTE semanas >= LIMIAR_SURTO.
Todas as features usam apenas informacao disponivel ate a semana t (sem vazamento).
"""
import numpy as np
import pandas as pd

from config import HORIZONTE, LIMIAR_SURTO, PROCESSED, get_engine

FEATURES = [
    "inc_t", "inc_lag1", "inc_lag2", "inc_lag3", "inc_media4", "inc_delta1", "inc_tendencia4",
    "nivel_alerta", "rt",
    "temp_media", "temp_media_lag2", "temp_media4", "temp_min4",
    "precip_mm", "precip_soma4", "precip_soma8",
    "umid_media", "umid_media4",
    "semana_sin", "semana_cos", "log_populacao",
]
ALVO = "surto_futuro"


def carregar_base(eng=None):
    eng = eng or get_engine()
    return pd.read_sql("select * from vw_base_modelo order by geocode, se", eng, parse_dates=["data_ini"])


def criar_features(df):
    df = df.sort_values(["geocode", "se"]).reset_index(drop=True)
    g = df.groupby("geocode")

    df["inc_t"] = df["inc100k"]
    for k in (1, 2, 3):
        df[f"inc_lag{k}"] = g["inc100k"].shift(k)
    df["inc_media4"] = g["inc100k"].transform(lambda s: s.rolling(4).mean())
    df["inc_delta1"] = df["inc_t"] - df["inc_lag1"]
    df["inc_tendencia4"] = df["inc_t"] - g["inc100k"].shift(4)

    df["temp_media_lag2"] = g["temp_media"].shift(2)
    df["temp_media4"] = g["temp_media"].transform(lambda s: s.rolling(4).mean())
    df["temp_min4"] = g["temp_min"].transform(lambda s: s.rolling(4).min())
    df["precip_soma4"] = g["precip_mm"].transform(lambda s: s.rolling(4).sum())
    df["precip_soma8"] = g["precip_mm"].transform(lambda s: s.rolling(8).sum())
    df["umid_media4"] = g["umid_media"].transform(lambda s: s.rolling(4).mean())

    df["semana_sin"] = np.sin(2 * np.pi * df["semana"] / 52)
    df["semana_cos"] = np.cos(2 * np.pi * df["semana"] / 52)
    df["log_populacao"] = np.log(df["populacao"])
    df["rt"] = df["rt"].fillna(1.0)
    df["nivel_alerta"] = df["nivel_alerta"].fillna(1)

    df["inc_futura"] = g["inc100k"].shift(-HORIZONTE)
    df[ALVO] = (df["inc_futura"] >= LIMIAR_SURTO).astype("float").where(df["inc_futura"].notna())

    colunas = ["geocode", "municipio", "se", "ano", "data_ini", *FEATURES, "inc_futura", ALVO]
    return df[colunas].dropna().reset_index(drop=True).astype({ALVO: int})


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    feats = criar_features(carregar_base())
    feats.to_csv(PROCESSED / "features.csv", index=False)
    print(f"features.csv: {feats.shape} | prevalencia do alvo = {feats[ALVO].mean():.1%}")


if __name__ == "__main__":
    main()

