"""star_catalogue.csv: the real stars the night sky is drawn from.

The rows are the Yale Bright Star Catalogue, 5th edition (Hoffleit & Warren
1991; CDS catalogue V/50, free to use): every star a dark sky shows the naked
eye, about nine thousand, each with its J2000 position, its visual magnitude
and its B-V colour index. The CSV is committed, so a build needs no network;
fetch() (Scripts/fetch_star_catalogue.py) rewrites it from the CDS's copy,
cached in assets/cache/stars.

No `unreal` here: the fetcher runs under plain python3.
"""

import csv
import gzip
import os
import urllib.request
from collections import namedtuple

BSC_URL = "https://cdsarc.cds.unistra.fr/ftp/cats/V/50/catalog.gz"
_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "star_catalogue.csv")
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                          "assets", "cache", "stars", "bsc5.dat.gz")
FIELDS = ("ra_deg", "dec_deg", "vmag", "bv", "name")

# name is the catalogue's Bayer one: "Alp CMa" is Sirius, "Alp UMi" Polaris.
Star = namedtuple("Star", FIELDS)


def parse_bsc(text):
    """The catalogue's fixed-width lines as Stars. Its 14 entries without a
    position (novae and clusters once listed as stars) are dropped."""
    stars = []
    for line in text.splitlines():
        if not line[75:83].strip() or not line[102:107].strip():
            continue
        ra = (int(line[75:77]) + int(line[77:79]) / 60.0 + float(line[79:83]) / 3600.0) * 15.0
        dec = int(line[84:86]) + int(line[86:88]) / 60.0 + int(line[88:90]) / 3600.0
        if line[83] == "-":
            dec = -dec
        bv = line[109:114].strip()
        stars.append(Star(round(ra, 4), round(dec, 4), float(line[102:107]),
                          float(bv) if bv else 0.6, " ".join(line[7:14].split())))
    return stars


def fetch():
    """Download the catalogue (once: the copy is kept) and rewrite the CSV."""
    if not os.path.exists(CACHE_PATH):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        urllib.request.urlretrieve(BSC_URL, CACHE_PATH)
    with gzip.open(CACHE_PATH, "rt", encoding="latin-1") as f:
        stars = sorted(parse_bsc(f.read()), key=lambda s: s.vmag)
    with open(CSV_PATH, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(FIELDS)
        out.writerows(stars)
    return stars


def load_stars():
    """Every star of the CSV, brightest first."""
    with open(CSV_PATH, newline="") as f:
        return [Star(float(r["ra_deg"]), float(r["dec_deg"]), float(r["vmag"]),
                     float(r["bv"]), r["name"]) for r in csv.DictReader(f)]
