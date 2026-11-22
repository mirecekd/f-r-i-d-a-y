# backend/app/assets/synonyms.py
"""Czech word stems (diacritics removed) -> English index words, so a Czech query finds the English-named models."""

import unicodedata

CZ_STEMS: dict[str, tuple[str, ...]] = {
    "zidl": ("chair",), "stul": ("table",), "stol": ("table",), "auto": ("car", "vehicle", "truck"),
    "vuz": ("vehicle", "cart"), "kamion": ("truck",), "motork": ("motorcycle",), "motocykl": ("motorcycle",),
    "lod": ("boat", "ship"), "clun": ("boat",), "strom": ("tree",), "kvet": ("flower", "flowers"),
    "ker": ("bush",), "tráv": ("grass",), "trav": ("grass",), "kamen": ("rock",), "skal": ("rock",),
    "dum": ("house", "building"), "dom": ("house", "building"), "budov": ("building",), "chat": ("house",),
    "postel": ("bed",), "gauc": ("couch",), "pohov": ("couch",), "sedack": ("couch",), "skrin": ("drawer", "shelf"),
    "polic": ("shelf", "bookshelf"), "knihov": ("bookshelf",), "lamp": ("light", "lamp"), "svetl": ("light",),
    "svitidl": ("light",), "dvere": ("door",), "okno": ("window",), "okn": ("window",), "koberec": ("carpet",),
    "zaves": ("curtains",), "zavesy": ("curtains",), "ledni": ("fridge",), "lednic": ("fridge",), "sporak": ("oven",),
    "trouba": ("oven",), "dres": ("sink",), "umyvadl": ("sink",), "zachod": ("toilet",), "vana": ("bathtub",),
    "sprch": ("shower",), "zrcadl": ("mirror",), "talir": ("plate",), "vidlic": ("fork",), "luzic": ("spoon",),
    "nuz": ("knife",), "kuch": ("kitchen",), "koupeln": ("bathroom",), "rostlin": ("plant", "houseplant"),
    "kytk": ("flower", "plant"), "zvire": ("animal",), "kun": ("horse",), "krav": ("cow",), "pes": ("husky", "dog"),
    "vlk": ("wolf",), "liska": ("fox",), "jelen": ("deer", "stag"), "clovek": ("person", "character"),
    "muz": ("man", "person"), "zen": ("woman", "person"), "postav": ("character",), "voj": ("soldier", "character"),
    "kral": ("king",), "mec": ("sword",), "zbran": ("weapon",), "pistol": ("pistol",), "stan": ("tent",),
    "ohen": ("bonfire",), "ohnist": ("bonfire",), "kos": ("trashcan",), "baterk": ("torch",), "ulic": ("street",),
    "silnic": ("road", "street"), "cest": ("road",), "znack": ("sign",), "semafor": ("trafficlight", "traffic"),
    "most": ("bridge",), "mesto": ("city",), "vesnic": ("village",), "stredov": ("medieval",), "kostel": ("bell", "tower"),
    "mlyn": ("mill",), "studn": ("well",), "sud": ("barrel",), "bedn": ("crate",), "plot": ("fence",),
    "lavic": ("bench",), "stolek": ("table",), "taburet": ("stool",), "kreslo": ("chair", "couch"),
    "pytl": ("bag",), "batoh": ("backpack",), "mapa": ("compass",), "pohar": ("cup",),
}
EN_PLURALS = ("ies", "es", "s")


def fold(text: str) -> str:
    """Lower case without diacritics."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def expand(token: str) -> set[str]:
    """The token itself, its singular form and the English words behind a Czech stem (longest matching stem wins)."""
    folded = fold(token)
    out = {folded}
    for suffix in EN_PLURALS:
        if len(folded) > len(suffix) + 2 and folded.endswith(suffix):
            out.add(folded[: -len(suffix)])
    stems = sorted((s for s in CZ_STEMS if folded.startswith(fold(s)) and len(folded) <= len(s) + 5), key=len, reverse=True)
    if stems:
        out.update(CZ_STEMS[stems[0]])
    return out
