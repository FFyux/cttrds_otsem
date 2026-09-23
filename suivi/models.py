import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class OfficeDeTourisme(models.Model):
    """Office de tourisme pouvant être rattaché à un ou plusieurs sites."""

    nom = models.CharField("Nom", max_length=200)
    actif = models.BooleanField("Actif", default=True)

    class Meta:
        verbose_name = "Office de tourisme"
        verbose_name_plural = "Offices de tourisme"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class SiteTouristique(models.Model):
    """Un site touristique (musée, office de tourisme, monument, etc.)"""

    CATEGORIE_CHOICES = [
        ("musee", "Musée"),
        ("site_patrimonial", "Site patrimonial"),
        ("office_tourisme", "Office de tourisme"),
        ("parc_jardin", "Parc / jardin"),
        ("monument", "Monument"),
        ("site_naturel", "Site naturel"),
        ("art_contemporain", "Lieu d'art contemporain"),
        ("autre", "Autre"),
    ]

    nom = models.CharField("Nom du site", max_length=200)
    commune = models.CharField("Commune", max_length=150, blank=True)
    categorie = models.CharField(
        "Catégorie",
        max_length=30,
        choices=CATEGORIE_CHOICES,
        blank=True,
    )
    offices = models.ManyToManyField(
        OfficeDeTourisme,
        blank=True,
        verbose_name="Offices de tourisme rattachés",
        related_name="sites",
    )
    actif = models.BooleanField("Site actif", default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Site touristique"
        verbose_name_plural = "Sites touristiques"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Utilisateur(AbstractUser):
    """Utilisateur de la plateforme, rattaché à un site touristique."""

    ROLE_CHOICES = [
        ("saisisseur", "Saisisseur (site)"),
        ("admin", "Administrateur"),
    ]

    site = models.ForeignKey(
        SiteTouristique,
        verbose_name="Site rattaché",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="utilisateurs",
    )
    role = models.CharField(
        "Rôle", max_length=20, choices=ROLE_CHOICES, default="saisisseur"
    )
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    cle_api = models.CharField(
        "Clé API", max_length=64, blank=True, unique=True, null=True,
        help_text="Utilisée pour l'accès en lecture à l'API (ex: Power BI). Laisser vide si non utilisée.",
    )

    def save(self, *args, **kwargs):
        if not self.cle_api:
            self.cle_api = None  # évite les conflits d'unicité sur chaîne vide
        super().save(*args, **kwargs)

    def generer_cle_api(self):
        self.cle_api = secrets.token_hex(32)
        self.save(update_fields=["cle_api"])
        return self.cle_api

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def est_admin(self):
        return self.role == "admin" or self.is_superuser


class IndicateurMensuel(models.Model):
    """Saisie de fréquentation d'un site pour un mois donné."""

    MOIS_CHOICES = [
        (1, "Janvier"), (2, "Février"), (3, "Mars"), (4, "Avril"),
        (5, "Mai"), (6, "Juin"), (7, "Juillet"), (8, "Août"),
        (9, "Septembre"), (10, "Octobre"), (11, "Novembre"), (12, "Décembre"),
    ]

    site = models.ForeignKey(
        SiteTouristique, on_delete=models.CASCADE, related_name="indicateurs"
    )
    annee = models.PositiveIntegerField(
        "Année", validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    mois = models.PositiveSmallIntegerField("Mois", choices=MOIS_CHOICES)

    frequentation_totale = models.PositiveIntegerField(
        "Fréquentation totale", default=0
    )
    frequentation_locale = models.PositiveIntegerField(
        "Fréquentation locale", default=0,
        help_text="Visiteurs résidant dans le bassin local",
    )
    frequentation_france = models.PositiveIntegerField(
        "Fréquentation France (hors local)", default=0
    )
    frequentation_etranger = models.PositiveIntegerField(
        "Fréquentation étranger", default=0
    )
    frequentation_gratuite = models.PositiveIntegerField(
        "Fréquentation gratuite", default=0
    )
    frequentation_payante = models.PositiveIntegerField(
        "Fréquentation payante", default=0
    )

    nb_jours_ouverture = models.PositiveSmallIntegerField(
        "Nombre de jours d'ouverture",
        validators=[MaxValueValidator(31)],
    )

    saisi_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, related_name="saisies"
    )
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    commentaire = models.TextField("Commentaire", blank=True)

    class Meta:
        verbose_name = "Indicateur mensuel"
        verbose_name_plural = "Indicateurs mensuels"
        unique_together = ("site", "annee", "mois")
        ordering = ["-annee", "-mois", "site__nom"]

    def __str__(self):
        return f"{self.site.nom} - {self.get_mois_display()} {self.annee}"

    def clean(self):
        total_provenance = (
            (self.frequentation_locale or 0)
            + (self.frequentation_france or 0)
            + (self.frequentation_etranger or 0)
        )
        if total_provenance and self.frequentation_totale and total_provenance > self.frequentation_totale:
            raise ValidationError(
                "La somme des fréquentations par provenance "
                f"({total_provenance}) dépasse la fréquentation totale "
                f"déclarée ({self.frequentation_totale})."
            )

        total_tarif = (self.frequentation_gratuite or 0) + (self.frequentation_payante or 0)
        if total_tarif and self.frequentation_totale and total_tarif > self.frequentation_totale:
            raise ValidationError(
                "La somme des fréquentations gratuite et payante "
                f"({total_tarif}) dépasse la fréquentation totale "
                f"déclarée ({self.frequentation_totale})."
            )


class Evenement(models.Model):
    """Fréquentation liée à un événement ponctuel sur un site (exposition, festival, etc.)"""

    site = models.ForeignKey(
        SiteTouristique, on_delete=models.CASCADE, related_name="evenements"
    )
    nom = models.CharField("Nom de l'événement", max_length=200)
    date_debut = models.DateField("Date de début")
    date_fin = models.DateField("Date de fin")
    frequentation = models.PositiveIntegerField("Fréquentation totale de l'événement", default=0)

    saisi_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, related_name="evenements_saisis"
    )
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    commentaire = models.TextField("Commentaire", blank=True)

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.nom} ({self.site.nom})"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError("La date de fin ne peut pas être antérieure à la date de début.")
