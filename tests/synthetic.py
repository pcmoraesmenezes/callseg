import random

import pandas as pd

TOPICS = {
    "automotive": {
        "vendas": "car price credit trade lease payment dealership deal financing monthly",
        "servico": "oil appointment service tire brake schedule maintenance inspection wheel alignment",
        "ura": "press extension dial party hold menu operator directory department transfer",
    },
    "home_service": {
        "vidro": "window glass door shower pane replace frame mirror estimate fix",
        "fauna": "wildlife animal raccoon squirrel trap nuisance attic critter removal rescue",
        "pesquisa": "survey feedback satisfied scale rate experience recommend unsatisfied completely score",
    },
    "medicare": {
        "pet": "dog pet boarding grooming daycare vaccine puppy suite reservation leash",
        "odonto": "dental teeth cleaning insurance patient crown cavity hygienist exam orthodontist",
        "clinica": "clinics hold options mobile vaccination records locations hours message callback office",
    },
}
FILLER = "yes okay thank you please hello right sure now well know just can will got want need".split()


def make_text(rng, words, n=90):
    vocab = words.split()
    return " ".join(rng.choice(vocab) if rng.random() < 0.7 else rng.choice(FILLER) for _ in range(n))


def make_corpus(per_topic=70, seed=0):
    rng = random.Random(seed)
    rows = []
    for sector, topics in TOPICS.items():
        for topic, words in topics.items():
            for i in range(per_topic):
                rows.append(dict(sector=sector, call_id=f"{sector}-{topic}-{i}", transcript=make_text(rng, words)))
    return pd.DataFrame(rows)
