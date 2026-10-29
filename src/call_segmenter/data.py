import glob
import json
import os
import re

import pandas as pd

SECTORS = ["automotive", "home_service", "medicare"]
_NAME = re.compile(r"([0-9a-f]+)(.*)\.json$")


def build_table(data_dir):
    rows = []
    for sector in SECTORS:
        for path in sorted(glob.glob(f"{data_dir}/{sector}/*.json")):
            name = os.path.basename(path)
            raw = open(path, "rb").read()
            if not raw.strip():
                continue
            d = json.loads(raw)
            call_id = _NAME.match(name).group(1)
            rows.append(
                dict(
                    sector=sector,
                    file=name,
                    call_id=call_id,
                    is_copy=name != f"{call_id}_transcript.json",
                    text=d.get("text") or "",
                    conf=d.get("confidence"),
                    dur=d.get("audio_duration"),
                    n_words=len(d.get("words", [])),
                )
            )
    return pd.DataFrame(rows)


def dedup(df):
    df = df[df.text.str.strip() != ""].sort_values(["call_id", "is_copy"])
    return df.drop_duplicates("call_id").reset_index(drop=True)
