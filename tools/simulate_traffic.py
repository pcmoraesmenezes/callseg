import argparse
import glob
import json
import random
import time
import urllib.request

SECTORS = ["automotive", "home_service", "medicare"]


def post(url, text):
    req = urllib.request.Request(
        f"{url}/segment", json.dumps({"text": text}).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser(description="Envia chamadas reais do dataset para a API.")
    ap.add_argument("data_dir")
    ap.add_argument("--url", default="http://127.0.0.1:8010")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--rate", type=float, default=10, help="chamadas por segundo")
    ap.add_argument("--mode", choices=["normal", "truncated", "one_sector"], default="normal")
    ap.add_argument("--words", type=int, default=40, help="palavras mantidas no modo truncated")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    sectors = ["automotive"] if args.mode == "one_sector" else SECTORS
    files = [f for s in sectors for f in glob.glob(f"{args.data_dir}/{s}/*_transcript.json")]
    rng.shuffle(files)
    ambiguous = 0
    for path in files[: args.n]:
        text = json.load(open(path))["text"]
        if args.mode == "truncated":
            text = " ".join(text.split()[: args.words])
        ambiguous += post(args.url, text)["subgroup"]["ambiguous"]
        time.sleep(1 / args.rate)
    print(f"{min(args.n, len(files))} chamadas, {ambiguous} ambíguas ({args.mode})")


if __name__ == "__main__":
    main()
