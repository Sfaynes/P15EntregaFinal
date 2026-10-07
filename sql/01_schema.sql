-- Modelo dimensional: 2 fatos (dengue semanal, clima diario) e 2 dimensoes.
DROP VIEW IF EXISTS vw_base_modelo;
DROP VIEW IF EXISTS vw_clima_semana;
DROP TABLE IF EXISTS fato_dengue_semana;
DROP TABLE IF EXISTS fato_clima_dia;
DROP TABLE IF EXISTS dim_semana;
DROP TABLE IF EXISTS dim_municipio;

CREATE TABLE dim_municipio (
    geocode    INTEGER PRIMARY KEY,           -- codigo IBGE
    nome       VARCHAR(60) NOT NULL,
    uf         CHAR(2)     NOT NULL,
    latitude   NUMERIC(8,4) NOT NULL,
    longitude  NUMERIC(8,4) NOT NULL
);

CREATE TABLE dim_semana (
    se         INTEGER PRIMARY KEY,           -- semana epidemiologica AAAASS
    data_ini   DATE    NOT NULL UNIQUE,       -- domingo de inicio
    ano        SMALLINT NOT NULL,
    semana     SMALLINT NOT NULL CHECK (semana BETWEEN 1 AND 53)
);

CREATE TABLE fato_dengue_semana (
    geocode     INTEGER NOT NULL REFERENCES dim_municipio(geocode),
    se          INTEGER NOT NULL REFERENCES dim_semana(se),
    casos       INTEGER NOT NULL CHECK (casos >= 0),
    casos_est   NUMERIC(12,2) NOT NULL CHECK (casos_est >= 0),
    populacao   INTEGER NOT NULL CHECK (populacao > 0),
    inc100k     NUMERIC(12,4) NOT NULL CHECK (inc100k >= 0),
    nivel_alerta SMALLINT,
    rt          NUMERIC(10,4),
    PRIMARY KEY (geocode, se)
);

CREATE TABLE fato_clima_dia (
    geocode     INTEGER NOT NULL REFERENCES dim_municipio(geocode),
    data        DATE    NOT NULL,
    temp_media  NUMERIC(5,2),
    temp_max    NUMERIC(5,2),
    temp_min    NUMERIC(5,2),
    precip_mm   NUMERIC(7,2) CHECK (precip_mm >= 0),
    umid_media  NUMERIC(5,2),
    PRIMARY KEY (geocode, data)
);
CREATE INDEX ix_clima_data ON fato_clima_dia (data);

-- Clima agregado por semana epidemiologica (domingo a sabado)
CREATE VIEW vw_clima_semana AS
SELECT s.se, c.geocode,
       AVG(c.temp_media)  AS temp_media,
       MAX(c.temp_max)    AS temp_max,
       MIN(c.temp_min)    AS temp_min,
       SUM(c.precip_mm)   AS precip_mm,
       AVG(c.umid_media)  AS umid_media,
       COUNT(*)           AS dias
FROM dim_semana s
JOIN fato_clima_dia c ON c.data BETWEEN s.data_ini AND s.data_ini + 6
GROUP BY s.se, c.geocode;

-- Base analitica: dengue + clima por municipio e semana
CREATE VIEW vw_base_modelo AS
SELECT d.geocode, m.nome AS municipio, m.uf, d.se, s.data_ini, s.ano, s.semana,
       d.casos, d.casos_est, d.populacao, d.inc100k, d.nivel_alerta, d.rt,
       w.temp_media, w.temp_max, w.temp_min, w.precip_mm, w.umid_media
FROM fato_dengue_semana d
JOIN dim_municipio m ON m.geocode = d.geocode
JOIN dim_semana s    ON s.se = d.se
JOIN vw_clima_semana w ON w.se = d.se AND w.geocode = d.geocode AND w.dias = 7;
