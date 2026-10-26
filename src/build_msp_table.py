"""Transcribe the DES MSP annexure (PDF pages 3-5) into a machine-readable CSV.

Source: Ministry of Agriculture & FW, Economics, Statistics & Evaluation Division
(MSP Section), F.No.9-3/2024-MSP-ES dated 6 May 2026, Annexure "Minimum Support
Price of Kharif Crops & Rabi Crops since 1995-96 to 2026-27 (Marketing
Season-wise)". Values are Rs per quintal exactly as printed; footnote symbols
are moved to `note`. Transcribed by hand - spot-check against the PDF.

Usage:
    python -I src/build_msp_table.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "prices" / "msp" / "des_msp_2004-05_to_2026-27_transcribed.csv"

KMS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2004, 2026)]  # KMS 2004-05 .. 2025-26
RMS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2004, 2027)]  # RMS 2004-05 .. 2026-27

KHARIF = {
    ("PADDY", "Common"): [560, 570, 580, 745, 900, 1000, 1000, 1080, 1250, 1310, 1360, 1410, 1470, 1550, 1750, 1815, 1868, 1940, 2040, 2183, 2300, 2369],
    ("JOWAR", "Hybrid"): [515, 525, 540, 600, 840, 840, 880, 980, 1500, 1500, 1530, 1570, 1625, 1700, 2430, 2550, 2620, 2738, 2970, 3180, 3371, 3699],
    ("BAJRA", ""): [515, 525, 540, 600, 840, 840, 880, 980, 1175, 1250, 1250, 1275, 1330, 1425, 1950, 2000, 2150, 2250, 2350, 2500, 2625, 2775],
    ("MAIZE", ""): [525, 540, 540, 620, 840, 840, 880, 980, 1175, 1310, 1310, 1325, 1365, 1425, 1700, 1760, 1850, 1870, 1962, 2090, 2225, 2400],
    ("TUR (ARHAR)", ""): [1390, 1400, 1410, 1590, 2000, 2300, 3000, 3200, 3850, 4300, 4350, 4625, 5050, 5450, 5675, 5800, 6000, 6300, 6600, 7000, 7550, 8000],
    ("MOONG", ""): [1410, 1520, 1520, 1740, 2520, 2760, 3170, 3500, 4400, 4500, 4600, 4850, 5225, 5575, 6975, 7050, 7196, 7275, 7755, 8558, 8682, 8768],
    ("URAD", ""): [1410, 1520, 1520, 1740, 2520, 2520, 2900, 3300, 4300, 4300, 4350, 4625, 5000, 5400, 5600, 5700, 6000, 6300, 6600, 6950, 7400, 7800],
    ("COTTON", "Medium Staple"): [1760, 1760, 1770, 1800, 2500, 2500, 2500, 2800, 3600, 3700, 3750, 3800, 3860, 4020, 5150, 5255, 5515, 5726, 6080, 6620, 7121, 7710],
    ("COTTON", "Long Staple"): [1960, 1980, 1990, 2030, 3000, 3000, 3000, 3300, 3900, 4000, 4050, 4100, 4160, 4320, 5450, 5550, 5825, 6025, 6380, 7020, 7521, 8110],
    ("GROUNDNUT", ""): [1500, 1520, 1520, 1550, 2100, 2100, 2300, 2700, 3700, 4000, 4000, 4030, 4220, 4450, 4890, 5090, 5275, 5550, 5850, 6377, 6783, 7263],
    ("SOYABEAN", "Yellow"): [1000, 1010, 1020, 1050, 1390, 1390, 1440, 1690, 2240, 2560, 2560, 2600, 2775, 3050, 3399, 3710, 3880, 3950, 4300, 4600, 4892, 5328],
}
RABI = {
    ("WHEAT", ""): [630, 640, 700, 850, 1000, 1080, 1100, 1170, 1285, 1350, 1400, 1450, 1525, 1625, 1735, 1840, 1925, 1975, 2015, 2125, 2275, 2425, 2585],
    ("BARLEY", ""): [525, 540, 550, 565, 650, 680, 750, 780, 980, 980, 1100, 1150, 1225, 1325, 1410, 1440, 1525, 1600, 1635, 1735, 1850, 1980, 2150],
    ("GRAM", ""): [1400, 1425, 1435, 1445, 1600, 1730, 1760, 2100, 2800, 3000, 3100, 3175, 3500, 4000, 4400, 4620, 4875, 5100, 5230, 5335, 5440, 5650, 5875],
    ("MASUR (LENTIL)", ""): [1500, 1525, 1535, 1545, 1700, 1870, 1870, 2250, 2800, 2900, 2950, 3075, 3400, 3950, 4250, 4475, 4800, 5100, 5500, 6000, 6425, 6700, 7000],
    ("RAPESEED & MUSTARD", ""): [1600, 1700, 1715, 1715, 1800, 1830, 1830, 1850, 2500, 3000, 3050, 3100, 3350, 3700, 4000, 4200, 4425, 4650, 5050, 5450, 5650, 5950, 6200],
}

# Footnotes as printed (season, crop) -> note
NOTES = {
    ("KMS", "2006-07", "PADDY"): "additional incentive bonus Rs 40/q payable 1.10.2006-31.03.2007 (Bihar to 31.5.2007), not included",
    ("KMS", "2007-08", "PADDY"): "745 incl. Central bonus Rs 100/q; raised to 850 (Grade A 880) from 12.06.2008",
    ("KMS", "2008-09", "PADDY"): "incl. Central bonus Rs 50/q",
    ("KMS", "2009-10", "PADDY"): "incl. Central bonus Rs 50/q",
    ("KMS", "2007-08", "TUR (ARHAR)"): "incl. Central bonus Rs 40/q",
    ("KMS", "2007-08", "MOONG"): "incl. Central bonus Rs 40/q",
    ("KMS", "2007-08", "URAD"): "incl. Central bonus Rs 40/q",
    **{("KMS", s, c): "additional incentive Rs 500/q on procurement during harvest, not included"
       for s in ("2010-11", "2011-12") for c in ("TUR (ARHAR)", "MOONG", "URAD")},
    ("KMS", "2015-16", "TUR (ARHAR)"): "incl. Central bonus Rs 200/q",
    ("KMS", "2015-16", "MOONG"): "incl. Central bonus Rs 200/q",
    ("KMS", "2015-16", "URAD"): "incl. Central bonus Rs 200/q",
    ("KMS", "2016-17", "TUR (ARHAR)"): "incl. Central bonus Rs 425/q",
    ("KMS", "2016-17", "MOONG"): "incl. Central bonus Rs 425/q",
    ("KMS", "2016-17", "URAD"): "incl. Central bonus Rs 425/q",
    ("KMS", "2017-18", "TUR (ARHAR)"): "incl. Central bonus Rs 200/q",
    ("KMS", "2017-18", "MOONG"): "incl. Central bonus Rs 200/q",
    ("KMS", "2017-18", "URAD"): "incl. Central bonus Rs 200/q",
    ("KMS", "2016-17", "GROUNDNUT"): "incl. Central bonus Rs 100/q",
    ("KMS", "2017-18", "GROUNDNUT"): "incl. Central bonus Rs 200/q",
    ("KMS", "2016-17", "SOYABEAN"): "incl. Central bonus Rs 100/q",
    ("KMS", "2017-18", "SOYABEAN"): "incl. Central bonus Rs 200/q",
    ("RMS", "2006-07", "WHEAT"): "incl. Central bonus Rs 50/q",
    ("RMS", "2007-08", "WHEAT"): "incl. Central bonus Rs 100/q",
    ("RMS", "2011-12", "WHEAT"): "incl. Central bonus Rs 50/q",
    ("RMS", "2016-17", "GRAM"): "incl. Central bonus Rs 75/q",
    ("RMS", "2016-17", "MASUR (LENTIL)"): "incl. Central bonus Rs 75/q",
    ("RMS", "2017-18", "GRAM"): "incl. Central bonus Rs 200/q",
    ("RMS", "2017-18", "MASUR (LENTIL)"): "incl. Central bonus Rs 150/q",
    ("RMS", "2017-18", "RAPESEED & MUSTARD"): "incl. Central bonus Rs 100/q",
    ("RMS", "2018-19", "GRAM"): "incl. Central bonus Rs 150/q",
    ("RMS", "2018-19", "MASUR (LENTIL)"): "incl. Central bonus Rs 100/q",
    ("RMS", "2018-19", "RAPESEED & MUSTARD"): "incl. Central bonus Rs 100/q",
}


def build() -> pd.DataFrame:
    rows = []
    for season, seasons, table in (("KMS", KMS, KHARIF), ("RMS", RMS, RABI)):
        for (crop, variety), values in table.items():
            assert len(values) == len(seasons), (crop, len(values))
            for s, v in zip(seasons, values):
                rows.append((season, s, crop, variety, v, NOTES.get((season, s, crop), "")))
    df = pd.DataFrame(rows, columns=["season_type", "marketing_season", "crop", "variety", "msp_rs_per_quintal", "note"])
    df["source"] = "DES MSP Section F.No.9-3/2024-MSP-ES (6 May 2026), Annexure pp.3-5"
    df.to_csv(OUT, index=False)
    return df


if __name__ == "__main__":
    print(f"{len(build())} rows -> {OUT}")
