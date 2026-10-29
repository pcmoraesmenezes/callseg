import numpy as np

from .text import tag_tokens


def describe(seg, df, n_terms=12, n_examples=2, window=(250, 520)):
    for sector, sub in seg.sub.items():
        g = df[df.sector == sector].reset_index(drop=True)
        X = sub.vec.transform([tag_tokens(t) for t in g.text])
        names = np.array(sub.vec.get_feature_names_out())
        Z = sub._embed(g.text.tolist())
        print(f"\n===== {sector} k={sub.k}")
        for c in range(sub.k):
            idx = np.where(sub.labels_ == c)[0]
            top = names[np.asarray(X[idx].mean(0)).ravel().argsort()[::-1][:n_terms]]
            near = idx[np.argsort(-(Z[idx] @ sub.centroids[c]))[:n_examples]]
            print(f"\n[{c}] n={len(idx)} ({len(idx) / len(g):.0%}) | {', '.join(top)}")
            for i in near:
                print("   >", g.text[i][window[0] : window[1]].replace("\n", " "))
