"""Classificador de setor: TF-IDF seguido de um estimador linear."""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.svm import LinearSVC

TFIDF_SETTINGS = {"min_df": 3, "max_df": 0.9, "sublinear_tf": True, "ngram_range": (1, 2), "max_features": 200_000}
ESTIMATORS = ("logreg", "svm_calibrated", "sgd_calibrated", "ridge_calibrated", "cnb")
CALIBRATION_FOLDS = 3


def build_estimator(estimator: str, regularization: float, **params):
    """Cria o estimador final, calibrado quando ele não devolve probabilidade por conta própria.

    Args:
        estimator: um de `ESTIMATORS`.
        regularization: `C` (SVM e regressão logística). Os demais usam `alpha` em `params`.
        **params: `alpha` e, para o SGD, `loss`.

    Returns:
        Estimador com `predict_proba`.
    """
    if estimator == "logreg":
        return LogisticRegression(max_iter=3000, C=regularization)
    if estimator == "svm_calibrated":
        return CalibratedClassifierCV(LinearSVC(C=regularization), cv=CALIBRATION_FOLDS, method="sigmoid")
    if estimator == "sgd_calibrated":
        sgd = SGDClassifier(alpha=params["alpha"], loss=params.get("loss", "hinge"), max_iter=2000, random_state=0)
        return CalibratedClassifierCV(sgd, cv=CALIBRATION_FOLDS, method="sigmoid")
    if estimator == "ridge_calibrated":
        return CalibratedClassifierCV(RidgeClassifier(alpha=params["alpha"]), cv=CALIBRATION_FOLDS, method="sigmoid")
    if estimator == "cnb":
        return ComplementNB(alpha=params["alpha"])
    raise ValueError(f"estimador desconhecido: {estimator}")


def build_sector_pipeline(
    estimator: str = "svm_calibrated", regularization: float = 5.0, tfidf_overrides: dict | None = None, **params
) -> Pipeline:
    """Monta o pipeline texto -> probabilidade de cada setor.

    Returns:
        `Pipeline([tfidf, classificador])`, ainda não ajustado.
    """
    vectorizer = TfidfVectorizer(**{**TFIDF_SETTINGS, **(tfidf_overrides or {})})
    return make_pipeline(vectorizer, build_estimator(estimator, regularization, **params))


def linear_weights(pipeline: Pipeline) -> np.ndarray:
    """Pesos de cada termo por setor, lidos do estimador linear do pipeline.

    Quando o estimador é calibrado, devolve a média dos pesos dos modelos ajustados em cada dobra.

    Returns:
        Matriz (setores, termos).
    """
    final_step = pipeline[-1]
    calibrated = getattr(final_step, "calibrated_classifiers_", None)
    if not calibrated:
        return final_step.coef_
    fitted_models = [fitted.estimator for fitted in calibrated]
    return np.mean([model.coef_ for model in fitted_models], axis=0)


def terms_that_pushed_toward(pipeline: Pipeline, text: str, sector: str, top: int = 5) -> list[str]:
    """Termos do texto que mais empurraram a decisão para `sector`, pelo peso do modelo linear."""
    vectorizer = pipeline[0]
    terms = vectorizer.get_feature_names_out()
    sector_row = list(pipeline.classes_).index(sector)
    contribution = vectorizer.transform([text]).multiply(linear_weights(pipeline)[sector_row]).tocoo()
    ranked = sorted(zip(contribution.col, contribution.data, strict=True), key=lambda pair: -pair[1])[:top]
    return [terms[column] for column, weight in ranked if weight > 0]
