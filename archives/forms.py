"""
archives/forms.py — Formulaires ENSMG — champs calés sur les vrais modèles.
"""
from django import forms
from django.utils import timezone


# ── Dépôt AGENT (simplifié) ──────────────────────────────────────────────────

class DepotAgentForm(forms.Form):
    """Formulaire simplifié : le personnel dépose juste le fichier + titre."""
    titre = forms.CharField(
        max_length=500, label="Titre du document",
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'Titre complet du document'})
    )
    fichier = forms.FileField(
        label="Fichier à déposer",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    date_reception = forms.DateField(
        label="Date du document", initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    categorie = forms.IntegerField(
        required=False, label="Catégorie (optionnel)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        required=False, label="Description / Contexte",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Contexte ou motif du depot (optionnel)…'})
    )
    mots_cles = forms.CharField(
        required=False, label="Mots-clés (optionnel)",
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'Ex : budget, 2023, conseil scientifique…'})
    )

    # ── Provenance ────────────────────────────────────────────────────────────
    provenance_interne = forms.BooleanField(
        required=False, initial=True, label="Provenance ENSMG (interne)",
    )
    provenance_externe = forms.IntegerField(
        required=False, label="Organisme externe",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_provenance_externe'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import CategorieDocument, ProvenanceExterne
        self.fields['categorie'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '— Aucune categorie —')] + [
                (c.pk, str(c)) for c in CategorieDocument.objects.all()
            ]
        )
        self.fields['provenance_externe'].widget = forms.Select(
            attrs={'class': 'form-select', 'id': 'id_provenance_externe'},
            choices=[('', '— Sélectionner un organisme —')] + [
                (p.pk, str(p)) for p in ProvenanceExterne.objects.filter(actif=True)
            ]
        )

    def clean(self):
        cleaned = super().clean()
        provenance_interne = cleaned.get('provenance_interne', True)
        if not provenance_interne and not cleaned.get('provenance_externe'):
            self.add_error('provenance_externe', "Sélectionnez l'organisme externe ou cochez 'Provenance ENSMG'.")
        return cleaned


# ── Traitement dépôt ARCHIVISTE ───────────────────────────────────────────────

class TraiterDepotForm(forms.Form):
    """L'archiviste archive (en renseignant tout) ou rejette le dépôt."""

    DECISION_CHOICES = [
        ('', '---------'), ('ARCHIVE', 'Archiver le document'), ('REJETE', 'Rejeter le depot'),
    ]
    STATUT_CHOICES = [
        ('COURANT', 'Archive courante'), ('INTERMEDIAIRE', 'Archive intermediaire'), ('DEFINITIF', 'Archive definitive'),
    ]
    CONFIDENTIALITE_CHOICES = [
        ('', '---------'), ('PUBLIC', 'Public'), ('INTERNE', 'Usage interne'),
        ('CONFIDENTIEL', 'Confidentiel'), ('SECRET', 'Secret'),
    ]
    SORT_FINAL_CHOICES = [
        ('EN_ATTENTE', 'En attente'), ('CONSERVATION', 'Conservation definitive'),
        ('ELIMINATION', 'Elimination'), ('TRI', 'Tri'),
    ]
    SUPPORT_CHOICES = [
        ('NUMERIQUE', 'Numerique'), ('PAPIER', 'Papier'), ('MIXTE', 'Mixte'),
    ]

    decision        = forms.ChoiceField(choices=DECISION_CHOICES, label="Decision",
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    producteur      = forms.CharField(required=False, max_length=200, label="Service producteur",
                                      widget=forms.TextInput(attrs={'class': 'form-control',
                                                                     'placeholder': 'Ex : Direction administrative'}))
    date_creation   = forms.DateField(required=False, label="Date du document",
                                      widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    categorie       = forms.IntegerField(required=False, label="Categorie documentaire",
                                         widget=forms.Select(attrs={'class': 'form-select'}))
    plan_classement = forms.IntegerField(required=False, label="Plan de classement",
                                         widget=forms.Select(attrs={'class': 'form-select'}))
    confidentialite = forms.ChoiceField(choices=CONFIDENTIALITE_CHOICES, required=False, label="Confidentialite",
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    statut          = forms.ChoiceField(choices=STATUT_CHOICES, initial='COURANT', label="Statut",
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    support         = forms.ChoiceField(choices=SUPPORT_CHOICES, initial='NUMERIQUE', label="Support",
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    sort_final      = forms.ChoiceField(choices=SORT_FINAL_CHOICES, initial='EN_ATTENTE', label="Sort final",
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    localisation    = forms.CharField(required=False, label="Localisation physique",
                                      widget=forms.TextInput(attrs={'class': 'form-control',
                                                                     'placeholder': 'Batiment A, Salle 12, Etagere 3'}))
    mots_cles       = forms.CharField(required=False, label="Mots-clés",
                                      widget=forms.TextInput(attrs={'class': 'form-control',
                                                                     'placeholder': 'Ex : budget, 2023, conseil scientifique…'}))
    motif_rejet     = forms.CharField(required=False, label="Motif du rejet",
                                      widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                                    'placeholder': "Expliquer le motif a l'agent..."}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import CategorieDocument, PlanClassement
        self.fields['categorie'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '---------')] + [(c.pk, str(c)) for c in CategorieDocument.objects.all()]
        )
        self.fields['plan_classement'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '---------')] + [
                (p.pk, f"{p.code} — {p.intitule}") for p in PlanClassement.objects.filter(actif=True)
            ]
        )

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get('decision')
        if decision == 'REJETE' and not cleaned.get('motif_rejet', '').strip():
            self.add_error('motif_rejet', "Le motif de rejet est obligatoire.")
        if decision == 'ARCHIVE':
            if not cleaned.get('plan_classement'):
                self.add_error('plan_classement', "Le plan de classement est requis.")
            if not cleaned.get('confidentialite'):
                self.add_error('confidentialite', "La confidentialite est requise.")
            if not cleaned.get('categorie'):
                self.add_error('categorie', "La categorie est requise.")
        return cleaned


# ── Demande de prêt AGENT ─────────────────────────────────────────────────────

class DemandePretForm(forms.Form):
    TYPE_CHOICES = [
        ('', '---------'),
        ('PHYSIQUE',  'Pret physique (document papier)'),
        ('NUMERIQUE', 'Acces numerique (telechargement temporaire)'),
    ]

    type_demande = forms.ChoiceField(
        choices=TYPE_CHOICES, label="Type de demande",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_type_demande'})
    )
    motif = forms.CharField(
        label="Motif de la demande",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Expliquer pourquoi vous avez besoin de ce document (min. 20 caracteres)…'})
    )
    duree_acces_heures = forms.IntegerField(
        required=False, label="Duree d'acces numerique (heures)",
        min_value=1, max_value=720, initial=24,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '24'})
    )

    def clean_motif(self):
        motif = self.cleaned_data.get('motif', '').strip()
        if len(motif) < 20:
            raise forms.ValidationError("Le motif doit comporter au moins 20 caracteres.")
        return motif

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('type_demande'):
            self.add_error('type_demande', "Veuillez choisir un type de demande.")
        if cleaned.get('type_demande') == 'NUMERIQUE' and not cleaned.get('duree_acces_heures'):
            cleaned['duree_acces_heures'] = 24
        return cleaned


# ── Traitement demande de prêt ARCHIVISTE ────────────────────────────────────

class TraiterDemandePretForm(forms.Form):
    DECISION_CHOICES = [
        ('', '---------'), ('ACCORDEE', 'Accorder le pret'), ('REFUSEE', 'Refuser le pret'),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES, label="Decision",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    motif_refus = forms.CharField(
        required=False, label="Motif du refus",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Obligatoire en cas de refus…'})
    )
    date_retour_prevue = forms.DateField(
        required=False, label="Date de retour confirmee (pret physique)",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    duree_acces_heures = forms.IntegerField(
        required=False, label="Duree d'acces accordee (heures)",
        min_value=1, max_value=720,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '24'})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'REFUSEE' and not cleaned.get('motif_refus', '').strip():
            self.add_error('motif_refus', "Un motif est requis pour un refus.")
        return cleaned


# ── Retour prêt ───────────────────────────────────────────────────────────────

class RetourPretForm(forms.Form):
    date_retour_effective = forms.DateField(
        label="Date de retour effective", initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    observations = forms.CharField(
        required=False, label="Observations",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'Etat du document, remarques…'})
    )


# ── Accès ABAC direct ─────────────────────────────────────────────────────────

class AccesDocumentForm(forms.Form):
    utilisateur = forms.IntegerField(
        label="Utilisateur",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_fin = forms.DateTimeField(
        required=False, label="Expiration (vide = permanent)",
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    motif = forms.CharField(
        label="Motif",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'Justification de cet acces special…'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['utilisateur'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '---------')] + [
                (u.pk, u.get_full_name() or u.username)
                for u in User.objects.filter(is_active=True).order_by('last_name')
            ]
        )


# ── Recherche ─────────────────────────────────────────────────────────────────

class RechercheDocumentForm(forms.Form):
    q = forms.CharField(
        required=False, label="Recherche",
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'Titre, identifiant, producteur…'})
    )
    categorie = forms.IntegerField(
        required=False, label="Categorie",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    confidentialite = forms.ChoiceField(
        required=False, label="Confidentialite",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    annee = forms.IntegerField(
        required=False, label="Annee", min_value=1900, max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '2024'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import CategorieDocument, Document
        self.fields['categorie'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', 'Toutes les categories')] + [
                (c.pk, str(c)) for c in CategorieDocument.objects.all()
            ]
        )
        self.fields['confidentialite'].choices = [('', 'Toutes')] + list(
            Document.Confidentialite.choices
        )


# ── Demande de recherche documentaire (agent, sans document connu) ────────────

class DemandeRechercheForm(forms.Form):
    """
    L'agent ne connaît pas l'identifiant du document.
    Il décrit ce qu'il cherche ; l'archiviste fait la recherche.
    """
    categorie = forms.IntegerField(
        required=False, label="Catégorie du document",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    service_producteur = forms.IntegerField(
        required=False,
        label="Service / département producteur",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    motif = forms.CharField(
        label="Motif de la demande",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Pourquoi avez-vous besoin de ce document ? (min. 20 caractères)'}),
    )
    description = forms.CharField(
        label="Description du document recherché",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                     'placeholder': 'Titre approximatif, date approximative, contenu, contexte, mots-clés…'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import CategorieDocument
        from users.models import Departement
        self.fields['categorie'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '— Toutes les catégories —')] + [
                (c.pk, str(c)) for c in CategorieDocument.objects.all()
            ]
        )
        self.fields['service_producteur'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '— Sélectionner un service/département —')] + [
                (d.pk, d.nom) for d in Departement.objects.filter(actif=True).order_by('nom')
            ]
        )

    def clean_motif(self):
        motif = self.cleaned_data.get('motif', '').strip()
        if len(motif) < 20:
            raise forms.ValidationError("Le motif doit comporter au moins 20 caractères.")
        return motif

    def clean_description(self):
        desc = self.cleaned_data.get('description', '').strip()
        if len(desc) < 20:
            raise forms.ValidationError("La description doit comporter au moins 20 caractères.")
        return desc


class TraiterRechercheForm(forms.Form):
    """Formulaire de traitement d'une demande de recherche par l'archiviste."""

    document_id = forms.IntegerField(
        required=False, label="Document trouvé",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_document_id'})
    )
    decision = forms.ChoiceField(
        choices=[('', '---------'), ('ACCORDER', 'Document trouvé — prêt accordé'), ('REFUSER', 'Document non trouvé / refuser')],
        label="Décision",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    motif_refus = forms.CharField(
        required=False, label="Motif du refus / document non trouvé",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': "Expliquer à l'agent pourquoi le document n'a pas été trouvé…"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import Document
        self.fields['document_id'].widget = forms.Select(
            attrs={'class': 'form-select', 'id': 'id_document_id'},
            choices=[('', '— Sélectionner le document trouvé —')] + [
                (d.pk, f"{d.identifiant} — {d.titre[:60]}")
                for d in Document.objects.exclude(statut='ELIMINE').order_by('identifiant')
            ]
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'ACCORDER' and not cleaned.get('document_id'):
            self.add_error('document_id', "Sélectionnez le document à prêter.")
        if cleaned.get('decision') == 'REFUSER' and not cleaned.get('motif_refus', '').strip():
            self.add_error('motif_refus', "Le motif est obligatoire.")
        return cleaned


# ── Administration — Catégorie de document ────────────────────────────────────

class CategorieDocumentForm(forms.Form):
    """CRUD catégorie — l'admin peut créer n'importe quel code (pas limité aux 8 fixes)."""
    code = forms.CharField(
        max_length=10, label="Code (ex : ADM, SCI…)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ADM, SCI, GEO…',
                                      'style': 'text-transform:uppercase'})
    )
    nom = forms.CharField(
        max_length=200, label="Intitulé",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet de la catégorie'})
    )
    description = forms.CharField(
        required=False, label="Description",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Description facultative…'})
    )

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


# ── Administration — Plan de classement ─────────────────────────────────────

class PlanClassementForm(forms.Form):
    """CRUD plan de classement."""
    NIVEAU_CHOICES = [
        ('', '---------'),
        (1, 'Fonds'),
        (2, 'Série'),
        (3, 'Sous-série'),
        (4, 'Dossier'),
    ]

    code = forms.CharField(
        max_length=30, label="Cote (ex : ENSMG-ADM-001)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ENSMG-ADM-001'})
    )
    intitule = forms.CharField(
        max_length=300, label="Intitulé",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre du plan de classement'})
    )
    niveau = forms.IntegerField(
        label="Niveau hiérarchique",
        widget=forms.Select(attrs={'class': 'form-select'}, choices=NIVEAU_CHOICES)
    )
    parent = forms.IntegerField(
        required=False, label="Rubrique parente (facultatif)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    categorie = forms.IntegerField(
        required=False, label="Catégorie documentaire (facultatif)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        required=False, label="Description",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    actif = forms.BooleanField(required=False, initial=True, label="Actif")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from archives.models import PlanClassement, CategorieDocument
        self.fields['parent'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '— Aucun parent (niveau racine) —')] + [
                (p.pk, f"{p.code} — {p.intitule}") for p in PlanClassement.objects.filter(actif=True).order_by('code')
            ]
        )
        self.fields['categorie'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[('', '— Aucune catégorie —')] + [
                (c.pk, str(c)) for c in CategorieDocument.objects.all()
            ]
        )


# ── Administration — Provenance externe ─────────────────────────────────────

class ProvenanceExterneForm(forms.Form):
    """Création/modification d'une provenance externe."""
    code = forms.CharField(
        max_length=30, label="Code court (ex : RECTO, BU, ESP)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: RECTO',
                                      'style': 'text-transform:uppercase'})
    )
    nom = forms.CharField(
        max_length=200, label="Nom de l'organisme",
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'Ex: Rectorat de l\'UCAD'})
    )
    description = forms.CharField(
        required=False, label="Description",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    actif = forms.BooleanField(required=False, initial=True, label="Actif")

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()
