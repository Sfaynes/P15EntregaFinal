"""Executa o pipeline completo: [coleta] -> ETL/PostgreSQL -> features -> modelo.

Uso:  python src/run_pipeline.py            (usa os CSVs ja versionados em data/raw)
      python src/run_pipeline.py --coleta   (baixa novamente das APIs)
"""
import sys

import coleta
import etl
import features
import modelo


def main():
    if "--coleta" in sys.argv:
        print("== 1. Coleta ==")
        coleta.main(force=True)
    print("== 2. ETL -> PostgreSQL ==")
    etl.main()
    print("== 3. Features ==")
    features.main()
    print("== 4. Modelo ==")
    modelo.main()


if __name__ == "__main__":
    main()
