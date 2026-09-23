from django.urls import path
from . import views

urlpatterns = [
    path("", views.tableau_de_bord, name="tableau_de_bord"),

    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),

    path("mot-de-passe/reinitialiser/", views.ReinitMotDePasseView.as_view(), name="reinit_mdp"),
    path("mot-de-passe/envoye/", views.ReinitMotDePasseEnvoyeView.as_view(), name="reinit_mdp_envoye"),
    path("mot-de-passe/confirmer/<uidb64>/<token>/", views.ReinitMotDePasseConfirmView.as_view(), name="reinit_mdp_confirm"),
    path("mot-de-passe/termine/", views.ReinitMotDePasseTermineView.as_view(), name="reinit_mdp_termine"),

    path("saisir/", views.saisir_indicateur, name="saisir_indicateur"),
    path("saisir/<int:pk>/", views.saisir_indicateur, name="modifier_indicateur"),
    path("indicateurs/", views.liste_indicateurs, name="liste_indicateurs"),
    path("indicateurs/export/", views.export_csv, name="export_csv"),

    path("import-export/", views.portail_import_export, name="portail_import_export"),
    path("import-export/export-excel/", views.export_excel_indicateurs, name="export_excel_indicateurs"),
    path("import-export/export-excel-unique/", views.export_excel_indicateurs_unique, name="export_excel_indicateurs_unique"),
    path("import-export/export-evenements/", views.export_excel_evenements, name="export_excel_evenements"),
    path("import-export/template/", views.telecharger_template_import, name="telecharger_template_import"),
    path("import-export/importer/", views.importer_indicateurs, name="importer_indicateurs"),

    path("evenements/", views.liste_evenements, name="liste_evenements"),
    path("evenements/nouveau/", views.saisir_evenement, name="saisir_evenement"),
    path("evenements/<int:pk>/", views.saisir_evenement, name="modifier_evenement"),

    path("sites/", views.liste_sites, name="liste_sites"),
    path("sites/nouveau/", views.creer_site, name="creer_site"),
    path("sites/<int:pk>/modifier/", views.modifier_site, name="modifier_site"),

    path("utilisateurs/", views.liste_utilisateurs, name="liste_utilisateurs"),
    path("utilisateurs/nouveau/", views.creer_utilisateur, name="creer_utilisateur"),
    path("utilisateurs/<int:pk>/cle-api/", views.generer_cle_api, name="generer_cle_api"),

    path("offices/", views.liste_offices, name="liste_offices"),
    path("offices/nouveau/", views.creer_office, name="creer_office"),
    path("offices/<int:pk>/modifier/", views.modifier_office, name="modifier_office"),

    path("api/indicateurs/", views.api_indicateurs, name="api_indicateurs"),
    path("api/sites/", views.api_sites, name="api_sites"),

    path("aide/", views.aide, name="aide"),
    path("a-propos/", views.a_propos, name="a_propos"),
]
