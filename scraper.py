"""
Scraper d'événements pour 15 salles de concert / clubs romands.
Génère un fichier events.ics agrégeant les événements de toutes les salles.

Chaque salle a sa propre fonction scrape_xxx(), écrite d'après la structure
HTML réelle du site observée en août 2026. Si un site change de structure,
la fonction correspondante retournera simplement une liste vide (elle ne
fera pas planter le reste du script) - voir la section "Maintenance" du
README pour savoir comment la corriger.

Salle non couverte : motelcampo.ch charge son contenu via JavaScript
(page vide au premier chargement) et ne peut pas être scrapé avec
requests + BeautifulSoup. Il faudrait Playwright pour cette salle -
voir la note à la fin du fichier.
"""

import re
import sys
import uuid
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AgendaConcertsBot/1.0; +perso)"
}

MOIS_FR = {
    "janvier": 1, "janv.": 1, "février": 2, "févr.": 2, "mars": 3,
    "avril": 4, "avr.": 4, "mai": 5, "juin": 6, "juillet": 7, "juil.": 7,
    "août": 8, "septembre": 9, "sept.": 9, "octobre": 10, "oct.": 10,
    "novembre": 11, "nov.": 11, "décembre": 12, "déc.": 12,
}


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def _infer_year(month, today=None):
    """Si l'année n'est pas précisée sur le site, on suppose l'occurrence
    future la plus proche (année en cours, ou suivante si le mois est
    déjà passé cette année)."""
    today = today or datetime.today()
    return today.year if month >= today.month else today.year + 1


# ---------------------------------------------------------------------
# 1. Docks (Lausanne) - date encodée dans l'URL /evenement/.../YYYYMMDD/
# ---------------------------------------------------------------------
def scrape_docks():
    events = []
    try:
        soup = _get("https://www.docks.ch/programme/")
    except requests.RequestException as e:
        print(f"[docks] {e}", file=sys.stderr)
        return events

    seen = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/evenement/[^/]+/(\d{8})/", a["href"])
        if not m or a["href"] in seen:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        try:
            event_date = datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        seen.add(a["href"])
        events.append({
            "title": title, "start": event_date,
            "location": "Docks, Lausanne", "url": a["href"], "venue": "Docks",
        })
    return events


# ---------------------------------------------------------------------
# 2. Le Romandie (Lausanne) - date en toutes lettres près du lien
# ---------------------------------------------------------------------
def scrape_leromandie():
    events = []
    try:
        soup = _get("https://www.leromandie.ch/programmation")
    except requests.RequestException as e:
        print(f"[leromandie] {e}", file=sys.stderr)
        return events

    date_re = re.compile(
        r"(\d{1,2})\s+(janv\.|févr\.|mars|avr\.|mai|juin|juil\.|août|sept\.|oct\.|nov\.|déc\.)\s+(\d{4})",
        re.IGNORECASE,
    )
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/event/[a-z0-9\-]+/?$")):
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)

        container, text_block = a, ""
        for _ in range(4):
            container = container.parent
            if container is None:
                break
            text_block = container.get_text(" ", strip=True)
            if date_re.search(text_block):
                break

        m = date_re.search(text_block)
        if not m:
            continue
        day, month_str, year = m.groups()
        month = MOIS_FR.get(month_str.lower())
        if not month:
            continue
        try:
            event_date = datetime(int(year), month, int(day))
        except ValueError:
            continue

        title_el = container.find(["h2", "h3", "h4"]) if container else None
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        if not title:
            continue

        events.append({
            "title": title, "start": event_date,
            "location": "Le Romandie, Lausanne",
            "url": href if href.startswith("http") else "https://www.leromandie.ch" + href,
            "venue": "Le Romandie",
        })
    return events


# ---------------------------------------------------------------------
# 3. Nouveau Monde (Fribourg) - tout dans le texte du lien
# ---------------------------------------------------------------------
def scrape_nouveau_monde():
    events = []
    try:
        soup = _get("https://nouveaumonde.ch/agenda/")
    except requests.RequestException as e:
        print(f"[nouveau-monde] {e}", file=sys.stderr)
        return events

    pattern = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(?:[a-z]+\s*-?\s*)*(.+?)\s+\d{1,2}h\d{2}$", re.IGNORECASE)

    for a in soup.find_all("a", href=re.compile(r"/agenda/[a-z0-9\-.]+/?$")):
        text = a.get_text(" ", strip=True)
        m = pattern.match(text)
        if not m:
            continue
        day, month, year, title = m.groups()
        try:
            event_date = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
        events.append({
            "title": title.strip(), "start": event_date,
            "location": "Nouveau Monde, Fribourg",
            "url": a["href"] if a["href"].startswith("http") else "https://nouveaumonde.ch" + a["href"],
            "venue": "Nouveau Monde",
        })
    return events


# ---------------------------------------------------------------------
# 4. Fri-Son (Fribourg) - jour+date+heure collés, lien /programme/YYYY/MM/slug
# ---------------------------------------------------------------------
def scrape_frison():
    events = []
    try:
        soup = _get("https://www.fri-son.ch/fr/programme")
    except requests.RequestException as e:
        print(f"[fri-son] {e}", file=sys.stderr)
        return events

    pattern = re.compile(
        r"(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})(\d{1,2}):(\d{2})\s*(.+)",
        re.IGNORECASE,
    )
    for a in soup.find_all("a", href=re.compile(r"/fr/programme/\d{4}/\d{2}/[a-z0-9\-]+/?$")):
        text = a.get_text(" ", strip=True)
        m = pattern.search(text)
        if not m:
            continue
        day, month_str, year, _hour, _minute, rest = m.groups()
        month = MOIS_FR.get(month_str.lower())
        if not month:
            continue
        try:
            event_date = datetime(int(year), month, int(day))
        except ValueError:
            continue
        title = rest.strip().split("  ")[0].strip() or rest.strip()

        events.append({
            "title": title, "start": event_date,
            "location": "Fri-Son, Fribourg",
            "url": a["href"] if a["href"].startswith("http") else "https://www.fri-son.ch" + a["href"],
            "venue": "Fri-Son",
        })
    return events


# ---------------------------------------------------------------------
# 5. Folklor (Lausanne) - pas de lien par événement, dates + titres en texte
# ---------------------------------------------------------------------
def scrape_folklor():
    events = []
    url = "https://www.folklor.club/events/"
    try:
        soup = _get(url)
    except requests.RequestException as e:
        print(f"[folklor] {e}", file=sys.stderr)
        return events

    date_re = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
    nodes = list(soup.stripped_strings)

    for i, node in enumerate(nodes):
        m = date_re.match(node)
        if not m or i + 1 >= len(nodes):
            continue
        day, month, year = m.groups()
        try:
            event_date = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
        events.append({
            "title": nodes[i + 1], "start": event_date,
            "location": "Folklor, Lausanne", "url": url, "venue": "Folklor",
        })
    return events


# ---------------------------------------------------------------------
# 6. Les Citrons Masqués (Yverdon) - regroupés sous des titres "## mois année"
# ---------------------------------------------------------------------
def scrape_citrons_masques():
    events = []
    try:
        soup = _get("https://citronsmasques.ch/")
    except requests.RequestException as e:
        print(f"[citrons-masques] {e}", file=sys.stderr)
        return events

    month_re = re.compile(
        r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})",
        re.IGNORECASE,
    )
    day_re = re.compile(r"^(lu|ma|me|je|ve|sa|di)\.?\s*(\d{1,2})\s*(.+)$", re.IGNORECASE)

    current_month, current_year = None, None
    for el in soup.find_all(["h2", "a"]):
        if el.name == "h2":
            m = month_re.search(el.get_text(strip=True))
            if m:
                current_month = MOIS_FR.get(m.group(1).lower())
                current_year = int(m.group(2))
            continue

        if current_month is None or not el.get("href") or "/events/" not in el["href"]:
            continue
        m = day_re.match(el.get_text(" ", strip=True))
        if not m:
            continue
        day, title = int(m.group(2)), m.group(3).strip()
        try:
            event_date = datetime(current_year, current_month, day)
        except ValueError:
            continue
        events.append({
            "title": title, "start": event_date,
            "location": "Les Citrons Masqués, Yverdon-les-Bains",
            "url": el["href"], "venue": "Les Citrons Masqués",
        })
    return events


# ---------------------------------------------------------------------
# 7. D! Club (Lausanne) - date encodée dans l'URL /agenda/YYYYMMDD/slug
# ---------------------------------------------------------------------
def scrape_dclub():
    events = []
    try:
        soup = _get("https://dclub.ch/agenda/")
    except requests.RequestException as e:
        print(f"[dclub] {e}", file=sys.stderr)
        return events

    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/agenda/(\d{8})/[a-z0-9\-]+")):
        href = a["href"]
        base_href = href.split("#")[0]
        m = re.search(r"/agenda/(\d{8})/", href)
        if not m or base_href in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        try:
            event_date = datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        seen.add(base_href)
        events.append({
            "title": title, "start": event_date,
            "location": "D! Club, Lausanne",
            "url": href if href.startswith("http") else "https://dclub.ch" + href,
            "venue": "D! Club",
        })
    return events


# ---------------------------------------------------------------------
# 8. Rocking Chair (Vevey) - date DD.MM.YYYY dans le texte du lien
# ---------------------------------------------------------------------
def scrape_rocking_chair():
    events = []
    try:
        soup = _get("https://www.rocking-chair.ch/")
    except requests.RequestException as e:
        print(f"[rocking-chair] {e}", file=sys.stderr)
        return events

    date_re = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
    for a in soup.find_all("a", href=re.compile(r"post_type=events")):
        text = a.get_text(" ", strip=True)
        m = date_re.search(text)
        if not m:
            continue
        day, month, year = m.groups()
        try:
            event_date = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
        title = text.split(" - Rocking Chair")[0].strip()
        if not title:
            continue
        events.append({
            "title": title, "start": event_date,
            "location": "Rocking Chair, Vevey", "url": a["href"], "venue": "Rocking Chair",
        })
    return events


# ---------------------------------------------------------------------
# 9. Le Bout du Monde (Vevey) - page scopée au mois courant, pas d'année
# ---------------------------------------------------------------------
def scrape_bout_du_monde():
    events = []
    url = "https://www.leboutdumonde.ch/programme/"
    try:
        soup = _get(url)
    except requests.RequestException as e:
        print(f"[bout-du-monde] {e}", file=sys.stderr)
        return events

    date_re = re.compile(r"(\d{2})\.(\d{2})\b")
    today = datetime.today()

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        m = date_re.search(text)
        if not m:
            continue
        day, month = int(m.group(1)), int(m.group(2))
        year = _infer_year(month, today)
        try:
            event_date = datetime(year, month, day)
        except ValueError:
            continue
        title_el = li.find_next(["h2", "h3"])
        link_el = li.find_next("a", href=re.compile(r"/evenements/"))
        events.append({
            "title": title_el.get_text(strip=True) if title_el else "Événement",
            "start": event_date,
            "location": "Le Bout du Monde, Vevey",
            "url": link_el["href"] if link_el else url,
            "venue": "Le Bout du Monde",
        })
    return events


# ---------------------------------------------------------------------
# 10. Le Rez-Usine (Genève) - titres "DD.MM.YY TITRE"
# ---------------------------------------------------------------------
def scrape_rez_usine():
    events = []
    url = "https://rez-usine.ch/"
    try:
        soup = _get(url)
    except requests.RequestException as e:
        print(f"[rez-usine] {e}", file=sys.stderr)
        return events

    date_re = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})\s+(.+)$")
    for h in soup.find_all(["h4", "h3"]):
        m = date_re.match(h.get_text(" ", strip=True))
        if not m:
            continue
        day, month, year2, title = m.groups()
        try:
            event_date = datetime(2000 + int(year2), int(month), int(day))
        except ValueError:
            continue
        link_el = h.find_next("a", href=re.compile(r"/portfolio-item/"))
        events.append({
            "title": title.strip(), "start": event_date,
            "location": "Le Rez-Usine, Genève",
            "url": link_el["href"] if link_el else url,
            "venue": "Le Rez-Usine",
        })
    return events


# ---------------------------------------------------------------------
# 11. La Brèche (Lausanne) - date encodée dans l'URL /events/DD-MM-YYYY
# ---------------------------------------------------------------------
def scrape_la_breche():
    events = []
    try:
        soup = _get("https://www.la-breche.fun/")
    except requests.RequestException as e:
        print(f"[la-breche] {e}", file=sys.stderr)
        return events

    for a in soup.find_all("a", href=re.compile(r"/events/\d{2}-\d{2}-\d{2,4}")):
        href = a["href"]
        m = re.search(r"/events/(\d{2})-(\d{2})-(\d{2,4})", href)
        if not m:
            continue
        day, month, year = m.groups()
        year = year if len(year) == 4 else f"20{year}"
        try:
            event_date = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
        title = a.get_text(" ", strip=True).replace(
            "This is some text inside of a div block.", ""
        ).strip() or "Concert à La Brèche"
        events.append({
            "title": title, "start": event_date,
            "location": "La Brèche, Lausanne",
            "url": href if href.startswith("http") else "https://www.la-breche.fun" + href,
            "venue": "La Brèche",
        })
    return events


# ---------------------------------------------------------------------
# 12. La Gravière (Genève) - "TITRE weekday DD mois artistes" sans année
# ---------------------------------------------------------------------
def scrape_graviere():
    events = []
    try:
        soup = _get("https://lagraviere.ch/")
    except requests.RequestException as e:
        print(f"[la-graviere] {e}", file=sys.stderr)
        return events

    date_re = re.compile(
        r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(\d{1,2})\s+"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)",
        re.IGNORECASE,
    )
    today = datetime.today()
    for a in soup.find_all("a", href=re.compile(r"/evenement/[a-z0-9\-]+/?$")):
        text = a.get_text(" ", strip=True)
        m = date_re.search(text)
        if not m:
            continue
        _, day, month_str = m.groups()
        month = MOIS_FR.get(month_str.lower())
        day = int(day)
        year = _infer_year(month, today)
        try:
            event_date = datetime(year, month, day)
        except ValueError:
            continue
        title = text[:m.start()].strip() or text
        events.append({
            "title": title, "start": event_date,
            "location": "La Gravière, Genève", "url": a["href"], "venue": "La Gravière",
        })
    return events


# ---------------------------------------------------------------------
# 13. Post Tenebras Rock / L'Usine (Genève) - "ven28août" collé, sans année
# ---------------------------------------------------------------------
def scrape_ptr():
    events = []
    try:
        soup = _get("https://ptrnet.ch/evenement/")
    except requests.RequestException as e:
        print(f"[ptr] {e}", file=sys.stderr)
        return events

    date_re = re.compile(
        r"(lun|mar|mer|jeu|ven|sam|dim)\s*(\d{1,2})\s*"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)",
        re.IGNORECASE,
    )
    today = datetime.today()
    for a in soup.find_all("a", href=re.compile(r"/evenement/[a-z0-9\-]+/?$")):
        text = a.get_text(" ", strip=True)
        m = date_re.search(text)
        if not m:
            continue
        _, day, month_str = m.groups()
        month = MOIS_FR.get(month_str.lower())
        day = int(day)
        year = _infer_year(month, today)
        try:
            event_date = datetime(year, month, day)
        except ValueError:
            continue
        title = text[:m.start()].strip() or text
        events.append({
            "title": title, "start": event_date,
            "location": "Post Tenebras Rock (L'Usine), Genève",
            "url": a["href"], "venue": "Post Tenebras Rock",
        })
    return events


# ---------------------------------------------------------------------
# 14. Audio Club (Genève) - date+heure explicites "sam. 15 août 2026 23:59"
# ---------------------------------------------------------------------
def scrape_audio_club():
    events = []
    try:
        soup = _get("https://www.audio-club.ch/")
    except requests.RequestException as e:
        print(f"[audio-club] {e}", file=sys.stderr)
        return events

    date_re = re.compile(
        r"(\d{1,2})\s+(janv\.|févr\.|mars|avr\.|mai|juin|juil\.|août|sept\.|oct\.|nov\.|déc\.)\s+(\d{4})\s+(\d{1,2}):(\d{2})",
        re.IGNORECASE,
    )
    seen = set()
    for h1 in soup.find_all("h1"):
        a = h1.find("a", href=re.compile(r"/all-events/"))
        if not a or a["href"] in seen:
            continue
        node = h1.find_next(string=date_re)
        if not node:
            continue
        m = date_re.search(str(node))
        if not m:
            continue
        day, month_str, year, hour, minute = m.groups()
        month = MOIS_FR.get(month_str.lower())
        if not month:
            continue
        try:
            event_date = datetime(int(year), month, int(day), int(hour), int(minute))
        except ValueError:
            continue
        seen.add(a["href"])
        events.append({
            "title": a.get_text(strip=True), "start": event_date, "has_time": True,
            "location": "Audio Club, Genève", "url": a["href"], "venue": "Audio Club",
        })
    return events


# Liste des scrapers actifs.
# motelcampo.ch n'est pas inclus : son contenu est chargé en JavaScript
# (page vide au chargement initial), requests+BeautifulSoup ne peut pas
# le lire. Une version avec Playwright serait nécessaire - demandez-le
# si vous voulez que cette salle soit ajoutée.
SCRAPERS = [
    scrape_docks,
    scrape_leromandie,
    scrape_nouveau_monde,
    scrape_frison,
    scrape_folklor,
    scrape_citrons_masques,
    scrape_dclub,
    scrape_rocking_chair,
    scrape_bout_du_monde,
    scrape_rez_usine,
    scrape_la_breche,
    scrape_graviere,
    scrape_ptr,
    scrape_audio_club,
]


def build_calendar(all_events):
    cal = Calendar()
    cal.add("prodid", "-//Agenda Concerts Romandie//mxm.dk//")
    cal.add("version", "2.0")

    for ev in all_events:
        event = Event()
        event.add("summary", f"{ev['title']} — {ev['venue']}")
        if ev.get("has_time"):
            event.add("dtstart", ev["start"])
        else:
            event.add("dtstart", ev["start"].date())
        event.add("location", ev["location"])
        event.add("description", ev["url"])
        event["uid"] = str(uuid.uuid5(uuid.NAMESPACE_URL, ev["url"] + ev["title"]))
        cal.add_component(event)

    return cal


def main():
    all_events = []
    for scraper in SCRAPERS:
        name = scraper.__name__
        print(f"Scraping : {name}")
        events = scraper()
        print(f"  -> {len(events)} evenement(s) trouve(s)")
        all_events.extend(events)

    cal = build_calendar(all_events)
    with open("events.ics", "wb") as f:
        f.write(cal.to_ical())

    print(f"Fichier events.ics genere avec {len(all_events)} evenement(s) au total.")


if __name__ == "__main__":
    main()
