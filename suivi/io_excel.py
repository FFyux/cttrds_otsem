"""
Utilitaires d'export Excel et d'import CSV/Excel pour les indicateurs de fréquentation.
Séparé des vues pour faciliter les tests et la maintenance.
"""
import csv
import io
from datetime import date

from openpyxl import Workbook, load_workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

from .models import IndicateurMensuel, SiteTouristique, Evenement

# ── Palette charte graphique ────────────────────────────────────────────────
C_PRIMARY      = "323C73"   # bleu marine
C_YEAR_ROW     = "F2E7AE"   # jaune crème (lignes d'en-tête année)
C_HEADER_FONT  = "FFFFFF"   # blanc
C_BORDER       = "A1A1A1"
C_ALT_ROW      = "F4F4F8"   # gris très clair pour l'alternance
C_TOTAL_COL    = "E8EAF6"   # bleu très pâle pour colonne totaux

MOIS_NOMS = [
    "Janvier","Février","Mars","Avril","Mai","Juin",
    "Juillet","Août","Septembre","Octobre","Novembre","Décembre",
]
MOIS_MAP = {n.lower(): i+1 for i, n in enumerate(MOIS_NOMS)}


def _style_header(cell, bg=C_PRIMARY, fg=C_HEADER_FONT, bold=True, size=10):
    cell.font = Font(name="Arial", bold=bold, color=fg, size=size)
    cell.fill = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _border_thin():
    s = Side(style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)


def _style_data(cell, bg=None, bold=False, align="center"):
    cell.font = Font(name="Arial", bold=bold, size=9)
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(horizontal=align, vertical="center")
    cell.border = _border_thin()


def export_indicateurs_excel_unique(queryset):
    """
    Export en onglet unique : tous les sites, même structure de colonnes,
    triés par site puis par année/mois. Lignes d'en-tête par site en jaune crème.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Tous les sites"

    COLS = [
        ("Site",                   25),
        ("Commune",                16),
        ("Année",                  10),
        ("Mois",                   14),
        ("Fréq. totale",           14),
        ("Fréq. locale",           14),
        ("Fréq. France",           14),
        ("Fréq. étranger",         14),
        ("Fréq. gratuite",         14),
        ("Fréq. payante",          14),
        ("Jours ouverture",        14),
        ("Saisi par",              22),
        ("Date de saisie",         18),
    ]

    # Titre général
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLS))
    t = ws.cell(row=1, column=1, value="Indicateurs de fréquentation — Export complet")
    t.font = Font(name="Arial", bold=True, color=C_HEADER_FONT, size=12)
    t.fill = PatternFill("solid", fgColor=C_PRIMARY)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    # En-têtes colonnes
    for col_idx, (label, width) in enumerate(COLS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=label)
        _style_header(cell)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[2].height = 28

    row_num = 3
    current_site_id = None

    for ind in queryset.order_by("site__nom", "annee", "mois"):
        # Ligne d'en-tête de changement de site
        if ind.site_id != current_site_id:
            current_site_id = ind.site_id
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=len(COLS))
            hdr = ws.cell(row=row_num, column=1,
                          value=f"▶  {ind.site.nom}{' — ' + ind.site.commune if ind.site.commune else ''}")
            hdr.font = Font(name="Arial", bold=True, color=C_PRIMARY, size=10)
            hdr.fill = PatternFill("solid", fgColor=C_YEAR_ROW)
            hdr.alignment = Alignment(horizontal="left", vertical="center")
            hdr.border = _border_thin()
            ws.row_dimensions[row_num].height = 18
            row_num += 1

        bg = C_ALT_ROW if (row_num % 2 == 0) else None
        values = [
            ind.site.nom,
            ind.site.commune,
            ind.annee,
            MOIS_NOMS[ind.mois - 1],
            ind.frequentation_totale,
            ind.frequentation_locale,
            ind.frequentation_france,
            ind.frequentation_etranger,
            ind.frequentation_gratuite,
            ind.frequentation_payante,
            ind.nb_jours_ouverture,
            ind.saisi_par.get_full_name() if ind.saisi_par else "",
            ind.date_saisie.strftime("%d/%m/%Y %H:%M") if ind.date_saisie else "",
        ]
        for col_idx, val in enumerate(values, start=1):
            align = "left" if col_idx in (1, 2, 12) else "center"
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            _style_data(cell, bg=bg, align=align, bold=(col_idx == 5))
        row_num += 1

    ws.freeze_panes = "A3"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── EXPORT INDICATEURS ──────────────────────────────────────────────────────

def export_indicateurs_excel(queryset):
    """
    Génère un fichier Excel stylé avec les indicateurs mensuels.
    Retourne un objet BytesIO prêt à streamer.
    Organisation : un onglet par site, lignes groupées par année (en-tête crème).
    """
    wb = Workbook()
    wb.remove(wb.active)  # supprimer la feuille vide par défaut

    # Regrouper par site
    sites = {}
    for ind in queryset.order_by("site__nom", "annee", "mois"):
        sites.setdefault(ind.site_id, {"site": ind.site, "data": []})["data"].append(ind)

    if not sites:
        ws = wb.create_sheet("Indicateurs")
        ws["A1"] = "Aucune donnée à exporter."
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    COLS = [
        ("Année",               12),
        ("Mois",                14),
        ("Fréq. totale",        14),
        ("Fréq. locale",        14),
        ("Fréq. France",        14),
        ("Fréq. étranger",      14),
        ("Fréq. gratuite",      14),
        ("Fréq. payante",       14),
        ("Jours ouverture",     14),
        ("Saisi par",           20),
        ("Date de saisie",      18),
    ]

    for site_data in sites.values():
        site = site_data["site"]
        # Nom d'onglet : max 31 caractères, caractères interdits supprimés
        sheet_name = site.nom[:31].replace("/","_").replace("\\","_").replace("?","").replace("*","").replace("[","").replace("]","")
        ws = wb.create_sheet(title=sheet_name)

        # Titre du site
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLS))
        title_cell = ws.cell(row=1, column=1, value=f"{site.nom} — {site.commune or ''}")
        title_cell.font = Font(name="Arial", bold=True, color=C_HEADER_FONT, size=12)
        title_cell.fill = PatternFill("solid", fgColor=C_PRIMARY)
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 22

        # En-têtes colonnes
        for col_idx, (label, width) in enumerate(COLS, start=1):
            cell = ws.cell(row=2, column=col_idx, value=label)
            _style_header(cell)
            ws.column_dimensions[get_column_letter(col_idx)].width = width
        ws.row_dimensions[2].height = 32

        # Données, groupées par année
        row_num = 3
        current_year = None

        for ind in site_data["data"]:
            if ind.annee != current_year:
                current_year = ind.annee

                # Ligne d'en-tête d'année
                ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=len(COLS))
                year_cell = ws.cell(row=row_num, column=1, value=f"▶  {current_year}")
                year_cell.font = Font(name="Arial", bold=True, color=C_PRIMARY, size=10)
                year_cell.fill = PatternFill("solid", fgColor=C_YEAR_ROW)
                year_cell.alignment = Alignment(horizontal="left", vertical="center")
                year_cell.border = _border_thin()
                ws.row_dimensions[row_num].height = 18
                row_num += 1

            # Alternance de fond
            bg = C_ALT_ROW if (row_num % 2 == 0) else None

            values = [
                ind.annee,
                MOIS_NOMS[ind.mois - 1],
                ind.frequentation_totale,
                ind.frequentation_locale,
                ind.frequentation_france,
                ind.frequentation_etranger,
                ind.frequentation_gratuite,
                ind.frequentation_payante,
                ind.nb_jours_ouverture,
                ind.saisi_par.get_full_name() if ind.saisi_par else "",
                ind.date_saisie.strftime("%d/%m/%Y %H:%M") if ind.date_saisie else "",
            ]
            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                align = "left" if col_idx >= 10 else "center"
                _style_data(cell, bg=bg, align=align)

            row_num += 1

        # Figer les deux premières lignes
        ws.freeze_panes = "A3"

    # Onglet récapitulatif tous sites
    _ajouter_recap(wb, sites)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _ajouter_recap(wb, sites):
    """Onglet récap : total par site et par année, toutes données confondues."""
    ws = wb.create_sheet(title="Récapitulatif", index=0)

    ws.merge_cells("A1:F1")
    c = ws.cell(row=1, column=1, value="Récapitulatif — tous sites")
    c.font = Font(name="Arial", bold=True, color=C_HEADER_FONT, size=12)
    c.fill = PatternFill("solid", fgColor=C_PRIMARY)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    headers = ["Site", "Année", "Total visites", "Dont gratuit", "Dont payant", "Jours ouverture"]
    widths   = [30, 10, 16, 14, 14, 16]
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=2, column=i, value=h)
        _style_header(cell)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[2].height = 28

    row = 3
    for site_data in sites.values():
        # Agréger par année
        by_year = {}
        for ind in site_data["data"]:
            y = ind.annee
            if y not in by_year:
                by_year[y] = {"total": 0, "gratuit": 0, "payant": 0, "jours": 0}
            by_year[y]["total"]  += ind.frequentation_totale
            by_year[y]["gratuit"] += ind.frequentation_gratuite
            by_year[y]["payant"]  += ind.frequentation_payante
            by_year[y]["jours"]   += ind.nb_jours_ouverture

        site_name = site_data["site"].nom
        for year in sorted(by_year):
            d = by_year[year]
            bg = C_ALT_ROW if row % 2 == 0 else None
            for col, val in enumerate([site_name, year, d["total"], d["gratuit"], d["payant"], d["jours"]], 1):
                cell = ws.cell(row=row, column=col, value=val)
                _style_data(cell, bg=bg, align="left" if col == 1 else "center",
                            bold=(col == 3))
            row += 1

    ws.freeze_panes = "A3"


# ── EXPORT ÉVÉNEMENTS ───────────────────────────────────────────────────────

def export_evenements_excel(queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Événements"

    ws.merge_cells("A1:G1")
    c = ws.cell(row=1, column=1, value="Événements — Saint-Étienne Tourisme")
    c.font = Font(name="Arial", bold=True, color=C_HEADER_FONT, size=12)
    c.fill = PatternFill("solid", fgColor=C_PRIMARY)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    COLS = [
        ("Nom de l'événement", 30),
        ("Site",               25),
        ("Commune",            18),
        ("Date début",         14),
        ("Date fin",           14),
        ("Fréquentation",      15),
        ("Saisi par",          20),
    ]
    for i, (h, w) in enumerate(COLS, 1):
        cell = ws.cell(row=2, column=i, value=h)
        _style_header(cell)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[2].height = 28

    for row_idx, ev in enumerate(queryset.order_by("date_debut"), start=3):
        bg = C_ALT_ROW if row_idx % 2 == 0 else None
        vals = [
            ev.nom,
            ev.site.nom,
            ev.site.commune,
            ev.date_debut.strftime("%d/%m/%Y"),
            ev.date_fin.strftime("%d/%m/%Y"),
            ev.frequentation,
            ev.saisi_par.get_full_name() if ev.saisi_par else "",
        ]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            _style_data(cell, bg=bg, align="left" if col in (1, 2, 3, 7) else "center")

    ws.freeze_panes = "A3"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── TEMPLATE D'IMPORT ───────────────────────────────────────────────────────

def generer_template_import():
    """
    Génère un fichier Excel vierge pré-formaté que l'admin remplit
    pour importer des données en masse.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicateurs à importer"

    # Entête explicatif
    ws.merge_cells("A1:K1")
    c = ws.cell(row=1, column=1,
        value="TEMPLATE D'IMPORT — Remplir les lignes à partir de la ligne 4. Ne pas modifier les en-têtes.")
    c.font = Font(name="Arial", bold=True, color="7A5C00", size=10)
    c.fill = PatternFill("solid", fgColor="FFF9C4")
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 20

    COLS = [
        ("nom_site *",             "Nom exact du site (tel qu'il existe dans la base)", 28),
        ("annee *",                "Ex : 2026",                                          10),
        ("mois *",                 "Janvier, Février... ou 1, 2...",                     14),
        ("frequentation_totale *", "Nombre entier ≥ 0",                                  18),
        ("frequentation_locale",   "Nombre entier ≥ 0 (facultatif)",                     18),
        ("frequentation_france",   "Nombre entier ≥ 0 (facultatif)",                     18),
        ("frequentation_etranger", "Nombre entier ≥ 0 (facultatif)",                     18),
        ("frequentation_gratuite", "Nombre entier ≥ 0 (facultatif)",                     18),
        ("frequentation_payante",  "Nombre entier ≥ 0 (facultatif)",                     18),
        ("nb_jours_ouverture *",   "Entier entre 0 et 31",                               18),
        ("commentaire",            "Texte libre (facultatif)",                            30),
    ]

    # Ligne d'aide (grisée)
    for i, (_, aide, _) in enumerate(COLS, 1):
        cell = ws.cell(row=2, column=i, value=aide)
        cell.font = Font(name="Arial", italic=True, color="757575", size=8)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 30

    # En-têtes
    for i, (label, _, width) in enumerate(COLS, 1):
        cell = ws.cell(row=3, column=i, value=label)
        _style_header(cell, size=9)
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[3].height = 28

    # Deux lignes d'exemple
    exemples = [
        ["Cité Le Corbusier", 2026, "Juin", 1200, 300, 700, 100, 400, 800, 26, ""],
        ["La Chartreuse",     2026, "Juin",  450, 100, 280,  50, 200, 250, 20, "Exposition temporaire"],
    ]
    for row_idx, ex in enumerate(exemples, start=4):
        for col, val in enumerate(ex, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = Font(name="Arial", color="1A6E1A", size=9, italic=True)
            cell.fill = PatternFill("solid", fgColor="F1FBF1")
            cell.alignment = Alignment(horizontal="left" if col in (1, 3, 11) else "center")
            cell.border = _border_thin()

    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── IMPORT ──────────────────────────────────────────────────────────────────

class ImportError(Exception):
    pass


def _parse_mois(val):
    """Accepte '6', '06', 'Juin', 'juin' → retourne int 1-12 ou None."""
    if val is None:
        return None
    s = str(val).strip()
    try:
        n = int(s)
        if 1 <= n <= 12:
            return n
    except ValueError:
        pass
    return MOIS_MAP.get(s.lower().replace("é","e").replace("û","u").replace("â","a"))


def _parse_int(val, default=0):
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def importer_indicateurs(file_obj, utilisateur, dry_run=False):
    """
    Importe des indicateurs depuis un fichier Excel ou CSV.
    Retourne un dict :
      {
        "ok": [...],          # lignes importées avec succès
        "erreurs": [...],     # lignes avec erreurs (numéro, message)
        "ignores": [...],     # lignes ignorées (doublons déjà existants)
        "total": int,
        "dry_run": bool,
      }
    """
    # Détecter le format
    name = getattr(file_obj, "name", "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        rows = _lire_excel(file_obj)
    else:
        rows = _lire_csv(file_obj)

    ok, erreurs, ignores = [], [], []
    sites_cache = {s.nom.strip().lower(): s for s in SiteTouristique.objects.filter(actif=True)}

    for i, row in enumerate(rows, start=1):
        # Ignorer les lignes complètement vides
        if all(v is None or str(v).strip() == "" for v in row.values()):
            continue

        num_ligne = f"Ligne {i}"
        erreurs_ligne = []

        # --- nom_site ---
        nom_site = str(row.get("nom_site") or "").strip()
        site = sites_cache.get(nom_site.lower())
        if not site:
            erreurs_ligne.append(f"Site « {nom_site} » introuvable ou inactif")

        # --- annee ---
        annee = _parse_int(row.get("annee"))
        if annee is None or not (2000 <= annee <= 2100):
            erreurs_ligne.append(f"Année invalide : « {row.get('annee')} »")

        # --- mois ---
        mois = _parse_mois(row.get("mois"))
        if mois is None:
            erreurs_ligne.append(f"Mois invalide : « {row.get('mois')} »")

        # --- fréquentation_totale ---
        freq_totale = _parse_int(row.get("frequentation_totale"))
        if freq_totale is None or freq_totale < 0:
            erreurs_ligne.append(f"Fréquentation totale invalide : « {row.get('frequentation_totale')} »")

        # --- champs optionnels ---
        freq_locale   = _parse_int(row.get("frequentation_locale"), 0)
        freq_france   = _parse_int(row.get("frequentation_france"), 0)
        freq_etranger = _parse_int(row.get("frequentation_etranger"), 0)
        freq_gratuite = _parse_int(row.get("frequentation_gratuite"), 0)
        freq_payante  = _parse_int(row.get("frequentation_payante"), 0)
        jours         = _parse_int(row.get("nb_jours_ouverture"), 0)
        commentaire   = str(row.get("commentaire") or "").strip()

        # --- validations métier ---
        if not erreurs_ligne:
            total_provenance = (freq_locale or 0) + (freq_france or 0) + (freq_etranger or 0)
            if total_provenance > (freq_totale or 0) and total_provenance > 0:
                erreurs_ligne.append(
                    f"Somme provenances ({total_provenance}) > total ({freq_totale})"
                )
            total_tarif = (freq_gratuite or 0) + (freq_payante or 0)
            if total_tarif > (freq_totale or 0) and total_tarif > 0:
                erreurs_ligne.append(
                    f"Somme gratuit+payant ({total_tarif}) > total ({freq_totale})"
                )
            if jours is not None and (jours < 0 or jours > 31):
                erreurs_ligne.append(f"Jours d'ouverture invalide : {jours}")

        if erreurs_ligne:
            erreurs.append({"ligne": num_ligne, "messages": erreurs_ligne, "data": row})
            continue

        # --- vérifier doublon ---
        existe = IndicateurMensuel.objects.filter(site=site, annee=annee, mois=mois).first()
        if existe:
            ignores.append({
                "ligne": num_ligne,
                "message": f"{site.nom} — {MOIS_NOMS[mois-1]} {annee} déjà présent (non écrasé)",
            })
            continue

        # --- créer l'objet ---
        if not dry_run:
            IndicateurMensuel.objects.create(
                site=site,
                annee=annee,
                mois=mois,
                frequentation_totale=freq_totale,
                frequentation_locale=freq_locale or 0,
                frequentation_france=freq_france or 0,
                frequentation_etranger=freq_etranger or 0,
                frequentation_gratuite=freq_gratuite or 0,
                frequentation_payante=freq_payante or 0,
                nb_jours_ouverture=jours or 0,
                commentaire=commentaire,
                saisi_par=utilisateur,
            )

        ok.append({
            "ligne": num_ligne,
            "label": f"{site.nom} — {MOIS_NOMS[mois-1]} {annee}",
        })

    return {
        "ok": ok,
        "erreurs": erreurs,
        "ignores": ignores,
        "total": len(ok) + len(erreurs) + len(ignores),
        "dry_run": dry_run,
    }


def _lire_excel(file_obj):
    """Lit un Excel, détecte automatiquement la ligne d'en-têtes (ligne 3 pour le template)."""
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # Chercher la ligne d'en-têtes (contient "nom_site")
    header_row_idx = None
    for idx, row in enumerate(rows):
        cells = [str(c).strip().lower() if c else "" for c in row]
        if "nom_site" in cells or "nom_site *" in cells:
            header_row_idx = idx
            break

    if header_row_idx is None:
        raise ImportError(
            "En-têtes non trouvés. "
            "Utilisez le template fourni ou assurez-vous que la première colonne s'intitule 'nom_site'."
        )

    raw_headers = rows[header_row_idx]
    # Normaliser les noms de colonnes (enlever *, espaces, étoiles)
    headers = [str(h).strip().lower().replace(" *", "").replace("*", "").replace(" ", "_") if h else "" for h in raw_headers]

    result = []
    for row in rows[header_row_idx + 1:]:
        d = {headers[i]: row[i] for i in range(min(len(headers), len(row))) if headers[i]}
        result.append(d)
    return result


def _lire_csv(file_obj):
    """Lit un CSV (délimiteur ; ou ,, encodage UTF-8 ou latin-1)."""
    try:
        content = file_obj.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        file_obj.seek(0)
        content = file_obj.read().decode("latin-1")

    # Détecter délimiteur
    delimiteur = ";" if content.count(";") > content.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiteur)

    # Normaliser les noms de colonnes
    rows = []
    for row in reader:
        d = {
            k.strip().lower().replace(" *", "").replace("*", "").replace(" ", "_"): v
            for k, v in row.items() if k
        }
        rows.append(d)
    return rows
