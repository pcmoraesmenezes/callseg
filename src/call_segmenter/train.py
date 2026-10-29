import argparse
import json
from importlib import resources

from .data import build_table, dedup
from .model import CallSegmenter

KS = {"automotive": 6, "home_service": 8, "medicare": 7}
SECTOR_KIND, SECTOR_C, MIN_PROB = "svm_calibrated", 5.0, 0.9


def main():
    ap = argparse.ArgumentParser(description="Treina o segmentador e grava o modelo.")
    ap.add_argument("data_dir")
    ap.add_argument("out")
    ap.add_argument("--sector-kind", default=SECTOR_KIND, choices=["logreg", "svm_calibrated"])
    ap.add_argument("--sector-C", type=float, default=SECTOR_C)
    ap.add_argument("--min-prob", type=float, default=MIN_PROB)
    args = ap.parse_args()
    names = json.loads(resources.files("call_segmenter").joinpath("names.json").read_text())
    df = dedup(build_table(args.data_dir))
    seg = CallSegmenter(KS, names, sector_kind=args.sector_kind, sector_C=args.sector_C, min_prob=args.min_prob).fit(df)
    seg.save(args.out)
    print(f"{len(df)} chamadas, versão {seg.model_version}, modelo em {args.out}")


if __name__ == "__main__":
    main()
