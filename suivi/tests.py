from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .forms import IndicateurMensuelForm
from .models import Evenement, IndicateurMensuel, SiteTouristique, Utilisateur


class ConfigurationSmokeTests(SimpleTestCase):
    def test_secret_key_is_configured(self):
        self.assertTrue(settings.SECRET_KEY)

    def test_secret_key_is_not_the_old_default(self):
        self.assertFalse(settings.SECRET_KEY.startswith("django-insecure"))


class IndicateurMensuelModelTests(TestCase):
    def setUp(self):
        self.site = SiteTouristique.objects.create(
            nom="Musée de test",
            commune="Saint-Étienne",
            categorie="musee",
        )
        self.utilisateur = Utilisateur.objects.create_user(
    username="test_indicateur",
    password="MotDePasseTest123!",
    site=self.site,
    role="saisisseur",
)

    def creer_indicateur(self, **kwargs):
        valeurs = {
            "site": self.site,
            "annee": 2026,
            "mois": 1,
            "frequentation_totale": 100,
            "frequentation_locale": 30,
            "frequentation_france": 50,
            "frequentation_etranger": 20,
            "frequentation_gratuite": 40,
            "frequentation_payante": 60,
            "nb_jours_ouverture": 20,
            "saisi_par": self.utilisateur,
        }
        valeurs.update(kwargs)
        return IndicateurMensuel(**valeurs)

    def test_indicateur_valide(self):
        indicateur = self.creer_indicateur()
        indicateur.full_clean()

    def test_provenance_ne_peut_pas_depasser_le_total(self):
        indicateur = self.creer_indicateur(
            frequentation_totale=10,
            frequentation_locale=6,
            frequentation_france=3,
            frequentation_etranger=2,
        )

        with self.assertRaises(ValidationError):
            indicateur.full_clean()

    def test_gratuit_plus_payant_ne_peut_pas_depasser_le_total(self):
        indicateur = self.creer_indicateur(
            frequentation_totale=10,
            frequentation_gratuite=6,
            frequentation_payante=5,
        )

        with self.assertRaises(ValidationError):
            indicateur.full_clean()

    def test_un_seul_indicateur_par_site_mois_et_annee(self):
        premier = self.creer_indicateur()
        premier.save()

        doublon = self.creer_indicateur()

        with self.assertRaises(ValidationError):
            doublon.full_clean()


class EvenementModelTests(TestCase):
    def setUp(self):
        self.site = SiteTouristique.objects.create(
            nom="Site événement",
            commune="Saint-Étienne",
            categorie="site_patrimonial",
        )
        self.utilisateur = Utilisateur.objects.create_user(
            username="test_evenement",
            password="MotDePasseTest123!",
            site=self.site,
            role="saisisseur",
        )

    def test_date_de_fin_apres_date_de_debut(self):
        evenement = Evenement(
            site=self.site,
            nom="Événement valide",
            date_debut=date(2026, 6, 10),
            date_fin=date(2026, 6, 12),
            frequentation=100,
            saisi_par=self.utilisateur,
        )

        evenement.full_clean()

    def test_date_de_fin_avant_date_de_debut(self):
        evenement = Evenement(
            site=self.site,
            nom="Événement invalide",
            date_debut=date(2026, 6, 12),
            date_fin=date(2026, 6, 10),
            frequentation=100,
            saisi_par=self.utilisateur,
        )

        with self.assertRaises(ValidationError):
            evenement.full_clean()


class FormulaireIndicateurTests(TestCase):
    def setUp(self):
        self.site = SiteTouristique.objects.create(
            nom="Site formulaire",
            commune="Saint-Étienne",
            categorie="musee",
        )
        self.autre_site = SiteTouristique.objects.create(
            nom="Autre site",
            commune="Firminy",
            categorie="monument",
        )
        self.utilisateur = Utilisateur.objects.create_user(
            username="saisisseur_test",
            password="MotDePasseTest123!",
            site=self.site,
            role="saisisseur",
        )

    def test_un_saisisseur_ne_voit_que_son_site(self):
        formulaire = IndicateurMensuelForm(utilisateur=self.utilisateur)

        self.assertTrue(formulaire.fields["site"].disabled)
        self.assertEqual(
            list(formulaire.fields["site"].queryset),
            [self.site],
        )

    def test_formulaire_refuse_une_provenance_trop_elevee(self):
        formulaire = IndicateurMensuelForm(
            data={
                "site": self.site.pk,
                "annee": 2026,
                "mois": 1,
                "frequentation_totale": 10,
                "frequentation_locale": 6,
                "frequentation_france": 3,
                "frequentation_etranger": 2,
                "frequentation_gratuite": 0,
                "frequentation_payante": 0,
                "nb_jours_ouverture": 1,
            },
            utilisateur=self.utilisateur,
        )

        self.assertFalse(formulaire.is_valid())
        self.assertIn(
            "fréquentation totale",
            formulaire.non_field_errors()[0],
        )


class AccesEtApiTests(TestCase):
    def setUp(self):
        self.site = SiteTouristique.objects.create(
            nom="Site API",
            commune="Saint-Étienne",
            categorie="musee",
        )
        self.autre_site = SiteTouristique.objects.create(
            nom="Autre site API",
            commune="Firminy",
            categorie="monument",
        )
        self.utilisateur = Utilisateur.objects.create_user(
            username="api_test",
            password="MotDePasseTest123!",
            site=self.site,
            role="saisisseur",
            cle_api="cle-api-test",
        )

        IndicateurMensuel.objects.create(
            site=self.site,
            annee=2026,
            mois=1,
            frequentation_totale=100,
            frequentation_locale=30,
            frequentation_france=50,
            frequentation_etranger=20,
            frequentation_gratuite=40,
            frequentation_payante=60,
            nb_jours_ouverture=20,
        )
        IndicateurMensuel.objects.create(
            site=self.autre_site,
            annee=2026,
            mois=1,
            frequentation_totale=200,
            frequentation_locale=50,
            frequentation_france=100,
            frequentation_etranger=50,
            frequentation_gratuite=80,
            frequentation_payante=120,
            nb_jours_ouverture=20,
        )

    def test_tableau_de_bord_demande_une_connexion(self):
        response = self.client.get(reverse("tableau_de_bord"))

        self.assertEqual(response.status_code, 302)

    def test_api_refuse_une_cle_absente(self):
        response = self.client.get(reverse("api_indicateurs"))

        self.assertEqual(response.status_code, 401)

    def test_api_limite_les_resultats_au_site_de_l_utilisateur(self):
        response = self.client.get(
            reverse("api_indicateurs"),
            HTTP_X_API_KEY="cle-api-test",
        )

        self.assertEqual(response.status_code, 200)
        contenu = response.json()

        self.assertEqual(contenu["total"], 1)
        self.assertEqual(
            contenu["resultats"][0]["site_id"],
            self.site.pk,
        )