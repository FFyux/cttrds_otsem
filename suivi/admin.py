from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, SiteTouristique, IndicateurMensuel, Evenement, OfficeDeTourisme


@admin.register(OfficeDeTourisme)
class OfficeDeTourismeAdmin(admin.ModelAdmin):
    list_display = ("nom", "actif")


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "site", "role", "is_active")
    list_filter = ("role", "site", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Informations spécifiques", {"fields": ("site", "role", "telephone", "cle_api")}),
    )


@admin.register(SiteTouristique)
class SiteTouristiqueAdmin(admin.ModelAdmin):
    list_display = ("nom", "commune", "categorie", "actif")
    list_filter = ("actif", "categorie")
    filter_horizontal = ("offices",)


@admin.register(IndicateurMensuel)
class IndicateurMensuelAdmin(admin.ModelAdmin):
    list_display = ("site", "annee", "mois", "frequentation_totale", "nb_jours_ouverture", "saisi_par")
    list_filter = ("annee", "site")


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = ("nom", "site", "date_debut", "date_fin", "frequentation")
    list_filter = ("site",)
