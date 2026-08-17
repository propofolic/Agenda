# Agenda Concerts — guide de mise en place

Ce projet scrape la programmation de 14 salles romandes, génère un fichier
`events.ics`, et le republie automatiquement chaque jour via GitHub Actions +
GitHub Pages. Vous vous abonnez ensuite à ce fichier depuis un agenda séparé
dans Google Calendar.

## Salles couvertes

Docks, Le Romandie, Nouveau Monde, Fri-Son, Folklor, Les Citrons Masqués,
D! Club, Rocking Chair, Le Bout du Monde, Le Rez-Usine, La Brèche,
La Gravière, Post Tenebras Rock, Audio Club.

**motelcampo.ch n'est pas inclus** : ce site charge son contenu via
JavaScript (la page est vide au premier chargement), la méthode
requests + BeautifulSoup ne peut donc pas le lire. Il faudrait un outil
comme Playwright, qui simule un vrai navigateur — dites-le-moi si vous
voulez que je l'ajoute.

## Important — ces scrapers n'ont pas pu être testés en conditions réelles

Chaque scraper a été écrit en inspectant la structure HTML réelle de
chaque site, mais mon environnement n'a pas accès à internet en dehors
d'une liste de domaines autorisés (GitHub, PyPI, etc.) — je n'ai donc pas
pu exécuter le script contre les vrais sites pour vérifier que chaque
scraper fonctionne à 100%. **Il est important de suivre l'étape 2
ci-dessous (test en local) avant de tout automatiser.** Si un scraper
retourne 0 événement ou une erreur, copiez-collez le message dans notre
conversation avec le nom de la salle concernée : je pourrai l'ajuster.

## Structure du projet

```
agenda-concerts/
├── scraper.py                          # le script qui scrape et génère events.ics
├── requirements.txt                    # dépendances Python
├── .github/workflows/update-calendar.yml  # automatisation GitHub Actions
└── README.md
```

---

## Étape 1 — Créer le dépôt GitHub

1. Si besoin, créez un compte sur [github.com](https://github.com).
2. Cliquez sur **New repository**.
3. Nommez-le par exemple `agenda-concerts`, laissez-le **public** (nécessaire
   pour GitHub Pages gratuit), cochez "Add a README" ou pas, peu importe.
4. Créez le dépôt.

## Étape 2 — Tester en local avant de tout automatiser

Sur votre ordinateur, avec Python déjà installé :

```bash
git clone https://github.com/VOTRE-PSEUDO/agenda-concerts.git
cd agenda-concerts
python3 -m venv venv
source venv/bin/activate        # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
python scraper.py
```

Vous devriez voir apparaître, dans la console, une ligne par salle indiquant
combien d'événements ont été trouvés :

```
Scraping : scrape_docks
  -> 12 evenement(s) trouve(s)
Scraping : scrape_leromandie
  -> 15 evenement(s) trouve(s)
...
Fichier events.ics genere avec 87 evenement(s) au total.
```

Si une salle affiche `0 evenement(s)` ou qu'une erreur s'affiche, c'est que
le scraper de cette salle a besoin d'un ajustement (voir "Maintenance"
ci-dessous) — dites-le-moi, avec le message d'erreur exact, et je corrige
la fonction correspondante.

Ouvrez ensuite `events.ics` avec un éditeur de texte pour vérifier son
contenu, ou double-cliquez dessus pour l'importer ponctuellement dans un
agenda et voir le rendu.

## Étape 3 — Ajouter une salle supplémentaire (optionnel)

Si vous voulez ajouter une salle qui n'est pas dans la liste initiale :

1. Ouvrez la page "programmation" ou "agenda" du site dans votre navigateur.
2. Clic droit sur un événement affiché → **Inspecter**, pour voir le HTML
   correspondant (classe autour de chaque événement, balise du titre, de la
   date, lien vers la page de l'événement).
3. Le plus simple est de me donner l'URL de la salle : je peux inspecter la
   page et vous écrire directement la fonction `scrape_xxx()` correspondante,
   comme je l'ai fait pour les 14 salles incluses.
4. Ajoutez la nouvelle fonction à la liste `SCRAPERS` en bas de `scraper.py`.

**Point légal/éthique** : vérifiez le fichier `robots.txt` du site
(`https://www.site.fr/robots.txt`) et ses conditions d'utilisation. Un usage
personnel, à faible fréquence (une fois par jour), respectant les règles du
site, pose en général peu de problème — mais ça reste à vérifier au cas par
cas.

## Étape 4 — Envoyer les modifications sur GitHub

```bash
git add scraper.py
git commit -m "Ajout du scraper pour la salle X"
git push
```

## Étape 5 — Vérifier les permissions du workflow

Le fichier `.github/workflows/update-calendar.yml` est déjà inclus dans le
projet et permet à GitHub d'exécuter le scraper automatiquement chaque jour
à 6h UTC, et de committer le résultat.

Pour qu'il ait le droit d'écrire dans le dépôt :
1. Sur GitHub, allez dans **Settings** du dépôt.
2. Menu **Actions** → **General**.
3. Descendez à **Workflow permissions**, sélectionnez
   **Read and write permissions**, sauvegardez.

Le workflow se déclenchera automatiquement chaque jour. Vous pouvez aussi le
lancer manuellement : onglet **Actions** du dépôt → sélectionnez
"Update concert calendar" → **Run workflow**.

## Étape 6 — Activer GitHub Pages

1. **Settings** → **Pages**.
2. Sous "Build and deployment", **Source** : `Deploy from a branch`.
3. **Branch** : `main`, dossier `/ (root)`. Sauvegardez.
4. Après quelques minutes, GitHub affiche l'URL publique de votre site, du
   type :
   `https://VOTRE-PSEUDO.github.io/agenda-concerts/`
5. Votre fichier sera donc accessible à :
   `https://VOTRE-PSEUDO.github.io/agenda-concerts/events.ics`

(La première fois, il faut attendre que le workflow ait tourné au moins une
fois pour que `events.ics` existe dans le dépôt.)

## Étape 7 — Abonner Google Calendar à ce flux

1. Dans Google Calendar (version web), cliquez sur le **+** à côté de
   "Autres agendas" (colonne de gauche).
2. **À partir de l'URL**.
3. Collez `https://VOTRE-PSEUDO.github.io/agenda-concerts/events.ics`.
4. **Ajouter l'agenda**.

Un nouvel agenda apparaît, distinct de votre agenda principal — vous pouvez
l'afficher/masquer et lui donner une couleur à part. Google Calendar relit ce
flux automatiquement toutes les quelques heures (la fréquence exacte n'est
pas réglable, c'est géré par Google).

## Maintenance

- Si une salle change la structure de son site, le scraper correspondant
  cessera de trouver des événements (il ne plantera pas, il retournera juste
  une liste vide) — à surveiller de temps en temps.
- Pour ajouter une nouvelle salle, voir l'étape 3.
- Les logs de chaque exécution sont visibles dans l'onglet **Actions** du
  dépôt, utile pour diagnostiquer un souci.
- Certaines salles n'affichent pas l'année sur leur page (La Gravière, Post
  Tenebras Rock, Le Bout du Monde) : le script déduit l'année la plus
  probable (l'occurrence future la plus proche). Autour du réveillon, si un
  événement de "janvier" apparaît avec la mauvaise année, signalez-le-moi.
