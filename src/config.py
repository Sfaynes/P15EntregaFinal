"""Configuracoes compartilhadas do pipeline."""
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"

ANO_INI, ANO_FIM = 2021, 2024
ANO_TESTE = 2024  # split temporal: treino 2021-2023, teste 2024
HORIZONTE = 4  # semanas de antecedencia da previsao
LIMIAR_SURTO = 50.0  # casos estimados por 100 mil hab. na semana (alta incidencia)

# (geocode IBGE, nome, UF, latitude, longitude)
MUNICIPIOS = [
    (3304557, "Rio de Janeiro", "RJ", -22.90, -43.20),
    (3550308, "Sao Paulo", "SP", -23.55, -46.63),
    (3106200, "Belo Horizonte", "MG", -19.92, -43.94),
    (3509502, "Campinas", "SP", -22.91, -47.06),
    (5208707, "Goiania", "GO", -16.68, -49.25),
    (5300108, "Brasilia", "DF", -15.79, -47.88),
    (5002704, "Campo Grande", "MS", -20.47, -54.62),
    (2927408, "Salvador", "BA", -12.97, -38.51),
    (2304400, "Fortaleza", "CE", -3.73, -38.52),
    (2611606, "Recife", "PE", -8.05, -34.88),
    (1302603, "Manaus", "AM", -3.12, -60.02),
    (4106902, "Curitiba", "PR", -25.43, -49.27),
]


def _carregar_env():
    env = ROOT / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_carregar_env()


def _url(database):
    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        database=database,
    )


DB_NAME = os.getenv("PGDATABASE", "dengue_clima")


def get_engine():
    """Engine do banco do projeto; cria o banco se nao existir."""
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        existe = c.execute(text("select 1 from pg_database where datname=:n"), {"n": DB_NAME}).scalar()
        if not existe:
            c.execute(text(f'create database "{DB_NAME}"'))
    admin.dispose()
    return create_engine(_url(DB_NAME))


