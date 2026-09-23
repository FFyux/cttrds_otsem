# Plateforme de saisie des indicateurs de fréquentation touristique

Application web Django permettant aux sites touristiques de saisir mensuellement
leurs chiffres de fréquentation (total, par provenance, jours d'ouverture).

## Fonctionnalités

- Gestion des utilisateurs avec rattachement à un site touristique
- Deux rôles : **saisisseur** (ne voit/saisit que son site) et **administrateur**
  (accès à tous les sites, gestion des utilisateurs et des sites)
- Saisie mensuelle : fréquentation totale, locale, France, étranger, jours d'ouverture
- Contrôle automatique : un site ne peut avoir qu'une seule saisie par mois/année,
  et la somme des provenances ne peut pas dépasser le total déclaré
- Authentification complète avec réinitialisation de mot de passe par email
- Export CSV des données (pour réinjection dans Power BI / Excel)
- Interface d'administration Django (`/admin/`) en complément des écrans dédiés

## Installation locale

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

L'application est ensuite accessible sur http://127.0.0.1:8000/
et l'admin Django sur http://127.0.0.1:8000/admin/

## Premiers pas

1. Connectez-vous avec le compte superutilisateur créé (`createsuperuser`)
2. Allez dans **Sites** > **Nouveau site** pour créer vos sites touristiques
3. Allez dans **Utilisateurs** > **Nouvel utilisateur** pour créer un compte
   par site, en sélectionnant le site rattaché et le rôle "Saisisseur"
4. Communiquez l'identifiant et le mot de passe initial à chaque responsable
   de site (ils pourront le changer via "Mot de passe oublié")

## Déploiement en production

Avant mise en production, modifier `indicateurs_tourisme/settings.py` :

1. **SECRET_KEY** : générer une nouvelle clé secrète et la sortir du code
   (variable d'environnement), ne jamais garder celle du dépôt
2. **DEBUG = False**
3. **ALLOWED_HOSTS** : ajouter le nom de domaine réel (ex: `indicateurs.saint-etienne-tourisme.fr`)
4. **Base de données** : remplacer SQLite par PostgreSQL pour un usage à 30+ utilisateurs
   concurrents (`DATABASES` dans settings.py, driver `psycopg`)
5. **Email** : remplacer `EMAIL_BACKEND` (actuellement en mode "console", les emails
   s'affichent dans les logs) par un vrai backend SMTP, par exemple :

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.votre-fournisseur.fr'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'votre-compte'
EMAIL_HOST_PASSWORD = 'votre-mot-de-passe'  # à mettre en variable d'environnement
```

6. **Fichiers statiques** : exécuter `python manage.py collectstatic` et servir
   via un serveur web (nginx) ou whitenoise
7. **Serveur applicatif** : utiliser gunicorn ou uwsgi derrière nginx plutôt que
   le serveur de développement (`runserver`)
8. Activer HTTPS et les en-têtes de sécurité Django (`SECURE_SSL_REDIRECT`,
   `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)

## Structure du projet

```
indicateurs_tourisme/
├── manage.py
├── requirements.txt
├── indicateurs_tourisme/      # configuration du projet (settings, urls)
└── suivi/                     # application principale
    ├── models.py               # Utilisateur, SiteTouristique, IndicateurMensuel
    ├── views.py                # logique métier (saisie, listes, export, admin)
    ├── forms.py                # formulaires
    ├── urls.py                 # routes de l'application
    ├── admin.py                # configuration de l'admin Django
    └── templates/suivi/        # gabarits HTML (Bootstrap 5)
```

## API JSON (pour Power BI / outils externes)

Deux endpoints en lecture seule, authentifiés par clé API :

- `GET /api/indicateurs/` — liste des indicateurs (filtres optionnels : `?annee=2026&mois=6&site=1`)
- `GET /api/sites/` — liste des sites touristiques

Authentification : header `X-API-Key: <clé>` ou paramètre `?cle=<clé>`.

Génération d'une clé : page **Utilisateurs** (admin), bouton "Générer" / "Régénérer"
en face de l'utilisateur concerné. La clé n'est affichée qu'une fois, en clair,
dans le message de confirmation — à copier immédiatement.

Un utilisateur "saisisseur" avec une clé API ne voit que les données de son site ;
un administrateur avec une clé voit toutes les données.

Exemple d'appel depuis Power BI (connecteur Web) :
```
https://votre-domaine.fr/api/indicateurs/?annee=2026&cle=VOTRE_CLE
```

## Rappels automatiques par email

Commande de gestion à planifier en tâche périodique :

```bash
python manage.py rappel_saisie
```

Par défaut, elle vérifie le **mois précédent** et envoie un email à chaque
saisisseur dont le site n'a pas encore de saisie pour cette période.

Options utiles :
- `--annee 2026 --mois 6` : cibler un mois précis plutôt que le mois précédent
- `--resume-admin` : envoie en plus un récapitulatif aux administrateurs
- `--simulation` : n'envoie aucun email, affiche seulement ce qui serait fait (utile pour tester)

Exemple recommandé en production (le 5 de chaque mois, rappel + résumé admin) :
```bash
python manage.py rappel_saisie --resume-admin
```

Sur PythonAnywhere, cela se programme dans l'onglet **Tasks** (tâche planifiée
quotidienne ou mensuelle qui exécute la commande ci-dessus).

## Évolutions possibles

- Tableaux de bord graphiques (évolution mensuelle, comparaison de sites)
- Rappels automatiques par email aux saisisseurs en retard de saisie
- API REST pour connecter Power BI directement (au lieu de l'export CSV)
- Validation/verrouillage des données après une date de clôture mensuelle
