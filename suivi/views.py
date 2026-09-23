import csv
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import (
    LoginView, LogoutView,
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView,
)
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .forms import IndicateurMensuelForm, UtilisateurCreationForm, SiteTouristiqueForm, EvenementForm, choix_annees, OfficeDeTourismeForm
from .models import IndicateurMensuel, SiteTouristique, Utilisateur, Evenement, OfficeDeTourisme
from . import io_excel


def est_admin(user):
    return user.is_authenticated and user.est_admin


# --- Authentification ---------------------------------------------------

class ConnexionView(LoginView):
    template_name = "suivi/connexion.html"


class DeconnexionView(LogoutView):
    next_page = "connexion"


class ReinitMotDePasseView(PasswordResetView):
    template_name = "suivi/reinit_mdp.html"
    email_template_name = "suivi/reinit_mdp_email.txt"
    subject_template_name = "suivi/reinit_mdp_objet.txt"
    success_url = reverse_lazy("reinit_mdp_envoye")


class ReinitMotDePasseEnvoyeView(PasswordResetDoneView):
    template_name = "suivi/reinit_mdp_envoye.html"


class ReinitMotDePasseConfirmView(PasswordResetConfirmView):
    template_name = "suivi/reinit_mdp_confirm.html"
    success_url = reverse_lazy("reinit_mdp_termine")


class ReinitMotDePasseTermineView(PasswordResetCompleteView):
    template_name = "suivi/reinit_mdp_termine.html"


# --- Tableau de bord ------------------------------------------------------

@login_required
def tableau_de_bord(request):
    user = request.user
    if user.est_admin:
        indicateurs = IndicateurMensuel.objects.select_related("site").all()[:50]
        sites = SiteTouristique.objects.filter(actif=True)
    else:
        indicateurs = IndicateurMensuel.objects.filter(site=user.site).select_related("site")[:24]
        sites = SiteTouristique.objects.filter(pk=user.site_id) if user.site_id else []

    # --- Site sélectionné ---
    site_choisi_id = request.GET.get("site_graphique")
    if site_choisi_id:
        site_graphique = sites.filter(pk=site_choisi_id).first() if hasattr(sites, "filter") else None
    else:
        site_graphique = sites.first() if hasattr(sites, "first") else (sites[0] if sites else None)

    # --- Années disponibles ---
    annees_dispo = choix_annees()  # liste de (int, str)

    # --- Années sélectionnées (multi, séparées par virgule) ---
    annees_param = request.GET.get("annees", "")
    if annees_param:
        try:
            annees_selectionnees = [int(a) for a in annees_param.split(",") if a.strip()]
        except ValueError:
            annees_selectionnees = [date.today().year]
    else:
        annees_selectionnees = [date.today().year]

    # Limiter à 5 années max pour lisibilité
    annees_selectionnees = annees_selectionnees[:5]

    labels_mois = ["Jan","Fév","Mars","Avr","Mai","Juin","Juil","Août","Sep","Oct","Nov","Déc"]

    # Palette fixe : chaque année a toujours la même couleur
    # L'index est calculé à partir de l'année, indépendamment de la sélection
    PALETTE = [
        "#03EA68",  # vert vif
        "#F7BB00",  # jaune or
        "#DE0068",  # rose/rouge
        "#0084FA",  # bleu vif
        "#87FF00",  # vert lime
        "#D2D2D2",  # gris clair
        "#FFEA2C",  # jaune citron
    ]
    BASE_YEAR = 2020  # ancre fixe pour le calcul d'index

    datasets = []
    if site_graphique:
        for annee in sorted(annees_selectionnees):
            donnees = [0] * 12
            qs = IndicateurMensuel.objects.filter(site=site_graphique, annee=annee)
            for ind in qs:
                donnees[ind.mois - 1] = ind.frequentation_totale
            couleur = PALETTE[(annee - BASE_YEAR) % len(PALETTE)]
            datasets.append({
                "label": str(annee),
                "data": donnees,
                "color": couleur,
            })

    # Construire la légende couleur → année pour le template
    legende_couleurs = {
        a: PALETTE[(a - BASE_YEAR) % len(PALETTE)]
        for (a, _) in annees_dispo
    }

    return render(request, "suivi/tableau_de_bord.html", {
        "indicateurs": indicateurs,
        "sites": sites,
        "site_graphique": site_graphique,
        "annees_dispo": annees_dispo,
        "annees_selectionnees": annees_selectionnees,
        "annees_param": ",".join(str(a) for a in annees_selectionnees),
        "labels_mois_json": json.dumps(labels_mois),
        "datasets_json": json.dumps([
            {"label": d["label"], "data": d["data"], "color": d["color"]}
            for d in datasets
        ]),
        "legende_couleurs_json": json.dumps(legende_couleurs),
        "annee_courante": annees_selectionnees[0] if annees_selectionnees else date.today().year,
        "annees_disponibles": annees_dispo,
        "donnees_annee_json": json.dumps(datasets[0]["data"] if datasets else [0]*12),
        "donnees_annee_precedente_json": json.dumps(datasets[1]["data"] if len(datasets) > 1 else [0]*12),
    })


# --- Saisie des indicateurs ------------------------------------------------

@login_required
def saisir_indicateur(request, pk=None):
    instance = None
    if pk:
        instance = get_object_or_404(IndicateurMensuel, pk=pk)
        if not request.user.est_admin and instance.site_id != request.user.site_id:
            messages.error(request, "Vous n'êtes pas autorisé à modifier cette saisie.")
            return redirect("tableau_de_bord")

    if request.method == "POST":
        form = IndicateurMensuelForm(request.POST, instance=instance, utilisateur=request.user)
        if form.is_valid():
            indicateur = form.save(commit=False)
            if not request.user.est_admin:
                indicateur.site = request.user.site
            indicateur.saisi_par = request.user
            indicateur.save()
            messages.success(request, "Indicateur enregistré avec succès.")
            return redirect("tableau_de_bord")
    else:
        form = IndicateurMensuelForm(instance=instance, utilisateur=request.user)

    return render(request, "suivi/saisir_indicateur.html", {
        "form": form,
        "instance": instance,
        "form_provenance": [
            ("frequentation_locale",   "Locale (Loire)",                   "locale"),
            ("frequentation_france",   "France (hors fréquentation locale)", "france"),
            ("frequentation_etranger", "Étranger",                          "etranger"),
        ],
    })


@login_required
def liste_indicateurs(request):
    if request.user.est_admin:
        indicateurs = IndicateurMensuel.objects.select_related("site").all()
        site_filtre = request.GET.get("site")
        if site_filtre:
            indicateurs = indicateurs.filter(site_id=site_filtre)
    else:
        indicateurs = IndicateurMensuel.objects.filter(site=request.user.site).select_related("site")

    return render(request, "suivi/liste_indicateurs.html", {
        "indicateurs": indicateurs,
        "sites": SiteTouristique.objects.filter(actif=True) if request.user.est_admin else None,
    })


# --- Événements ------------------------------------------------------------

@login_required
def saisir_evenement(request, pk=None):
    instance = None
    if pk:
        instance = get_object_or_404(Evenement, pk=pk)
        if not request.user.est_admin and instance.site_id != request.user.site_id:
            messages.error(request, "Vous n'êtes pas autorisé à modifier cet événement.")
            return redirect("liste_evenements")

    if request.method == "POST":
        form = EvenementForm(request.POST, instance=instance, utilisateur=request.user)
        if form.is_valid():
            evenement = form.save(commit=False)
            if not request.user.est_admin:
                evenement.site = request.user.site
            evenement.saisi_par = request.user
            evenement.save()
            messages.success(request, "Événement enregistré avec succès.")
            return redirect("liste_evenements")
    else:
        form = EvenementForm(instance=instance, utilisateur=request.user)

    return render(request, "suivi/saisir_evenement.html", {"form": form, "instance": instance})


@login_required
def liste_evenements(request):
    if request.user.est_admin:
        evenements = Evenement.objects.select_related("site").all()
    else:
        evenements = Evenement.objects.filter(site=request.user.site).select_related("site")
    return render(request, "suivi/liste_evenements.html", {"evenements": evenements})


@login_required
def export_csv(request):
    if request.user.est_admin:
        indicateurs = IndicateurMensuel.objects.select_related("site").all()
    else:
        indicateurs = IndicateurMensuel.objects.filter(site=request.user.site).select_related("site")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="indicateurs_frequentation.csv"'
    response.write("\ufeff")  # BOM pour Excel
    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Site", "Année", "Mois", "Fréquentation totale",
        "Fréquentation locale", "Fréquentation France", "Fréquentation étranger",
        "Fréquentation gratuite", "Fréquentation payante",
        "Jours d'ouverture", "Saisi par", "Date de saisie",
    ])
    for ind in indicateurs:
        writer.writerow([
            ind.site.nom, ind.annee, ind.get_mois_display(),
            ind.frequentation_totale, ind.frequentation_locale,
            ind.frequentation_france, ind.frequentation_etranger,
            ind.frequentation_gratuite, ind.frequentation_payante,
            ind.nb_jours_ouverture,
            ind.saisi_par.get_full_name() if ind.saisi_par else "",
            ind.date_saisie.strftime("%d/%m/%Y %H:%M"),
        ])
    return response


# ── Export/Import Excel ─────────────────────────────────────────────────────

@user_passes_test(est_admin)
def portail_import_export(request):
    """Page centrale du module import/export."""
    nb_indicateurs = IndicateurMensuel.objects.count()
    nb_evenements  = Evenement.objects.count()
    return render(request, "suivi/import_export.html", {
        "nb_indicateurs": nb_indicateurs,
        "nb_evenements":  nb_evenements,
        "sites":  SiteTouristique.objects.filter(actif=True),
        "annees": choix_annees(),
    })


@user_passes_test(est_admin)
def export_excel_indicateurs(request):
    qs = IndicateurMensuel.objects.select_related("site", "saisi_par").all()
    site_id = request.GET.get("site")
    annee   = request.GET.get("annee")
    if site_id:
        qs = qs.filter(site_id=site_id)
    if annee:
        qs = qs.filter(annee=annee)

    buf = io_excel.export_indicateurs_excel(qs)
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="indicateurs_frequentation.xlsx"'
    return response


@user_passes_test(est_admin)
def export_excel_indicateurs_unique(request):
    """Export onglet unique tous sites."""
    qs = IndicateurMensuel.objects.select_related("site", "saisi_par").all()
    site_id = request.GET.get("site")
    annee   = request.GET.get("annee")
    if site_id:
        qs = qs.filter(site_id=site_id)
    if annee:
        qs = qs.filter(annee=annee)

    buf = io_excel.export_indicateurs_excel_unique(qs)
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="indicateurs_tous_sites.xlsx"'
    return response


@user_passes_test(est_admin)
def export_excel_evenements(request):
    qs = Evenement.objects.select_related("site", "saisi_par").all()
    buf = io_excel.export_evenements_excel(qs)
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="evenements.xlsx"'
    return response


@user_passes_test(est_admin)
def telecharger_template_import(request):
    buf = io_excel.generer_template_import()
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="template_import_indicateurs.xlsx"'
    return response


@user_passes_test(est_admin)
def importer_indicateurs(request):
    if request.method != "POST":
        return redirect("portail_import_export")

    fichier = request.FILES.get("fichier")
    if not fichier:
        messages.error(request, "Aucun fichier sélectionné.")
        return redirect("portail_import_export")

    # Extension autorisée
    ext = fichier.name.rsplit(".", 1)[-1].lower()
    if ext not in ("xlsx", "csv"):
        messages.error(request, "Format non accepté. Utilisez un fichier .xlsx ou .csv.")
        return redirect("portail_import_export")

    dry_run = "simulation" in request.POST

    try:
        resultat = io_excel.importer_indicateurs(fichier, request.user, dry_run=dry_run)
    except io_excel.ImportError as e:
        messages.error(request, f"Erreur de lecture du fichier : {e}")
        return redirect("portail_import_export")
    except Exception as e:
        messages.error(request, f"Erreur inattendue : {e}")
        return redirect("portail_import_export")

    return render(request, "suivi/import_resultat.html", {
        "resultat": resultat,
        "fichier_nom": fichier.name,
    })
    return response


# --- Administration : sites ------------------------------------------------

@user_passes_test(est_admin)
def liste_sites(request):
    sites = SiteTouristique.objects.all()
    return render(request, "suivi/liste_sites.html", {"sites": sites})


@user_passes_test(est_admin)
def creer_site(request):
    if request.method == "POST":
        form = SiteTouristiqueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Site créé avec succès.")
            return redirect("liste_sites")
    else:
        form = SiteTouristiqueForm()
    return render(request, "suivi/formulaire_site.html", {"form": form})


@user_passes_test(est_admin)
def modifier_site(request, pk):
    site = get_object_or_404(SiteTouristique, pk=pk)
    if request.method == "POST":
        form = SiteTouristiqueForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, "Site mis à jour.")
            return redirect("liste_sites")
    else:
        form = SiteTouristiqueForm(instance=site)
    return render(request, "suivi/formulaire_site.html", {"form": form, "site": site})


# --- Administration : utilisateurs -----------------------------------------

@user_passes_test(est_admin)
def liste_utilisateurs(request):
    utilisateurs = Utilisateur.objects.select_related("site").all()
    return render(request, "suivi/liste_utilisateurs.html", {"utilisateurs": utilisateurs})


@user_passes_test(est_admin)
def creer_utilisateur(request):
    if request.method == "POST":
        form = UtilisateurCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Utilisateur créé avec succès.")
            return redirect("liste_utilisateurs")
    else:
        form = UtilisateurCreationForm()
    return render(request, "suivi/formulaire_utilisateur.html", {"form": form})


# --- Offices de tourisme ---------------------------------------------------

@user_passes_test(est_admin)
def liste_offices(request):
    offices = OfficeDeTourisme.objects.prefetch_related("sites").all()
    return render(request, "suivi/liste_offices.html", {"offices": offices})


@user_passes_test(est_admin)
def creer_office(request):
    if request.method == "POST":
        form = OfficeDeTourismeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Office de tourisme créé.")
            return redirect("liste_offices")
    else:
        form = OfficeDeTourismeForm()
    return render(request, "suivi/formulaire_office.html", {"form": form})


@user_passes_test(est_admin)
def modifier_office(request, pk):
    office = get_object_or_404(OfficeDeTourisme, pk=pk)
    if request.method == "POST":
        form = OfficeDeTourismeForm(request.POST, instance=office)
        if form.is_valid():
            form.save()
            messages.success(request, "Office de tourisme mis à jour.")
            return redirect("liste_offices")
    else:
        form = OfficeDeTourismeForm(instance=office)
    return render(request, "suivi/formulaire_office.html", {"form": form, "office": office})


@user_passes_test(est_admin)
def generer_cle_api(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    cle = utilisateur.generer_cle_api()
    messages.success(
        request,
        f"Nouvelle clé API générée pour {utilisateur}. "
        f"Copiez-la maintenant, elle ne sera plus réaffichée en clair : {cle}",
    )
    return redirect("liste_utilisateurs")


# --- API JSON (lecture seule, pour Power BI ou autres outils externes) -----

def _authentifier_cle_api(request):
    """Authentifie une requête API via le header X-API-Key ou le paramètre ?cle="""
    cle = request.headers.get("X-API-Key") or request.GET.get("cle")
    if not cle:
        return None
    return Utilisateur.objects.filter(cle_api=cle, is_active=True).first()


@csrf_exempt
@require_GET
def api_indicateurs(request):
    """
    Endpoint JSON en lecture seule.
    Authentification : header 'X-API-Key: <clé>' ou paramètre '?cle=<clé>'.
    Filtres optionnels : ?annee=2026 / ?mois=6 / ?site=<id>
    """
    utilisateur = _authentifier_cle_api(request)
    if not utilisateur:
        return JsonResponse({"erreur": "Clé API manquante ou invalide."}, status=401)

    if utilisateur.est_admin:
        qs = IndicateurMensuel.objects.select_related("site").all()
    else:
        qs = IndicateurMensuel.objects.select_related("site").filter(site=utilisateur.site)

    annee = request.GET.get("annee")
    mois = request.GET.get("mois")
    site_id = request.GET.get("site")
    if annee:
        qs = qs.filter(annee=annee)
    if mois:
        qs = qs.filter(mois=mois)
    if site_id:
        qs = qs.filter(site_id=site_id)

    data = [
        {
            "site_id": ind.site_id,
            "site": ind.site.nom,
            "commune": ind.site.commune,
            "annee": ind.annee,
            "mois": ind.mois,
            "mois_libelle": ind.get_mois_display(),
            "frequentation_totale": ind.frequentation_totale,
            "frequentation_locale": ind.frequentation_locale,
            "frequentation_france": ind.frequentation_france,
            "frequentation_etranger": ind.frequentation_etranger,
            "frequentation_gratuite": ind.frequentation_gratuite,
            "frequentation_payante": ind.frequentation_payante,
            "nb_jours_ouverture": ind.nb_jours_ouverture,
            "date_modification": ind.date_modification.isoformat(),
        }
        for ind in qs.order_by("annee", "mois", "site__nom")
    ]
    return JsonResponse({"resultats": data, "total": len(data)}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_GET
def api_sites(request):
    """Liste des sites touristiques, en lecture seule, même authentification que api_indicateurs."""
    utilisateur = _authentifier_cle_api(request)
    if not utilisateur:
        return JsonResponse({"erreur": "Clé API manquante ou invalide."}, status=401)

    sites = SiteTouristique.objects.filter(actif=True)
    if not utilisateur.est_admin:
        sites = sites.filter(pk=utilisateur.site_id)

    data = [
        {"id": s.pk, "nom": s.nom, "commune": s.commune, "categorie": s.categorie}
        for s in sites
    ]
    return JsonResponse({"resultats": data}, json_dumps_params={"ensure_ascii": False})


@login_required
def aide(request):
    termes_lexique = [
        {"nom": "Fréquentation totale", "anglais": "Total attendance", "definition": "Nombre total de visiteurs ayant accédé au site sur la période concernée, toutes catégories confondues. C'est l'indicateur de référence à partir duquel sont calculées toutes les répartitions.", "exemple": "Un musée accueille 800 scolaires, 150 individuels et 50 groupes adultes en juin → fréquentation totale : 1 000."},
        {"nom": "Fréquentation locale (Loire)", "anglais": None, "definition": "Visiteurs résidant dans le bassin de vie immédiat du site, principalement le département de la Loire (42) et les communes limitrophes des départements voisins. Reflète l'ancrage territorial du site auprès des habitants de proximité.", "exemple": "Habitants de Saint-Étienne, Firminy, Roanne, Montbrison venant visiter un site stéphanois."},
        {"nom": "Fréquentation France (hors local)", "anglais": "Domestic visitors", "definition": "Visiteurs en provenance de France métropolitaine ou des DOM-TOM, à l'exclusion du bassin local. Mesure le rayonnement national du site et son attractivité touristique hors département.", "exemple": "Un groupe de Parisiens en visite à la Cité Le Corbusier, ou des touristes lyonnais en week-end."},
        {"nom": "Fréquentation étrangère", "anglais": "International visitors", "definition": "Visiteurs dont la résidence principale est située hors de France. Inclut les touristes internationaux, expatriés et groupes organisés étrangers. Indicateur clé de la notoriété internationale du site.", "exemple": "Visiteurs italiens, allemands ou japonais découvrant le patrimoine ligérien."},
        {"nom": "Fréquentation gratuite", "anglais": "Free admissions", "definition": "Entrées n'ayant donné lieu à aucun paiement. Comprend les journées portes ouvertes, les ayants droit (carte musée, adhérents), les enfants en bas âge, les professionnels du tourisme et les invités.", "exemple": "Lors des Journées du Patrimoine, toutes les entrées sont gratuites."},
        {"nom": "Fréquentation payante", "anglais": "Paid admissions", "definition": "Entrées ayant donné lieu au paiement d'un droit d'accès, quel que soit le tarif (plein, réduit, groupe, billet combiné). C'est le principal indicateur des recettes billetterie.", "exemple": "Adulte plein tarif à 8 €, tarif réduit à 5 €, tarif groupe à 4 €/personne."},
        {"nom": "Jours d'ouverture", "anglais": "Opening days", "definition": "Nombre de jours calendaires durant lesquels le site a accueilli du public au cours du mois. Permet de calculer la fréquentation journalière moyenne et d'analyser les pics de fréquentation.", "exemple": "Un musée ouvert tous les jours sauf le lundi compte 26 jours d'ouverture en juin."},
        {"nom": "Taux de fréquentation journalière", "anglais": "Daily attendance rate", "definition": "Fréquentation totale divisée par le nombre de jours d'ouverture. Indicateur de performance opérationnelle permettant de comparer des sites aux horaires différents.", "exemple": "1 000 visiteurs / 26 jours = 38,5 visiteurs/jour en moyenne."},
        {"nom": "Taux de gratuité", "anglais": "Free admission rate", "definition": "Part de la fréquentation gratuite dans la fréquentation totale (gratuit ÷ total). Reflète la politique d'accessibilité et d'ouverture sociale du site. Un taux élevé peut signifier une politique délibérée ou des périodes d'ouverture libre.", "exemple": "300 gratuits / 1 000 total = taux de gratuité de 30 %."},
        {"nom": "Taux de provenance locale", "anglais": "Local catchment rate", "definition": "Part des visiteurs locaux dans la fréquentation totale. Un taux élevé indique un fort ancrage territorial mais une dépendance au bassin local ; un taux faible traduit une attractivité touristique plus large.", "exemple": "200 locaux / 1 000 total = 20 % de fréquentation locale."},
        {"nom": "Office de tourisme", "anglais": "Tourist office", "definition": "Structure chargée de la promotion touristique d'un territoire. Dans cette plateforme, chaque site est rattaché à un ou plusieurs offices de tourisme correspondant à sa zone géographique de compétence.", "exemple": "Saint-Étienne Métropole, Loire Forez Agglomération, Office du Pilat…"},
        {"nom": "Événement", "anglais": "Event", "definition": "Manifestation ponctuelle organisée sur un site (exposition temporaire, festival, journée thématique, inauguration). Les événements font l'objet d'une saisie distincte des indicateurs mensuels et permettent d'analyser l'impact des actions de programmation.", "exemple": "Nuit des musées, Journées du Patrimoine, exposition itinérante."},
        {"nom": "Indicateur N-1", "anglais": "Year-over-year", "definition": "Valeur du même indicateur pour la même période de l'année précédente. La comparaison N / N-1 est la référence principale pour évaluer l'évolution de la fréquentation en neutralisant les effets saisonniers.", "exemple": "Juin 2026 vs juin 2025 : +12 % de fréquentation."},
        {"nom": "Saisisseur", "anglais": None, "definition": "Rôle attribué aux responsables de sites. Un saisisseur ne peut saisir et consulter que les données de son propre site. Il n'a pas accès aux données des autres sites ni aux fonctions d'administration.", "exemple": None},
        {"nom": "Administrateur", "anglais": None, "definition": "Rôle attribué à l'équipe OTSE. L'administrateur peut consulter et modifier toutes les données, gérer les sites, les offices de tourisme et les utilisateurs, accéder aux fonctions d'import/export et générer des clés API.", "exemple": None},
        {"nom": "Clé API", "anglais": "API key", "definition": "Jeton d'authentification permettant à des outils externes (Power BI, tableurs, scripts) d'interroger les données de la plateforme via une URL sécurisée, sans avoir à se connecter via l'interface web.", "exemple": "https://indicateurs.example.fr/api/indicateurs/?cle=abc123&annee=2026"},
    ]

    faqs = [
        {"question": "Je me suis trompé dans ma saisie du mois dernier, puis-je la corriger ?", "reponse": "Oui. Allez dans Historique, trouvez la ligne concernée et cliquez sur Modifier. Vous pouvez corriger tous les champs. La date de modification est enregistrée automatiquement pour la traçabilité."},
        {"question": "Que faire si mon site était fermé tout le mois ?", "reponse": "Saisissez quand même un indicateur avec fréquentation totale = 0 et jours d'ouverture = 0. Cela confirme que la saisie a bien été effectuée et distingue une fermeture volontaire d'un oubli de saisie."},
        {"question": "La somme locale + France + étranger doit-elle obligatoirement être égale au total ?", "reponse": "Non, elle peut être inférieure au total. Il arrive qu'une partie des visiteurs ne soit pas identifiée géographiquement (billetterie sans enquête, visites rapides). La contrainte est uniquement que la somme ne dépasse pas le total."},
        {"question": "Je reçois des rappels email mais j'ai déjà saisi. Pourquoi ?", "reponse": "Les rappels sont envoyés le 5 de chaque mois pour la période précédente. Si vous avez saisi après l'envoi du rappel, vous pouvez l'ignorer. Si vous avez saisi avant et que vous recevez quand même un rappel, contactez l'administrateur — il peut y avoir un décalage dans la base de données."},
        {"question": "Puis-je saisir des données pour une année antérieure ?", "reponse": "Oui. Le menu déroulant des années propose les 5 dernières années. Pour des données plus anciennes, contactez l'administrateur qui peut effectuer un import en masse via le module Import/Export."},
        {"question": "Comment connecter Power BI à la plateforme ?", "reponse": "Dans Power BI Desktop, cliquez sur Obtenir des données → Web → Avancé. Entrez l'URL /api/indicateurs/ et ajoutez le header HTTP X-API-Key avec votre clé. Votre clé API se génère depuis la page Utilisateurs (admin). Voir la section API & Export ci-dessus pour les détails."},
        {"question": "La fréquentation d'un événement doit-elle être incluse dans la saisie mensuelle ?", "reponse": "Cela dépend de votre mode de comptage. Si votre billetterie ou registre de visites comptabilise déjà l'événement dans vos totaux mensuels, incluez-le dans la saisie mensuelle et créez en plus la fiche événement. Si vous comptez séparément, saisissez l'événement seul. L'important est d'être cohérent et de ne pas compter deux fois."},
    ]

    return render(request, "suivi/aide.html", {
        "termes_lexique": termes_lexique,
        "faqs": faqs,
    })


@login_required
def a_propos(request):
    stack = [
        {"icone": "🐍", "nom": "Python / Django 5+", "detail": "Framework backend, ORM, authentification"},
        {"icone": "🗃️", "nom": "SQLite / PostgreSQL", "detail": "Base de données relationnelle"},
        {"icone": "📊", "nom": "Chart.js 4", "detail": "Graphiques interactifs multi-années"},
        {"icone": "⚡", "nom": "Alpine.js 3", "detail": "Réactivité côté client, validation temps réel"},
        {"icone": "📅", "nom": "Flatpickr", "detail": "Sélecteur de dates localisé"},
        {"icone": "📦", "nom": "openpyxl", "detail": "Export Excel formaté aux couleurs OTSE"},
        {"icone": "🔔", "nom": "Toastify.js", "detail": "Notifications toast élégantes"},
        {"icone": "🎨", "nom": "Bootstrap 5 + Inter", "detail": "UI responsive, typographie éditoriale"},
    ]
    offices = OfficeDeTourisme.objects.filter(actif=True)
    return render(request, "suivi/a_propos.html", {"stack": stack, "offices": offices})
