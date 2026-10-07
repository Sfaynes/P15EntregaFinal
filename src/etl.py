"""Etapa 2 - ETL: le os CSVs brutos, trata, valida e carrega no PostgreSQL."""
import pandas as pd
from sqlalchemy import text

from config import MUNICIPIOS, RAW, SQL_DIR, get_engine


def criar_schema(eng):
    sql = (SQL_DIR / "01_schema.sql").read_text(encoding="utf-8")
    with eng.begin() as c:
        c.exec_driver_sql(sql)


# ---------- Extract ----------
def extrair():
    dengue = pd.concat([pd.read_csv(RAW / f"dengue_{m[0]}.csv").assign(geocode=m[0]) for m in MUNICIPIOS],
                       ignore_index=True)
    clima = pd.concat([pd.read_csv(RAW / f"clima_{m[0]}.csv") for m in MUNICIPIOS], ignore_index=True)
    return dengue, clima


# ---------- Transform ----------
def transformar_dengue(df):
    df = df.copy()
    df["data_ini"] = pd.to_datetime(df["data_iniSE"])
    df["se"] = df["SE"].astype(int)
    out = pd.DataFrame({
        "geocode": df["geocode"].astype(int),
        "se": df["se"],
        "data_ini": df["data_ini"],
        "casos": df["casos"].fillna(0).astype(int),
        "casos_est": df["casos_est"].fillna(df["casos"]).astype(float),
        "populacao": df["pop"].round().astype(int),
        "inc100k": df["p_inc100k"].astype(float),
        "nivel_alerta": df["nivel"].astype("Int64"),
        "rt": df["Rt"].astype(float),
    })
    out = out.drop_duplicates(["geocode", "se"]).sort_values(["geocode", "se"])
    return out


def transformar_clima(df):
    out = pd.DataFrame({
        "geocode": df["geocode"].astype(int),
        "data": pd.to_datetime(df["data"]),
        "temp_media": df["temperature_2m_mean"],
        "temp_max": df["temperature_2m_max"],
        "temp_min": df["temperature_2m_min"],
        "precip_mm": df["precipitation_sum"].clip(lower=0),
        "umid_media": df["relative_humidity_2m_mean"],
    }).drop_duplicates(["geocode", "data"])
    # lacunas pontuais: interpola dentro de cada municipio
    cols = ["temp_media", "temp_max", "temp_min", "umid_media"]
    out[cols] = out.groupby("geocode")[cols].transform(lambda s: s.interpolate(limit=3))
    out["precip_mm"] = out["precip_mm"].fillna(0)
    return out


def validar(dengue, clima):
    assert len(dengue) > 0 and len(clima) > 0, "dados vazios"
    assert dengue["inc100k"].ge(0).all(), "incidencia negativa"
    assert clima["temp_media"].between(-10, 50).all(), "temperatura fora do intervalo"
    assert clima["umid_media"].between(0, 100).all(), "umidade fora do intervalo"
    print(f"Validacoes OK | dengue={len(dengue)} linhas, clima={len(clima)} linhas")


# ---------- Load ----------
def carregar(eng, dengue, clima):
    dim_mun = pd.DataFrame(MUNICIPIOS, columns=["geocode", "nome", "uf", "latitude", "longitude"])
    dim_sem = (dengue[["se", "data_ini"]].drop_duplicates("se").assign(
        ano=lambda d: d["se"] // 100, semana=lambda d: d["se"] % 100))
    with eng.begin() as c:
        dim_mun.to_sql("dim_municipio", c, if_exists="append", index=False)
        dim_sem.to_sql("dim_semana", c, if_exists="append", index=False)
        dengue.drop(columns="data_ini").to_sql("fato_dengue_semana", c, if_exists="append", index=False, chunksize=1000)
        clima.to_sql("fato_clima_dia", c, if_exists="append", index=False, chunksize=2000)


def main():
    eng = get_engine()
    criar_schema(eng)
    dengue_raw, clima_raw = extrair()
    dengue, clima = transformar_dengue(dengue_raw), transformar_clima(clima_raw)
    validar(dengue, clima)
    carregar(eng, dengue, clima)
    with eng.connect() as c:
        for t in ["dim_municipio", "dim_semana", "fato_dengue_semana", "fato_clima_dia", "vw_base_modelo"]:
            print(f"{t}: {c.execute(text(f'select count(*) from {t}')).scalar()} linhas")


if __name__ == "__main__":
    main()
