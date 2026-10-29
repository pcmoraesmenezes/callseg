import os
import textwrap

import matplotlib.pyplot as plt
import numpy as np

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs")
COLORS = {"automotive": "#2a6f97", "home_service": "#e07a1f", "medicare": "#5a9e6f"}
LABEL = {"automotive": "automotivo", "home_service": "home service", "medicare": "medicare"}
INK, MUTED, WARN = "#1f2933", "#6b7280", "#e07a1f"


def setup():
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 170,
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "figure.constrained_layout.use": True,
        }
    )


def wrap(text, width=34):
    return "\n".join(textwrap.wrap(text, width))


def save(fig, name):
    fig.savefig(os.path.join(DOCS, name), bbox_inches="tight", facecolor="white")


def confusion(ax, cm, labels):
    share = cm / cm.sum(1, keepdims=True)
    ax.imshow(share, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(
                j,
                i,
                f"{cm[i, j]:,}".replace(",", "."),
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold" if i == j else "normal",
                color="white" if share[i, j] > 0.5 else INK,
            )
    names = [LABEL[x].replace(" ", "\n") for x in labels]
    ax.set_xticks(range(len(labels)), names)
    ax.set_yticks(range(len(labels)), names)
    ax.set_xlabel("previsto")
    ax.set_ylabel("real")
    ax.spines[:].set_visible(False)


def heatmap(ax, table, row_labels, col_labels, title, vmax=100):
    ax.imshow(table, cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(col_labels)), col_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(row_labels)), [wrap(r, 40) for r in row_labels], fontsize=8.5)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            ax.text(
                j,
                i,
                f"{table[i, j]:.0f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if table[i, j] > vmax * 0.55 else INK,
            )
    ax.set_title(title)
    ax.spines[:].set_visible(False)


def reliability(ax, y_true_onehot, proba, label, color, bins=10):
    conf = proba.max(1)
    hit = (proba.argmax(1) == y_true_onehot.argmax(1)).astype(float)
    edges = np.linspace(0.3, 1.0, bins + 1)
    idx = np.clip(np.digitize(conf, edges) - 1, 0, bins - 1)
    xs, ys = [], []
    for b in range(bins):
        m = idx == b
        if m.sum() >= 20:
            xs.append(conf[m].mean())
            ys.append(hit[m].mean())
    ax.plot(xs, ys, "-o", color=color, label=label)
    ax.plot([0.3, 1], [0.3, 1], "--", color=MUTED, lw=1)
