"""Etapa 4 - Modelagem e avaliacao (classificacao de surto daqui a HORIZONTE semanas).

Split temporal: treino = anos < ANO_TESTE, teste = ANO_TESTE.
Selecao do modelo por F1 em validacao cruzada temporal (TimeSeriesSplit) apenas no treino.
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import ANO_TESTE, HORIZONTE, LIMIAR_SURTO, MODELS, PROCESSED, REPORTS
from features import ALVO, FEATURES

SEED = 42


def modelos():
    return {
        "Regressao Logistica": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000)),
        "Random Forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced",
                                                random_state=SEED, n_jobs=-1),
        "Gradient Boosting": HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200,
                                                            class_weight="balanced", random_state=SEED),
    }


def metricas(y, pred, proba=None):
    m = dict(accuracy=accuracy_score(y, pred), precision=precision_score(y, pred, zero_division=0),
             recall=recall_score(y, pred, zero_division=0), f1=f1_score(y, pred, zero_division=0))
    if proba is not None:
        m["roc_auc"] = roc_auc_score(y, proba)
    return {k: round(float(v), 4) for k, v in m.items()}


def main():
    REPORTS.mkdir(exist_ok=True)
    MODELS.mkdir(exist_ok=True)
    df = pd.read_csv(PROCESSED / "features.csv", parse_dates=["data_ini"]).sort_values(["se", "geocode"])
    treino, teste = df[df["ano"] < ANO_TESTE], df[df["ano"] == ANO_TESTE]
    Xtr, ytr, Xte, yte = treino[FEATURES], treino[ALVO], teste[FEATURES], teste[ALVO]
    print(f"treino={len(treino)} (surto {ytr.mean():.1%}) | teste={len(teste)} (surto {yte.mean():.1%})")

    linhas, ajustados = [], {}
    # baseline ingenuo: "a situacao daqui a H semanas sera a de hoje" (persistencia)
    base_pred = (teste["inc_t"] >= LIMIAR_SURTO).astype(int)
    linhas.append({"modelo": "Baseline (persistencia)", "cv_f1_treino": None, **metricas(yte, base_pred)})
    dummy = DummyClassifier(strategy="most_frequent").fit(Xtr, ytr)
    linhas.append({"modelo": "Baseline (classe majoritaria)", "cv_f1_treino": None, **metricas(yte, dummy.predict(Xte))})

    tscv = TimeSeriesSplit(n_splits=3)
    for nome, mdl in modelos().items():
        # TimeSeriesSplit exige ordem temporal: treino ja esta ordenado por semana
        cv = cross_val_score(mdl, Xtr, ytr, cv=tscv, scoring="f1").mean()
        mdl.fit(Xtr, ytr)
        ajustados[nome] = mdl
        linhas.append({"modelo": nome, "cv_f1_treino": round(float(cv), 4),
                       **metricas(yte, mdl.predict(Xte), mdl.predict_proba(Xte)[:, 1])})

    ranking = pd.DataFrame(linhas)
    ranking.to_csv(REPORTS / "ranking_modelos.csv", index=False)
    print(ranking.to_string(index=False))

    melhor_nome = ranking[ranking["modelo"].isin(ajustados)].sort_values("cv_f1_treino", ascending=False).iloc[0]["modelo"]
    melhor = ajustados[melhor_nome]
    pred = melhor.predict(Xte)
    joblib.dump({"modelo": melhor, "features": FEATURES, "limiar_surto": LIMIAR_SURTO, "horizonte": HORIZONTE}, MODELS / "modelo_surto_dengue.pkl")

    # Graficos
    fig, ax = plt.subplots(figsize=(7, 4))
    ranking.set_index("modelo")[["accuracy", "f1", "recall", "precision"]].plot.barh(ax=ax)
    ax.set_title("Comparacao de modelos (teste = 2024)")
    plt.tight_layout(); plt.savefig(REPORTS / "comparacao_modelos.png", dpi=120); plt.close()

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay(confusion_matrix(yte, pred), display_labels=["Sem surto", "Surto"]).plot(ax=ax, colorbar=False)
    ax.set_title(f"Matriz de confusao - {melhor_nome}")
    plt.tight_layout(); plt.savefig(REPORTS / "matriz_confusao.png", dpi=120); plt.close()

    imp = permutation_importance(melhor, Xte, yte, scoring="f1", n_repeats=10, random_state=SEED)
    imp = pd.Series(imp.importances_mean, index=FEATURES).sort_values()
    imp.tail(12).plot.barh(figsize=(7, 5), title=f"Importancia por permutacao (F1) - {melhor_nome}")
    plt.tight_layout(); plt.savefig(REPORTS / "importancia_features.png", dpi=120); plt.close()

    resumo = {"melhor_modelo": melhor_nome, "metricas_teste": metricas(yte, pred, melhor.predict_proba(Xte)[:, 1]),
              "limiar_surto_inc100k": LIMIAR_SURTO, "horizonte_semanas": HORIZONTE, "ano_teste": ANO_TESTE,
              "n_treino": len(treino), "n_teste": len(teste),
              "prevalencia_treino": round(float(ytr.mean()), 4), "prevalencia_teste": round(float(yte.mean()), 4),
              "top_features": imp.tail(5).round(4).to_dict()}
    (REPORTS / "metricas.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMelhor (CV F1): {melhor_nome}\n{json.dumps(resumo['metricas_teste'])}")


if __name__ == "__main__":
    main()

