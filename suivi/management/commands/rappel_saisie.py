"""
Commande de rappel automatique par email.

Envoie un email aux utilisateurs dont le site n'a pas encore saisi ses
indicateurs pour le mois cible (par défaut : le mois précédent).

Usage :
    python manage.py rappel_saisie
    python manage.py rappel_saisie --annee 2026 --mois 6
    python manage.py rappel_saisie --resume-admin

À planifier en tâche périodique (cron / tâche planifiée PythonAnywhere),
par exemple le 5 de chaque mois pour rappeler la saisie du mois précédent.
"""
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from suivi.models import SiteTouristique, IndicateurMensuel, Utilisateur


def mois_precedent(aujourdhui=None):
    aujourdhui = aujourdhui or date.today()
    if aujourdhui.month == 1:
        return aujourdhui.year - 1, 12
    return aujourdhui.year, aujourdhui.month - 1


NOMS_MOIS = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


class Command(BaseCommand):
    help = "Envoie un rappel par email aux sites n'ayant pas saisi leurs indicateurs pour le mois cible."

    def add_arguments(self, parser):
        parser.add_argument("--annee", type=int, help="Année cible (par défaut : mois précédent)")
        parser.add_argument("--mois", type=int, help="Mois cible 1-12 (par défaut : mois précédent)")
        parser.add_argument(
            "--resume-admin", action="store_true",
            help="Envoie aussi un email récapitulatif aux administrateurs",
        )
        parser.add_argument(
            "--simulation", action="store_true",
            help="N'envoie aucun email, affiche seulement ce qui serait fait",
        )

    def handle(self, *args, **options):
        if options.get("annee") and options.get("mois"):
            annee, mois = options["annee"], options["mois"]
        else:
            annee, mois = mois_precedent()

        libelle_periode = f"{NOMS_MOIS.get(mois, mois)} {annee}"

        sites_actifs = SiteTouristique.objects.filter(actif=True)
        sites_saisis_ids = set(
            IndicateurMensuel.objects.filter(annee=annee, mois=mois).values_list("site_id", flat=True)
        )
        sites_manquants = [s for s in sites_actifs if s.pk not in sites_saisis_ids]

        if not sites_manquants:
            self.stdout.write(self.style.SUCCESS(
                f"Tous les sites actifs ont saisi leurs indicateurs pour {libelle_periode}."
            ))
            return

        nb_emails_envoyes = 0
        for site in sites_manquants:
            destinataires = Utilisateur.objects.filter(
                site=site, is_active=True, role="saisisseur"
            ).exclude(email="")
            emails = [u.email for u in destinataires]
            if not emails:
                self.stdout.write(self.style.WARNING(
                    f"Site '{site.nom}' : aucune saisie pour {libelle_periode}, "
                    f"mais aucun utilisateur avec email valide à prévenir."
                ))
                continue

            sujet = f"Rappel : saisie de fréquentation manquante - {libelle_periode}"
            message = (
                f"Bonjour,\n\n"
                f"La fréquentation du site \"{site.nom}\" n'a pas encore été saisie "
                f"pour {libelle_periode} sur la plateforme de suivi des indicateurs.\n\n"
                f"Merci de bien vouloir compléter cette saisie dès que possible.\n\n"
                f"Cordialement,\n"
                f"Saint-Étienne Tourisme"
            )

            if options["simulation"]:
                self.stdout.write(f"[SIMULATION] Email à {emails} pour le site '{site.nom}'")
            else:
                send_mail(
                    sujet, message, settings.DEFAULT_FROM_EMAIL, emails, fail_silently=False
                )
                nb_emails_envoyes += len(emails)
            self.stdout.write(f"Rappel préparé pour le site '{site.nom}' ({len(emails)} destinataire(s))")

        if options.get("resume_admin"):
            admins = Utilisateur.objects.filter(is_active=True).filter(
                models_q_admin()
            ).exclude(email="")
            emails_admin = [a.email for a in admins]
            if emails_admin:
                liste_sites = "\n".join(f"- {s.nom}" for s in sites_manquants)
                sujet = f"Récapitulatif des saisies manquantes - {libelle_periode}"
                message = (
                    f"Bonjour,\n\n"
                    f"{len(sites_manquants)} site(s) n'ont pas encore saisi leur fréquentation "
                    f"pour {libelle_periode} :\n\n{liste_sites}\n\n"
                    f"Cordialement,\n"
                    f"Plateforme de suivi des indicateurs"
                )
                if not options["simulation"]:
                    send_mail(sujet, message, settings.DEFAULT_FROM_EMAIL, emails_admin, fail_silently=False)
                self.stdout.write(f"Résumé envoyé aux administrateurs ({len(emails_admin)})")

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. {len(sites_manquants)} site(s) en attente de saisie pour {libelle_periode}, "
            f"{nb_emails_envoyes} email(s) envoyé(s)."
        ))


def models_q_admin():
    from django.db.models import Q
    return Q(role="admin") | Q(is_superuser=True)
