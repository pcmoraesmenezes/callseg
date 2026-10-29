"""Gera docs/reports/MODEL_CARD.md a partir dos modelos *.template.md e de reports/metrics.json.

Nenhum número é digitado nos modelos: cada `{{tipo:caminho}}` é lido do JSON.
Tipos: `pct` (porcentagem, 1 casa), `pct2` (2 casas), `int` (milhar com ponto), `f3` (3 casas), sem tipo (texto).
O caminho separa os níveis por ponto; níveis de lista são índices (`ic95_f1_macro.0`).
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "reports"
PLACEHOLDER = re.compile(r"\{\{(pct2:|pct:|int:|f3:)?([^{}]+)\}\}")


def lookup(metrics, path: str):
    value = metrics
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def render(template: str, metrics: dict) -> str:
    def substitute(match):
        kind, path = match.group(1), match.group(2).strip()
        value = lookup(metrics, path)
        if kind == "pct2:":
            return f"{value * 100:.2f}".replace(".", ",") + "%"
        if kind == "pct:":
            return f"{value * 100:.1f}".replace(".", ",") + "%"
        if kind == "int:":
            return f"{int(value):,}".replace(",", ".")
        if kind == "f3:":
            return f"{value:.3f}".replace(".", ",")
        return str(value).replace(".", ",") if isinstance(value, float) else str(value)

    return PLACEHOLDER.sub(substitute, template)


def main():
    metrics = json.loads((ROOT / "reports" / "metrics.json").read_text())
    for template_path in sorted(REPORTS.glob("*.template.md")):
        output = template_path.with_name(template_path.name.replace(".template", ""))
        output.write_text(render(template_path.read_text(), metrics))
        print("gerado", output.relative_to(ROOT))


if __name__ == "__main__":
    main()
