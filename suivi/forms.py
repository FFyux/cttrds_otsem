from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import IndicateurMensuel, Utilisateur, SiteTouristique, Evenement, OfficeDeTourisme


def choix_annees():
    annee_courante = date.today().year
    return [(a, str(a)) for a in range(annee_courante - 5, annee_courante + 2)][::-1]


class IndicateurMensuelForm(forms.ModelForm):
    annee = forms.TypedChoiceField(
        label="Année", choices=[], coerce=int,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = IndicateurMensuel
        fields = [
            "site",
            "annee",
            "mois",
            "frequentation_totale",
            "frequentation_locale",
            "frequentation_france",
            "frequentation_etranger",
            "frequentation_gratuite",
            "frequentation_payante",
            "nb_jours_ouverture",
            "commentaire",
        ]
        widgets = {
            "mois": forms.Select(attrs={"class": "form-select"}),
            "frequentation_totale": forms.NumberInput(attrs={"class": "form-control"}),
            "frequentation_locale": forms.NumberInput(attrs={"class": "form-control"}),
            "frequentation_france": forms.NumberInput(attrs={"class": "form-control"}),
            "frequentation_etranger": forms.NumberInput(attrs={"class": "form-control"}),
            "frequentation_gratuite": forms.NumberInput(attrs={"class": "form-control"}),
            "frequentation_payante": forms.NumberInput(attrs={"class": "form-control"}),
            "nb_jours_ouverture": forms.NumberInput(attrs={"class": "form-control"}),
            "commentaire": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = choix_annees()
        # Un saisisseur ne peut saisir que pour son propre site
        if utilisateur and not utilisateur.est_admin:
            self.fields["site"].queryset = SiteTouristique.objects.filter(
                pk=utilisateur.site_id
            )
            self.fields["site"].initial = utilisateur.site
            self.fields["site"].disabled = True
        else:
            self.fields["site"].queryset = SiteTouristique.objects.filter(actif=True)

    def clean(self):
        cleaned = super().clean()
        totale = cleaned.get("frequentation_totale") or 0
        local = cleaned.get("frequentation_locale") or 0
        france = cleaned.get("frequentation_france") or 0
        etranger = cleaned.get("frequentation_etranger") or 0
        if (local + france + etranger) > totale and totale > 0:
            raise forms.ValidationError(
                "La somme des fréquentations par provenance dépasse la "
                "fréquentation totale saisie. Merci de vérifier les chiffres."
            )
        return cleaned


class UtilisateurCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = ["username", "first_name", "last_name", "email", "site", "role", "telephone"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "site": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["password1", "password2"]:
            self.fields[name].widget.attrs.update({"class": "form-control"})


class SiteTouristiqueForm(forms.ModelForm):
    offices = forms.ModelMultipleChoiceField(
        queryset=OfficeDeTourisme.objects.filter(actif=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Offices de tourisme rattachés",
    )

    class Meta:
        model = SiteTouristique
        fields = ["nom", "commune", "categorie", "offices", "actif"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "commune": forms.TextInput(attrs={"class": "form-control"}),
            "categorie": forms.Select(attrs={"class": "form-select"}),
        }


class OfficeDeTourismeForm(forms.ModelForm):
    class Meta:
        model = OfficeDeTourisme
        fields = ["nom", "actif"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
        }


class EvenementForm(forms.ModelForm):
    class Meta:
        model = Evenement
        fields = ["site", "nom", "date_debut", "date_fin", "frequentation", "commentaire"]
        widgets = {
            "site": forms.Select(attrs={"class": "form-select"}),
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "date_debut": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "date_fin": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "frequentation": forms.NumberInput(attrs={"class": "form-control"}),
            "commentaire": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        if utilisateur and not utilisateur.est_admin:
            self.fields["site"].queryset = SiteTouristique.objects.filter(pk=utilisateur.site_id)
            self.fields["site"].initial = utilisateur.site
            self.fields["site"].disabled = True
        else:
            self.fields["site"].queryset = SiteTouristique.objects.filter(actif=True)
