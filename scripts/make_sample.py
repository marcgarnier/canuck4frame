"""Generate a small, SYNTHETIC sample corpus for offline pipeline runs.

This is NOT real journalism. It is a set of programmatically composed,
plausible-sounding article texts spanning several distinct "frames", languages
(EN/FR), outlets, and years — just enough for BERTopic to produce clusters so
the notebooks run end-to-end without hitting the network.

Real analyses must use ``python scripts/run_pipeline.py --collect`` to pull the
actual corpus from GDELT.

Run: ``python scripts/make_sample.py``
"""

from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample" / "sample_articles.jsonl"

# Each frame is a bag of sentences the generator samples from.
FRAMES_EN = {
    "far_right_engine": [
        "Researchers warn that 4chan has become an incubator for far-right and white-nationalist ideology.",
        "Extremism experts link the imageboard 4chan to a growing pipeline of radicalization among young men.",
        "The report describes how hate speech and racist memes spread from 4chan into mainstream politics.",
        "Analysts say coordinated harassment campaigns are organized on anonymous boards like 4chan and 8chan.",
        "A manifesto posted before the attack echoed language commonly found on 4chan message boards.",
    ],
    "meme_culture": [
        "Internet historians trace many viral memes back to the anonymous community on 4chan.",
        "The playful, absurdist humour of 4chan shaped a generation of online meme culture.",
        "From Rickrolling to lolcats, 4chan sits at the origin of countless internet jokes and memes.",
        "Digital culture writers describe 4chan as a chaotic engine of creativity and viral content.",
        "The imageboard's meme factory continues to influence how humour travels across the web.",
    ],
    "free_speech_haven": [
        "Supporters describe 4chan as a rare bastion of anonymous free speech online.",
        "Debates about content moderation often cite 4chan as a test of free expression limits.",
        "The site's defenders argue that anonymity on 4chan protects unpopular opinions from censorship.",
        "Critics counter that unmoderated free speech on 4chan enables abuse and disinformation.",
        "Civil-liberties commentators weigh anonymity and free speech against real-world harm.",
    ],
    "security_threat": [
        "Police investigated threats of violence posted anonymously to 4chan this week.",
        "Cybersecurity officials tracked a hoax that originated on the 4chan message board.",
        "Authorities say a bomb threat circulated on 4chan before being flagged to investigators.",
        "A leaked cache of private photos was first distributed through 4chan, prosecutors allege.",
        "Law-enforcement agencies monitor 4chan for coordinated threats and criminal activity.",
    ],
}

FRAMES_FR = {
    "moteur_extreme_droite": [
        "Des chercheurs affirment que 4chan est devenu un incubateur de l'idéologie d'extrême droite.",
        "Les experts en radicalisation associent le forum anonyme 4chan à la montée du nationalisme identitaire.",
        "Le rapport décrit comment les discours haineux et les mèmes racistes se propagent depuis 4chan.",
        "Des campagnes de harcèlement seraient coordonnées sur des forums anonymes comme 4chan et 8chan.",
        "Le manifeste diffusé avant l'attaque reprenait un vocabulaire répandu sur les forums de 4chan.",
    ],
    "culture_meme": [
        "Les historiens du web font remonter de nombreux mèmes viraux à la communauté anonyme de 4chan.",
        "L'humour absurde de 4chan a façonné toute une génération de la culture des mèmes en ligne.",
        "De Rickroll aux lolcats, 4chan est à l'origine d'innombrables blagues et mèmes d'Internet.",
        "Les observateurs décrivent 4chan comme une usine à mèmes chaotique mais créative.",
        "Le forum d'images continue d'influencer la circulation de l'humour sur le web.",
    ],
    "liberte_expression": [
        "Ses partisans présentent 4chan comme un rare refuge de la liberté d'expression anonyme.",
        "Les débats sur la modération citent souvent 4chan comme une limite de la liberté d'expression.",
        "Pour ses défenseurs, l'anonymat sur 4chan protège les opinions impopulaires de la censure.",
        "Les critiques répliquent que l'absence de modération sur 4chan favorise les abus et la désinformation.",
        "Des commentateurs pèsent l'anonymat et la liberté d'expression face aux préjudices réels.",
    ],
    "menace_securite": [
        "La police a enquêté sur des menaces de violence publiées anonymement sur 4chan.",
        "Les autorités ont suivi un canular né sur le forum 4chan cette semaine.",
        "Une alerte à la bombe aurait circulé sur 4chan avant d'être signalée aux enquêteurs.",
        "Un lot de photos privées aurait d'abord été diffusé via 4chan, selon les procureurs.",
        "Les forces de l'ordre surveillent 4chan à la recherche de menaces coordonnées.",
    ],
}

OUTLETS_EN = [("CBC News", "cbc.ca")]
OUTLETS_FR = [
    ("Radio-Canada", "ici.radio-canada.ca"),
    ("Le Devoir", "ledevoir.com"),
    ("TVA Nouvelles", "tvanouvelles.ca"),
]
YEARS = list(range(2015, 2026))


def _article(sentences: list[str], n: int = 6) -> str:
    picks = [random.choice(sentences) for _ in range(n)]
    return " ".join(picks)


def build() -> list[dict]:
    rows = []
    idx = 0
    for lang, frames, outlets in [("en", FRAMES_EN, OUTLETS_EN), ("fr", FRAMES_FR, OUTLETS_FR)]:
        for frame_key, sentences in frames.items():
            for _ in range(8):  # 8 articles per frame per language
                source, domain = random.choice(outlets)
                year = random.choice(YEARS)
                month, day = random.randint(1, 12), random.randint(1, 28)
                idx += 1
                rows.append(
                    {
                        "id": f"sample-{idx:03d}",
                        "title": f"[SAMPLE] Coverage of 4chan — {frame_key}",
                        "url": f"https://{domain}/sample/{idx:03d}",
                        "date": f"{year}-{month:02d}-{day:02d}",
                        "source": source,
                        "domain": domain,
                        "lang": lang,
                        "body": _article(sentences),
                    }
                )
    random.shuffle(rows)
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} synthetic sample articles to {OUT}")


if __name__ == "__main__":
    main()
