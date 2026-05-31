"""Generate per-flavor SVG can artwork for the Sama catalog.

Writes one SVG per flavor into samafood/static/products/. Runs at build time
(or whenever the palette/lineup changes). Keeps real branding consistent:
red+blue Sama splash on the label, flavor-specific can body colour.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "products"
OUT.mkdir(parents=True, exist_ok=True)

# (slug, label_en, body_dark, body_light, accent, label_bg)
FLAVORS = [
    # Carbonated soft drinks
    ("cola",           "COLA",          "#0b1d5c", "#2451b8", "#ffffff", "#0b1d5c"),
    ("cola-zero",      "COLA ZERO",     "#1a1a1a", "#3a3a3a", "#e8232a", "#1a1a1a"),
    ("orange-soda",    "ORANGE",        "#b3490b", "#f47d2a", "#ffffff", "#b3490b"),
    ("lemon-soda",     "LEMON",         "#8a9100", "#d9e34a", "#1f3a14", "#fffceb"),
    ("lemon-zero",     "LEMON ZERO",    "#9aa0a6", "#dadce0", "#1f7a3f", "#ffffff"),
    ("fruit-soda",     "FRUIT MIX",     "#7a0e3a", "#d6336c", "#ffffff", "#7a0e3a"),
    # Fruit drinks
    ("mango",          "MANGO",         "#b35a00", "#ffb648", "#ffffff", "#b35a00"),
    ("apple",          "APPLE",         "#1f6f1f", "#5fbf3a", "#ffffff", "#1f6f1f"),
    ("pineapple",      "PINEAPPLE",     "#a07300", "#ffd84d", "#1f3a14", "#fffceb"),
    ("guava",          "GUAVA",         "#a3185f", "#ef7ab2", "#ffffff", "#a3185f"),
    ("mixfruit",       "MIX FRUIT",     "#9b1c1c", "#ef4444", "#ffffff", "#9b1c1c"),
    ("orange-juice",   "ORANGE",        "#a64500", "#ff9a3c", "#ffffff", "#a64500"),
    ("lemon-mint",     "LEMON & MINT",  "#0d6b4a", "#43c79a", "#ffffff", "#0d6b4a"),
    ("apricot",        "APRICOT",       "#a55a14", "#f0a76b", "#ffffff", "#a55a14"),
    ("berry",          "BERRIES",       "#3a0a4a", "#8a2bb8", "#ffffff", "#3a0a4a"),
    # Soft drinks (specialty flavors)
    ("grape",          "GRAPE",         "#3a0a5a", "#7c3aed", "#ffffff", "#3a0a5a"),
    ("ginger",         "GINGER",        "#8a5a00", "#e0b04a", "#1f1f1f", "#fffceb"),
    ("cream-soda",     "CREAM SODA",    "#a07a3a", "#f0d99a", "#3a2a14", "#fff5e0"),
    ("coffee",         "COFFEE",        "#3a1f0a", "#8a5a3a", "#ffffff", "#3a1f0a"),
    ("pina-colada",    "PINA COLADA",   "#a0823a", "#f0d49a", "#3a2a14", "#fff5e0"),
    ("pomegranate",    "POMEGRANATE",   "#8a0a1f", "#d62828", "#ffffff", "#8a0a1f"),
    ("lychee",         "LYCHEE",        "#a3508a", "#f0b8d2", "#3a0a2a", "#ffffff"),
    ("pomelo",         "POMELO",        "#7a7a00", "#d9e34a", "#1f3a14", "#fffceb"),
    ("salty-lime",     "SALTY LIME",    "#1f5a3a", "#5fbf8a", "#ffffff", "#1f5a3a"),
    # Energy
    ("raz",            "RAZ ENERGY",    "#000000", "#1f1f1f", "#e8232a", "#000000"),
    # Water
    ("water",          "WATER",         "#0a4a8a", "#5fb0e8", "#ffffff", "#0a4a8a"),
    ("water-gallon",   "WATER 5L",      "#0a4a8a", "#5fb0e8", "#ffffff", "#0a4a8a"),
]


CAN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 240" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="body" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{dark}"/>
      <stop offset="0.5" stop-color="{light}"/>
      <stop offset="1" stop-color="{dark}"/>
    </linearGradient>
    <linearGradient id="top" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#e0e0e0"/>
      <stop offset="1" stop-color="#9a9a9a"/>
    </linearGradient>
  </defs>
  <!-- can shadow -->
  <ellipse cx="60" cy="230" rx="38" ry="4" fill="#000" opacity="0.18"/>
  <!-- top lid -->
  <ellipse cx="60" cy="14" rx="36" ry="7" fill="url(#top)"/>
  <rect x="24" y="14" width="72" height="6" fill="#bdbdbd"/>
  <!-- body -->
  <rect x="24" y="20" width="72" height="200" rx="3" fill="url(#body)"/>
  <!-- label band -->
  <rect x="22" y="100" width="76" height="70" fill="{label_bg}" opacity="0.97"/>
  <!-- top highlight -->
  <rect x="26" y="22" width="6" height="196" fill="#ffffff" opacity="0.18"/>
  <rect x="88" y="22" width="6" height="196" fill="#000000" opacity="0.18"/>
  <!-- sama splash mark on label -->
  <g transform="translate(60,118)">
    <path transform="rotate(-30) scale(0.42)" d="M0,4 C-13,-22 -9,-40 0,-50 C9,-40 13,-22 0,4 Z" fill="#13388c"/>
    <path transform="rotate(2) scale(0.42)" d="M0,4 C-12,-26 -8,-46 0,-58 C9,-46 13,-26 0,4 Z" fill="#e8232a"/>
    <path transform="rotate(40) scale(0.42)" d="M0,4 C-14,-24 -10,-42 0,-54 C11,-42 16,-22 0,4 Z" fill="#13388c"/>
  </g>
  <!-- brand wordmark on label -->
  <text x="60" y="148" text-anchor="middle" font-family="Verdana, Tahoma, sans-serif" font-size="16" font-weight="800" fill="{accent}" letter-spacing="-1">{brand}</text>
  <!-- flavor name on label -->
  <text x="60" y="162" text-anchor="middle" font-family="Arial, sans-serif" font-size="8" font-weight="700" fill="{accent}" letter-spacing="0.5">{label}</text>
  <!-- bottom rim -->
  <ellipse cx="60" cy="220" rx="36" ry="5" fill="#9a9a9a"/>
</svg>
"""

GALLON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 220" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1"><stop offset="0" stop-color="{dark}"/><stop offset="1" stop-color="{light}"/></linearGradient>
  </defs>
  <ellipse cx="80" cy="212" rx="60" ry="6" fill="#000" opacity="0.18"/>
  <rect x="60" y="14" width="40" height="20" rx="4" fill="#bdbdbd"/>
  <path d="M30 40 Q30 30 50 30 L110 30 Q130 30 130 40 L130 200 Q130 210 110 210 L50 210 Q30 210 30 200 Z" fill="url(#bg)"/>
  <rect x="40" y="80" width="80" height="80" fill="#ffffff"/>
  <g transform="translate(80,108)">
    <path transform="rotate(-30) scale(0.55)" d="M0,4 C-13,-22 -9,-40 0,-50 C9,-40 13,-22 0,4 Z" fill="#13388c"/>
    <path transform="rotate(2) scale(0.55)" d="M0,4 C-12,-26 -8,-46 0,-58 C9,-46 13,-26 0,4 Z" fill="#e8232a"/>
    <path transform="rotate(40) scale(0.55)" d="M0,4 C-14,-24 -10,-42 0,-54 C11,-42 16,-22 0,4 Z" fill="#13388c"/>
  </g>
  <text x="80" y="140" text-anchor="middle" font-family="Verdana" font-size="22" font-weight="800" fill="#13388c">sama</text>
  <text x="80" y="156" text-anchor="middle" font-family="Arial" font-size="10" font-weight="700" fill="#13388c">{label}</text>
</svg>
"""


def make_all():
    for slug, label, dark, light, accent, label_bg in FLAVORS:
        brand = "RAZ" if slug == "raz" else "sama"
        template = GALLON_SVG if slug == "water-gallon" else CAN_SVG
        svg = template.format(
            label=label, dark=dark, light=light, accent=accent, label_bg=label_bg, brand=brand
        )
        (OUT / f"{slug}.svg").write_text(svg, encoding="utf-8")
    # remove the old generic placeholders (juice/soda/gallon) — replaced by flavor-specific
    for legacy in ("juice.svg", "soda.svg", "gallon.svg", "energy.svg", "water.svg"):
        old = OUT / legacy
        if old.exists() and legacy not in {f"{s[0]}.svg" for s in FLAVORS}:
            old.unlink()
    manifest = {slug: f"/static/products/{slug}.svg" for slug, *_ in FLAVORS}
    (OUT / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(FLAVORS)} product SVGs into {OUT}")


if __name__ == "__main__":
    make_all()
