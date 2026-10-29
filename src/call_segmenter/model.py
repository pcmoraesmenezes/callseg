import hashlib

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import normalize
from sklearn.svm import LinearSVC

from .text import tag_tokens

AMBIGUOUS_QUANTILE = 0.10
ANCHOR_TERMS = 30


TFIDF_DEFAULT = {"min_df": 3, "max_df": 0.9, "sublinear_tf": True, "ngram_range": (1, 2), "max_features": 200000}


def sector_pipeline(kind="logreg", C=5.0, tfidf=None, **params):
    vec = TfidfVectorizer(**{**TFIDF_DEFAULT, **(tfidf or {})})
    if kind == "logreg":
        clf = LogisticRegression(max_iter=3000, C=C)
    elif kind == "svm_calibrated":
        clf = CalibratedClassifierCV(LinearSVC(C=C), cv=3, method="sigmoid")
    elif kind == "sgd_calibrated":
        base = SGDClassifier(alpha=params["alpha"], loss=params.get("loss", "hinge"), max_iter=2000, random_state=0)
        clf = CalibratedClassifierCV(base, cv=3, method="sigmoid")
    elif kind == "ridge_calibrated":
        clf = CalibratedClassifierCV(RidgeClassifier(alpha=params["alpha"]), cv=3, method="sigmoid")
    elif kind == "cnb":
        clf = ComplementNB(alpha=params["alpha"])
    else:
        raise ValueError(f"estimador desconhecido: {kind}")
    return make_pipeline(vec, clf)


class SubgroupModel:
    def __init__(self, k, names=None, anchors=None, seed=0, n_components=100):
        self.k, self.seed, self.n_components = k, seed, n_components
        self.names = {int(i): n for i, n in names.items()} if names else {i: f"grupo_{i}" for i in range(k)}
        self.anchors = {int(i): a for i, a in anchors.items()} if anchors else {}

    def _embed(self, texts):
        return normalize(self.svd.transform(self.vec.transform([tag_tokens(t) for t in texts])))

    def fit(self, texts):
        self.vec = TfidfVectorizer(
            min_df=5, max_df=0.4, sublinear_tf=True, ngram_range=(1, 2), stop_words="english", max_features=100000
        )
        X = self.vec.fit_transform([tag_tokens(t) for t in texts])
        self.svd = TruncatedSVD(min(self.n_components, X.shape[1] - 1), random_state=self.seed).fit(X)
        Z = normalize(self.svd.transform(X))
        self.svd.components_ = self.svd.components_.astype(np.float32)
        self.km = KMeans(self.k, n_init=10, random_state=self.seed).fit(Z)
        self.centroids = normalize(self.km.cluster_centers_)
        sims = np.sort(Z @ self.centroids.T, axis=1)
        self.margin_cut = float(np.quantile(sims[:, -1] - sims[:, -2], AMBIGUOUS_QUANTILE))
        self.labels_ = self.km.labels_
        terms = np.array(self.vec.get_feature_names_out())
        self.top_terms = {}
        for c in range(self.k):
            weight = np.asarray(X[self.labels_ == c].mean(0)).ravel()
            self.top_terms[c] = terms[weight.argsort()[::-1][:ANCHOR_TERMS]].tolist()
        self.summary = [
            dict(id=c, name=self.names[c], size=int((self.labels_ == c).sum()), top_terms=self.top_terms[c][:10])
            for c in range(self.k)
        ]
        return self

    def check_anchors(self):
        missing = [(c, a) for c, a in self.anchors.items() if not set(a) & set(self.top_terms[c])]
        if missing:
            raise ValueError(f"grupos cujo nome não bate com o vocabulário: {missing}")

    def evidence_terms(self, text, cluster, top=5):
        """Termos de âncora do subgrupo que aparecem na chamada, na ordem do peso no grupo."""
        tokens = set(self.vec.build_analyzer()(tag_tokens(text)))
        return [t for t in self.top_terms[cluster] if t in tokens][:top]

    def predict(self, texts):
        sims = self._embed(texts) @ self.centroids.T
        order = np.argsort(sims, axis=1)[:, ::-1]
        out = []
        for s, o in zip(sims, order, strict=True):
            margin = float(s[o[0]] - s[o[1]])
            out.append(
                dict(
                    id=int(o[0]),
                    name=self.names[int(o[0])],
                    similarity=round(float(s[o[0]]), 4),
                    margin=round(margin, 4),
                    ambiguous=margin < self.margin_cut,
                    runner_up=self.names[int(o[1])],
                )
            )
        return out


class CallSegmenter:
    def __init__(
        self,
        ks,
        names=None,
        seed=0,
        n_components=100,
        sector_kind="logreg",
        sector_C=5.0,
        min_prob=0.6,
        sector_tfidf=None,
        sector_params=None,
    ):
        self.ks, self.names, self.seed, self.n_components = ks, names or {}, seed, n_components
        self.sector_kind, self.sector_C, self.min_prob = sector_kind, sector_C, min_prob
        self.sector_tfidf, self.sector_params = sector_tfidf, sector_params or {}

    def fit(self, df):
        self.sector_model = sector_pipeline(
            self.sector_kind, self.sector_C, self.sector_tfidf, **self.sector_params
        ).fit(df.text, df.sector)
        self.sub = {}
        for sector, k in self.ks.items():
            meta = self.names.get(sector, {})
            g = df[df.sector == sector]
            sub = SubgroupModel(
                k,
                {i: v["name"] for i, v in meta.items()} or None,
                {i: v["anchors"] for i, v in meta.items()} or None,
                self.seed,
                self.n_components,
            ).fit(g.text.tolist())
            sub.check_anchors()
            self.sub[sector] = sub
        digest = hashlib.sha256("".join(sorted(df.call_id.astype(str))).encode()).hexdigest()[:8]
        ks = ".".join(str(k) for k in self.ks.values())
        self.model_version = f"{digest}-{self.sector_kind}-k{ks}-s{self.seed}"
        self.n_train = len(df)
        return self

    def _sector_coef(self):
        if not hasattr(self, "_coef"):
            clf = self.sector_model[-1]
            fitted = getattr(clf, "calibrated_classifiers_", None)
            if fitted:
                parts = [getattr(f, "estimator", None) or f.base_estimator for f in fitted]
                coef = np.mean([p.coef_ for p in parts], axis=0)
            else:
                coef = clf.coef_
            self._coef = coef
        return self._coef

    def evidence(self, text, sector, top=5):
        """Termos do texto que mais empurraram para o setor e para o subgrupo, lidos dos pesos do modelo."""
        vec = self.sector_model[0]
        row = vec.transform([text])
        terms = vec.get_feature_names_out()
        k = list(self.sector_model.classes_).index(sector)
        contrib = row.multiply(self._sector_coef()[k]).tocoo()
        best = sorted(zip(contrib.col, contrib.data, strict=True), key=lambda x: -x[1])[:top]
        return dict(sector_terms=[terms[i] for i, w in best if w > 0], subgroup_terms=[])

    def predict(self, texts, explain=False):
        probs = self.sector_model.predict_proba(texts)
        classes = self.sector_model.classes_
        out = []
        for text, p in zip(texts, probs, strict=True):
            sector = classes[int(p.argmax())]
            out.append(
                dict(
                    sector=sector,
                    sector_probability=round(float(p.max()), 4),
                    sector_scores={c: round(float(v), 4) for c, v in zip(classes, p, strict=True)},
                    low_confidence=bool(p.max() < self.min_prob),
                    subgroup=self.sub[sector].predict([text])[0],
                )
            )
            if explain:
                out[-1]["evidence"] = self.evidence(text, sector)
                out[-1]["evidence"]["subgroup_terms"] = self.sub[sector].evidence_terms(text, out[-1]["subgroup"]["id"])
        return out

    def save(self, path):
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path):
        return joblib.load(path)
