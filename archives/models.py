"""
Modèles du système de gestion des archives de l'ENSMG.
Conformes à la norme ISO 15489 et à la loi sénégalaise n° 2006-19.
"""

import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# =============================================================================
# 1. CATÉGORIES DOCUMENTAIRES (CDC § 4)
# =============================================================================

class CategorieDocument(models.Model):
    """
    Huit catégories documentaires issues du cahier des charges (§ 4.1 à 4.8).
    Constituent le premier niveau de classification thématique.
    """

    class Code(models.TextChoices):
        ADMINISTRATIF  = 'ADM', 'Administratif et institutionnel'
        PEDAGOGIQUE    = 'PED', 'Gestion académique et pédagogique'
        SCIENTIFIQUE   = 'SCI', 'Scientifique et de recherche'
        GEOLOGIQUE     = 'GEO', 'Géologique et minier'
        TERRAIN        = 'TER', 'Terrain et technique'
        PARTENARIAT    = 'PAR', 'Partenariats et industrie'
        FINANCIER_RH   = 'FRH', 'Financier et ressources humaines'
        PATRIMONIAL    = 'PAT', 'Patrimonial et historique'

    code        = models.CharField(max_length=10, unique=True, verbose_name='Code')
    nom         = models.CharField(max_length=200, verbose_name='Intitulé')
    description = models.TextField(blank=True, verbose_name='Description')

    class Meta:
        verbose_name          = 'Catégorie de document'
        verbose_name_plural   = 'Catégories de documents'
        ordering              = ['code']

    def __str__(self):
        return f"[{self.code}] {self.nom}"


# =============================================================================
# 2. PLAN DE CLASSEMENT HIÉRARCHIQUE (CDC § 5.3)
# =============================================================================

class PlanClassement(models.Model):
    """
    Plan de classement hiérarchique à 4 niveaux :
    Fonds > Série > Sous-série > Dossier.
    Permet la mise à jour contrôlée via le champ `actif`.
    """

    class Niveau(models.IntegerChoices):
        FONDS      = 1, 'Fonds'
        SERIE      = 2, 'Série'
        SOUS_SERIE = 3, 'Sous-série'
        DOSSIER    = 4, 'Dossier'

    code      = models.CharField(max_length=30, unique=True, verbose_name='Cote')
    intitule  = models.CharField(max_length=300, verbose_name='Intitulé')
    parent    = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='enfants',
        verbose_name='Rubrique parente',
    )
    niveau    = models.PositiveSmallIntegerField(choices=Niveau.choices, verbose_name='Niveau hiérarchique')
    categorie = models.ForeignKey(
        CategorieDocument,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Catégorie documentaire',
    )
    description = models.TextField(blank=True, verbose_name='Description')
    actif       = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name        = 'Plan de classement'
        verbose_name_plural = 'Plan de classement'
        ordering            = ['code']

    def __str__(self):
        return f"{self.code} — {self.intitule}"

    def get_chemin_complet(self):
        """Retourne le chemin hiérarchique complet : Fonds > Série > Dossier."""
        if self.parent:
            return f"{self.parent.get_chemin_complet()} > {self.intitule}"
        return self.intitule


# =============================================================================
# 3. TABLEAU DE GESTION — DUA (CDC § 5.4)
# =============================================================================

class TableauGestion(models.Model):
    """
    Tableau de gestion des Durées d'Utilité Administrative (DUA).
    Définit, par type de document, la durée de conservation et le sort final.
    Conforme à la loi sénégalaise n° 2006-19.
    """

    class SortFinal(models.TextChoices):
        CONSERVATION = 'CONSERVATION', 'Conservation définitive'
        ELIMINATION  = 'ELIMINATION',  'Élimination'
        TRI          = 'TRI',          'Tri (conservation partielle)'

    type_document        = models.ForeignKey(CategorieDocument, on_delete=models.PROTECT, verbose_name='Catégorie')
    intitule             = models.CharField(max_length=300, verbose_name='Intitulé du type de document')
    duree_courante       = models.PositiveIntegerField(verbose_name='DUA courante (années)', help_text='Durée en archives courantes')
    duree_intermediaire  = models.PositiveIntegerField(default=0, verbose_name='DUA intermédiaire (années)', help_text='Durée en archives intermédiaires')
    sort_final           = models.CharField(max_length=20, choices=SortFinal.choices, verbose_name='Sort final')
    observations         = models.TextField(blank=True, verbose_name='Observations / Références légales')

    class Meta:
        verbose_name        = 'Tableau de gestion (DUA)'
        verbose_name_plural = 'Tableau de gestion (DUA)'
        ordering            = ['type_document', 'intitule']

    def __str__(self):
        return (
            f"{self.intitule} — "
            f"DUA: {self.duree_courante}+{self.duree_intermediaire} ans "
            f"→ {self.get_sort_final_display()}"
        )

    @property
    def duree_totale(self):
        return self.duree_courante + self.duree_intermediaire


# =============================================================================
# 4. DOCUMENT D'ARCHIVES — MODÈLE CENTRAL (CDC § 5.1 / ISO 15489)
# =============================================================================

class Document(models.Model):
    """
    Document d'archives : unité fondamentale du système.
    Contient toutes les métadonnées ISO 15489, le fichier numérique,
    la localisation physique et les informations de cycle de vie.
    """

    class Statut(models.TextChoices):
        COURANT        = 'COURANT',        'Archive courante'
        INTERMEDIAIRE  = 'INTERMEDIAIRE',  'Archive intermédiaire'
        DEFINITIF      = 'DEFINITIF',      'Archive définitive'
        EN_VERSEMENT   = 'EN_VERSEMENT',   'En cours de versement'
        VERSE          = 'VERSE',          'Versé aux Archives nationales'
        EN_ELIMINATION = 'EN_ELIMINATION', "En cours d'élimination"
        ELIMINE        = 'ELIMINE',        'Éliminé'

    class Confidentialite(models.TextChoices):
        PUBLIC       = 'PUBLIC',       'Public'
        INTERNE      = 'INTERNE',      'Usage interne'
        CONFIDENTIEL = 'CONFIDENTIEL', 'Confidentiel'
        SECRET       = 'SECRET',       'Secret'

    class Support(models.TextChoices):
        NUMERIQUE = 'NUMERIQUE', 'Numérique'
        PAPIER    = 'PAPIER',    'Papier'
        MIXTE     = 'MIXTE',     'Mixte (papier + numérique)'

    class SortFinal(models.TextChoices):
        CONSERVATION = 'CONSERVATION', 'Conservation définitive'
        ELIMINATION  = 'ELIMINATION',  'Élimination'
        TRI          = 'TRI',          'Tri'
        EN_ATTENTE   = 'EN_ATTENTE',   'En attente de décision'

    # --- Identifiant pérenne (généré automatiquement) ---
    identifiant = models.CharField(
        max_length=60, unique=True, editable=False,
        verbose_name='Identifiant unique',
        db_index=True,
        help_text='Format : ENSMG-AAAA-CODE-XXXXXXXX',
    )

    # --- Métadonnées ISO 15489 ---
    titre              = models.CharField(max_length=500, verbose_name='Titre')
    producteur         = models.CharField(max_length=200, verbose_name='Service producteur')
    date_creation      = models.DateField(verbose_name='Date de création du document')
    date_reception     = models.DateField(null=True, blank=True, verbose_name='Date de réception')
    date_enregistrement = models.DateTimeField(auto_now_add=True, verbose_name="Date d'enregistrement dans le système")
    description        = models.TextField(blank=True, verbose_name='Description / Résumé')
    mots_cles          = models.TextField(blank=True, verbose_name='Mots-clés', help_text='Séparés par des virgules')
    langue             = models.CharField(max_length=10, default='fr', verbose_name='Langue')

    # --- Classification ---
    categorie       = models.ForeignKey(CategorieDocument, on_delete=models.PROTECT, verbose_name='Catégorie documentaire')
    plan_classement = models.ForeignKey(PlanClassement, on_delete=models.PROTECT, verbose_name='Cote de classement')

    # --- Gestion ---
    statut          = models.CharField(max_length=20, choices=Statut.choices, default=Statut.COURANT, verbose_name='Statut', db_index=True)
    confidentialite = models.CharField(max_length=20, choices=Confidentialite.choices, default=Confidentialite.INTERNE, verbose_name='Niveau de confidentialité')
    support         = models.CharField(max_length=10, choices=Support.choices, default=Support.NUMERIQUE, verbose_name='Support')

    # --- Fichier numérique ---
    fichier               = models.FileField(upload_to='archives/%Y/%m/', null=True, blank=True, verbose_name='Fichier numérique')
    nom_fichier_original  = models.CharField(max_length=255, blank=True, verbose_name='Nom du fichier original')
    taille_fichier        = models.BigIntegerField(null=True, blank=True, verbose_name='Taille (octets)')
    empreinte_sha256      = models.CharField(max_length=64, blank=True, verbose_name='Empreinte SHA-256', help_text="Garantie d'intégrité du fichier numérique")
    texte_extrait         = models.TextField(blank=True, verbose_name='Texte extrait (OCR / indexation plein texte)')

    # --- Localisation physique (documents papier) ---
    localisation_physique = models.CharField(
        max_length=300, blank=True,
        verbose_name='Localisation physique',
        help_text='Ex : Bâtiment A, Salle 12, Étagère 3, Boîte 7',
    )

    # --- DUA et sort final ---
    tableau_gestion = models.ForeignKey(
        TableauGestion,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Tableau de gestion (DUA)',
    )
    date_fin_dua = models.DateField(
        null=True, blank=True,
        verbose_name='Date de fin de DUA',
        help_text='Calculée automatiquement à partir du tableau de gestion',
    )
    sort_final = models.CharField(
        max_length=20,
        choices=SortFinal.choices,
        default=SortFinal.EN_ATTENTE,
        verbose_name='Sort final',
    )

    # --- Traçabilité ---
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='documents_crees',
        verbose_name='Créé par',
    )
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='documents_modifies',
        verbose_name='Modifié par',
    )
    date_modification = models.DateTimeField(auto_now=True, verbose_name='Dernière modification')

    # --- Corbeille (soft delete) ---
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Mis en corbeille le',
        help_text='Si renseigné, le document est en corbeille (suppression logique). Purge automatique après 30 jours.',
    )

    class Meta:
        verbose_name        = "Document d'archives"
        verbose_name_plural = "Documents d'archives"
        ordering            = ['-date_enregistrement']
        permissions         = [
            ('can_eliminate',          'Peut déclencher une procédure d\'élimination'),
            ('can_verse',              'Peut effectuer un versement'),
            ('can_view_confidentiel',  'Peut consulter les documents confidentiels'),
            ('can_view_secret',        'Peut consulter les documents secrets'),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mémorise le nom du fichier à l'instanciation pour détecter les remplacements
        self._fichier_nom_original = self.fichier.name if self.fichier else None

    def _fichier_a_change(self) -> bool:
        """Retourne True si le fichier a été ajouté ou remplacé depuis le chargement."""
        nom_actuel = self.fichier.name if self.fichier else None
        return nom_actuel != self._fichier_nom_original or not self.empreinte_sha256

    def __str__(self):
        return f"[{self.identifiant}] {self.titre}"

    def save(self, *args, **kwargs):
        from archives.services import DocumentService
        DocumentService.preparer_sauvegarde(self)
        super().save(*args, **kwargs)
        # Met à jour le nom mémorisé après sauvegarde
        self._fichier_nom_original = self.fichier.name if self.fichier else None

    # --- Propriétés utiles ---

    @property
    def est_en_fin_de_dua(self):
        """Vrai si la DUA est échue — déclenche une alerte d'action."""
        if self.date_fin_dua:
            return timezone.now().date() >= self.date_fin_dua
        return False

    @property
    def taille_lisible(self):
        """Taille du fichier dans un format humain (Ko, Mo, Go)."""
        if not self.taille_fichier:
            return '—'
        for unite, seuil in [('Go', 1_073_741_824), ('Mo', 1_048_576), ('Ko', 1024)]:
            if self.taille_fichier >= seuil:
                return f"{self.taille_fichier / seuil:.1f} {unite}"
        return f"{self.taille_fichier} o"


# =============================================================================
# 5. JOURNAL D'AUDIT — MOUVEMENT DOCUMENT (CDC § 5.4 / ISO 15489)
# =============================================================================

class MouvementDocument(models.Model):
    """
    Journal d'audit immuable : trace toutes les actions sur les documents.
    Aucun enregistrement ne doit être modifiable ou supprimable.
    """

    class Action(models.TextChoices):
        CREATION          = 'CREATION',         'Création'
        MODIFICATION      = 'MODIFICATION',     'Modification'
        CONSULTATION      = 'CONSULTATION',     'Consultation'
        CHANGEMENT_STATUT = 'CHANGEMENT_STATUT','Changement de statut'
        VERSEMENT         = 'VERSEMENT',        'Versement'
        ELIMINATION       = 'ELIMINATION',      'Élimination'
        TRANSFERT         = 'TRANSFERT',        'Transfert'
        RESTAURATION      = 'RESTAURATION',     'Restauration'
        TELECHARGEMENT    = 'TELECHARGEMENT',   'Téléchargement'

    document     = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='mouvements', verbose_name='Document')
    action       = models.CharField(max_length=30, choices=Action.choices, verbose_name='Action')
    utilisateur  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Utilisateur')
    date_action  = models.DateTimeField(auto_now_add=True, verbose_name='Date et heure', db_index=True)
    commentaire  = models.TextField(blank=True, verbose_name='Commentaire')
    details      = models.JSONField(default=dict, verbose_name='Détails', help_text='Valeurs avant/après pour les modifications')
    adresse_ip   = models.GenericIPAddressField(null=True, blank=True, verbose_name='Adresse IP')

    class Meta:
        verbose_name        = "Journal d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering            = ['-date_action']
        # Aucun droit de modification ou suppression dans l'admin
        default_permissions = ('add', 'view')

    def __str__(self):
        horodatage = self.date_action.strftime('%d/%m/%Y %H:%M') if self.date_action else '?'
        return f"{self.get_action_display()} — {self.document.identifiant} — {horodatage}"


# =============================================================================
# 6. BORDEREAU DE VERSEMENT (CDC § 5.9 / Loi 2006-19)
# =============================================================================

class BordereauVersement(models.Model):
    """
    Bordereau de versement aux Archives nationales du Sénégal.
    Workflow : Brouillon → En validation → Validé → Exécuté.
    """

    class Statut(models.TextChoices):
        BROUILLON      = 'BROUILLON',      'Brouillon'
        EN_VALIDATION  = 'EN_VALIDATION',  'En attente de validation'
        VALIDE         = 'VALIDE',         'Validé'
        EXECUTE        = 'EXECUTE',        'Exécuté'
        REJETE         = 'REJETE',         'Rejeté'

    numero               = models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')
    date_creation        = models.DateField(auto_now_add=True, verbose_name='Date de création')
    service_versant      = models.CharField(max_length=200, verbose_name='Service versant')
    service_destinataire = models.CharField(max_length=200, default='Service des Archives — ENSMG', verbose_name='Service destinataire')
    statut               = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut')
    exercice             = models.IntegerField(
        null=True, blank=True, db_index=True,
        verbose_name='Exercice (année)',
        help_text='Année budgétaire — auto-détecté depuis les dates de dépôts.',
    )
    # M2M vers les dépôts inclus (auto-généré par service/exercice)
    depots               = models.ManyToManyField(
        'DepotDocument',
        related_name='bordereaux_versement',
        verbose_name='Dépôts inclus',
        blank=True,
    )
    documents            = models.ManyToManyField(Document, related_name='bordereaux_versement', verbose_name='Documents versés', blank=True)
    observations         = models.TextField(blank=True, verbose_name='Observations')
    cree_par             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='bordereaux_versement_crees', verbose_name='Créé par')
    valide_par           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='bordereaux_versement_valides', verbose_name='Validé par')
    date_validation      = models.DateField(null=True, blank=True, verbose_name='Date de validation')

    class Meta:
        verbose_name        = 'Bordereau de versement'
        verbose_name_plural = 'Bordereaux de versement'
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Versement {self.numero} — {self.get_statut_display()}"

    @property
    def nb_documents(self):
        return self.documents.count()


# =============================================================================
# 7. BORDEREAU D'ÉLIMINATION (CDC § 5.9 / Loi 2006-19)
# =============================================================================

class BordereauElimination(models.Model):
    """
    Bordereau d'élimination conforme à la loi sénégalaise 2006-19.
    L'élimination est SUBORDONNÉE au visa de la Direction des Archives du Sénégal (DAS).
    Workflow : Brouillon → En attente de visa DAS → Visa obtenu → Exécuté.
    """

    class Statut(models.TextChoices):
        BROUILLON     = 'BROUILLON',    'Brouillon'
        EN_VALIDATION = 'EN_VALIDATION','En attente de visa archivistique (DAS)'
        VISA_OBTENU   = 'VISA_OBTENU',  'Visa obtenu — Élimination autorisée'
        EXECUTE       = 'EXECUTE',      'Élimination exécutée'
        REJETE        = 'REJETE',       'Rejeté par la DAS'

    numero             = models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')
    date_creation      = models.DateField(auto_now_add=True, verbose_name='Date de création')
    service_producteur = models.CharField(max_length=200, verbose_name='Service producteur')
    statut             = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut')
    documents          = models.ManyToManyField(Document, related_name='bordereaux_elimination', verbose_name='Documents à éliminer')
    motif              = models.TextField(verbose_name="Motif d'élimination")
    observations       = models.TextField(blank=True, verbose_name='Observations')
    cree_par           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='bordereaux_elimination_crees', verbose_name='Créé par')

    # Visa obligatoire de la Direction des Archives du Sénégal
    visa_das           = models.BooleanField(default=False, verbose_name='Visa DAS obtenu', help_text='Visa de la Direction des Archives du Sénégal — obligatoire avant toute élimination')
    date_visa          = models.DateField(null=True, blank=True, verbose_name='Date du visa')
    reference_visa     = models.CharField(max_length=100, blank=True, verbose_name='Référence du visa')
    date_elimination   = models.DateField(null=True, blank=True, verbose_name="Date d'élimination effective")

    class Meta:
        verbose_name        = "Bordereau d'élimination"
        verbose_name_plural = "Bordereaux d'élimination"
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Élimination {self.numero} — {self.get_statut_display()}"

    @property
    def nb_documents(self):
        return self.documents.count()


# =============================================================================
# 8. PROVENANCE EXTERNE (référentiel contrôlé)
# =============================================================================

class ProvenanceExterne(models.Model):
    """
    Référentiel des provenances externes reconnues par l'ENSMG.
    Permet d'identifier l'origine d'un document hors ENSMG (Rectorat, BU, ESP, etc.).
    Géré par l'archiviste/admin via l'interface d'administration.
    """
    code        = models.CharField(max_length=30, unique=True, verbose_name='Code')
    nom         = models.CharField(max_length=200, verbose_name='Nom de l\'organisme')
    description = models.TextField(blank=True, verbose_name='Description')
    actif       = models.BooleanField(default=True, verbose_name='Actif')
    cree_le     = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name        = 'Provenance externe'
        verbose_name_plural = 'Provenances externes'
        ordering            = ['nom']

    def __str__(self):
        return f"[{self.code}] {self.nom}"


# =============================================================================
# 9. DÉPÔT DOCUMENT — VERSEMENT PAR UN AGENT
# =============================================================================

class DepotDocument(models.Model):
    """
    Dépôt d'un document par un agent (personnel, enseignant...).
    Déclenche une notification à l'archiviste.
    Workflow : En attente → Archivé | Rejeté.
    Chaque dépôt génère un numéro de récépissé automatique (preuve légale pour l'agent).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente de traitement'
        ARCHIVE    = 'ARCHIVE',    'Archivé'
        REJETE     = 'REJETE',     'Rejeté'

    numero_recepisse = models.CharField(
        max_length=30, unique=True, editable=False,
        verbose_name='Numéro de récépissé',
        help_text='Généré automatiquement — preuve légale du dépôt.',
    )
    agent          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='depots',
        verbose_name='Agent déposant',
    )
    fichier        = models.FileField(upload_to='depots/%Y/%m/', verbose_name='Fichier déposé')
    titre          = models.CharField(max_length=500, verbose_name='Titre du document')
    date_reception = models.DateField(verbose_name='Date de réception du document')
    categorie      = models.ForeignKey(
        CategorieDocument,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Type de document (optionnel)',
    )
    description    = models.TextField(blank=True, verbose_name='Description / Contexte')
    mots_cles      = models.TextField(blank=True, verbose_name='Mots-clés', help_text='Séparés par des virgules — optionnel, peut être renseigné par l\'archiviste')
    statut         = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name='Statut', db_index=True)
    date_depot     = models.DateTimeField(auto_now_add=True, verbose_name='Date de dépôt')
    traite_par     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='depots_traites',
        verbose_name='Traité par',
    )
    date_traitement  = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    motif_rejet      = models.TextField(blank=True, verbose_name='Motif du rejet')

    # --- Provenance ---
    provenance_interne = models.BooleanField(
        default=True,
        verbose_name='Provenance ENSMG (interne)',
        help_text='Décochez si le document provient d\'un organisme externe (Rectorat, BU, ESP…)',
    )
    provenance_externe = models.ForeignKey(
        'ProvenanceExterne',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Organisme externe',
        help_text='Sélectionnez l\'organisme d\'origine du document',
    )

    document_archive = models.OneToOneField(
        'Document',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='depot_source',
        verbose_name="Document d'archives créé",
    )

    class Meta:
        verbose_name        = 'Dépôt de document'
        verbose_name_plural = 'Dépôts de documents'
        ordering            = ['-date_depot']

    def __str__(self):
        return f"[{self.numero_recepisse}] {self.titre} — {self.get_statut_display()}"

    def save(self, *args, **kwargs):
        if not self.numero_recepisse:
            annee = timezone.now().year
            uid   = uuid.uuid4().hex[:6].upper()
            dept  = ''
            if self.agent_id:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    agent = User.objects.select_related('departement').get(pk=self.agent_id)
                    if agent.departement:
                        dept = agent.departement.code + '-'
                except Exception:
                    pass
            self.numero_recepisse = f"DEP-{annee}-{dept}{uid}"
        super().save(*args, **kwargs)

    @property
    def est_en_attente(self):
        return self.statut == self.Statut.EN_ATTENTE


# =============================================================================
# 9. NOTIFICATION INTERNE
# =============================================================================

class Notification(models.Model):
    """Système de notifications internes déclenché automatiquement sur les événements métier."""

    class Type(models.TextChoices):
        NOUVEAU_DEPOT = 'NOUVEAU_DEPOT', 'Nouveau dépôt à traiter'
        DEPOT_ARCHIVE = 'DEPOT_ARCHIVE', 'Votre dépôt a été archivé'
        DEPOT_REJETE  = 'DEPOT_REJETE',  'Votre dépôt a été rejeté'
        ACCES_ACCORDE = 'ACCES_ACCORDE', 'Accès accordé à un document'
        ACCES_EXPIRE  = 'ACCES_EXPIRE',  'Accès expiré'
        DEMANDE_PRET      = 'DEMANDE_PRET',      'Nouvelle demande de prêt'
        PRET_ACCORDE      = 'PRET_ACCORDE',      'Prêt accordé'
        PRET_REFUSE       = 'PRET_REFUSE',       'Prêt refusé'
        PRET_RAPPEL       = 'PRET_RAPPEL',       'Rappel : retour de prêt attendu'
        PRET_RETARD       = 'PRET_RETARD',       'Prêt en retard'
        ALERTE_DUA        = 'ALERTE_DUA',        'DUA échéant dans 30 jours'
        DUA_ECHUE         = 'DUA_ECHUE',         'DUA échue — action requise'
        INTEGRITE_KO      = 'INTEGRITE_KO',      'Alerte intégrité fichier'
        RECHERCHE_RECUE   = 'RECHERCHE_RECUE',   'Nouvelle demande de recherche documentaire'
        RECHERCHE_ACCORDEE = 'RECHERCHE_ACCORDEE', 'Recherche traitée — document trouvé'
        RECHERCHE_REFUSEE  = 'RECHERCHE_REFUSEE',  'Recherche — document non trouvé'

    destinataire  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Destinataire',
    )
    type          = models.CharField(max_length=30, choices=Type.choices, verbose_name='Type')
    titre         = models.CharField(max_length=200, verbose_name='Titre')
    message       = models.TextField(verbose_name='Message')
    lue           = models.BooleanField(default=False, verbose_name='Lue', db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date', db_index=True)
    url           = models.CharField(max_length=500, blank=True, verbose_name='Lien de redirection')
    depot         = models.ForeignKey('DepotDocument', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Dépôt lié')
    document      = models.ForeignKey('Document',      null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Document lié')

    class Meta:
        verbose_name        = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering            = ['-date_creation']
        default_permissions = ('add', 'view')

    def __str__(self):
        statut = '✓' if self.lue else '●'
        return f"{statut} [{self.get_type_display()}] → {self.destinataire} — {self.titre}"

    def marquer_lue(self):
        if not self.lue:
            self.lue = True
            self.save(update_fields=['lue'])

    @classmethod
    def envoyer(cls, destinataire, type_, titre, message, url='', depot=None, document=None):
        """Raccourci pour créer une notification."""
        return cls.objects.create(
            destinataire=destinataire, type=type_, titre=titre,
            message=message, url=url, depot=depot, document=document,
        )


# =============================================================================
# 10. ACCÈS SPÉCIAL DOCUMENT (ABAC)
# =============================================================================

class AccesDocument(models.Model):
    """
    Accès individuel accordé par l'archiviste à une personne précise pour un document donné.
    Indépendant du rôle (ABAC). Pour les numériques : 24h par défaut, révocable à tout moment.
    Si l'utilisateur est désactivé (is_active=False), ses accès sont automatiquement ignorés.
    """

    class TypeAcces(models.TextChoices):
        LECTURE        = 'LECTURE',        'Lecture seule'
        TELECHARGEMENT = 'TELECHARGEMENT', 'Lecture + Téléchargement'

    document    = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='acces_speciaux', verbose_name='Document')
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='acces_documents', verbose_name='Utilisateur')
    accorde_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='acces_accordes', verbose_name='Accordé par')
    date_debut  = models.DateTimeField(auto_now_add=True, verbose_name="Début de l'accès")
    date_fin    = models.DateTimeField(null=True, blank=True, verbose_name="Fin de l'accès", help_text='Laisser vide pour un accès permanent. 24h par défaut pour les numériques.')
    type_acces  = models.CharField(max_length=20, choices=TypeAcces.choices, default=TypeAcces.LECTURE, verbose_name="Type d'accès")
    actif       = models.BooleanField(default=True, verbose_name='Actif')
    motif       = models.TextField(blank=True, verbose_name="Motif de l'accès")

    class Meta:
        verbose_name        = 'Accès spécial document'
        verbose_name_plural = 'Accès spéciaux documents'
        unique_together     = ('document', 'utilisateur')
        ordering            = ['-date_debut']

    def __str__(self):
        exp = self.date_fin.strftime('%d/%m/%Y %H:%M') if self.date_fin else 'permanent'
        return f"{self.utilisateur} → {self.document.identifiant} ({self.get_type_acces_display()}, jusqu'au {exp})"

    @property
    def est_expire(self):
        if self.date_fin:
            return timezone.now() >= self.date_fin
        return False

    def revoquer(self):
        self.actif = False
        self.save(update_fields=['actif'])


# =============================================================================
# 11. DEMANDE DE PRÊT / ACCÈS NUMÉRIQUE
# =============================================================================

class DemandePret(models.Model):
    """
    Demande formulée par un agent pour accéder à un document hors de ses droits habituels.
    - Physique : génère un PretDocument après validation archiviste.
    - Numérique : génère un AccesDocument de 24h après validation.
    """

    class TypeDemande(models.TextChoices):
        PHYSIQUE  = 'PHYSIQUE',  'Document physique (prêt avec bon)'
        NUMERIQUE = 'NUMERIQUE', 'Document numérique (accès temporaire 24h)'

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente de traitement'
        ACCORDEE   = 'ACCORDEE',   'Accordée'
        REFUSEE    = 'REFUSEE',    'Refusée'
        CLOTUREE   = 'CLOTUREE',   'Clôturée'

    demandeur          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='demandes_pret', verbose_name='Demandeur')
    document           = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='demandes_pret', verbose_name='Document demandé')
    type_demande       = models.CharField(max_length=20, choices=TypeDemande.choices, verbose_name='Type de demande')
    motif              = models.TextField(verbose_name='Motif de la demande')
    statut             = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, verbose_name='Statut', db_index=True)
    date_demande       = models.DateTimeField(auto_now_add=True, verbose_name='Date de la demande')
    date_traitement    = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    traite_par         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='demandes_traitees', verbose_name='Traitée par')
    motif_refus        = models.TextField(blank=True, verbose_name='Motif du refus')
    duree_acces_heures = models.PositiveIntegerField(default=24, verbose_name="Durée d'accès (heures)", help_text='Pour les documents numériques uniquement. Défaut : 24h.')

    class Meta:
        verbose_name        = 'Demande de prêt / accès'
        verbose_name_plural = 'Demandes de prêt / accès'
        ordering            = ['-date_demande']

    def __str__(self):
        return f"[{self.get_type_demande_display()}] {self.demandeur} → {self.document.identifiant} — {self.get_statut_display()}"


# =============================================================================
# 12. PRÊT DE DOCUMENT PHYSIQUE
# =============================================================================

class PretDocument(models.Model):
    """Bon de prêt pour document physique. Cycle : En cours → Retourné (bon de retour)."""

    class Statut(models.TextChoices):
        EN_COURS  = 'EN_COURS',  'En cours'
        RETOURNE  = 'RETOURNE',  'Retourné'
        EN_RETARD = 'EN_RETARD', 'En retard'
        PERDU     = 'PERDU',     'Perdu / Non retourné'

    numero_bon            = models.CharField(max_length=30, unique=True, editable=False, verbose_name='Numéro de bon de prêt')
    demande               = models.OneToOneField(DemandePret, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Demande d'origine")
    document              = models.ForeignKey(Document, on_delete=models.PROTECT, related_name='prets', verbose_name='Document')
    emprunteur            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='prets', verbose_name='Emprunteur')
    accorde_par           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='prets_accordes', verbose_name='Accordé par')
    date_pret             = models.DateField(auto_now_add=True, verbose_name='Date de prêt')
    date_retour_prevue    = models.DateField(verbose_name='Date de retour prévue')
    date_retour_effective = models.DateField(null=True, blank=True, verbose_name='Date de retour effective')
    statut                = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS, verbose_name='Statut', db_index=True)
    observations          = models.TextField(blank=True, verbose_name='Observations')

    class Meta:
        verbose_name        = 'Prêt de document'
        verbose_name_plural = 'Prêts de documents'
        ordering            = ['-date_pret']

    def __str__(self):
        return f"[{self.numero_bon}] {self.emprunteur} — {self.document.identifiant} ({self.get_statut_display()})"

    def save(self, *args, **kwargs):
        if not self.numero_bon:
            annee           = timezone.now().year
            uid             = uuid.uuid4().hex[:6].upper()
            self.numero_bon = f"PRE-{annee}-{uid}"
        super().save(*args, **kwargs)

    @property
    def est_en_retard(self):
        from datetime import date
        return self.statut == self.Statut.EN_COURS and date.today() > self.date_retour_prevue


# =============================================================================
# 13. DEMANDE DE RECHERCHE DOCUMENTAIRE
# =============================================================================

class DemandeRecherche(models.Model):
    """
    Demande de recherche documentaire formulée par un agent qui ne connaît
    pas l'identifiant exact du document. L'archiviste recherche dans les fonds,
    identifie le document et crée directement un prêt numérique — ou refuse.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente de traitement'
        ACCORDEE   = 'ACCORDEE',   'Document trouvé — prêt accordé'
        REFUSEE    = 'REFUSEE',    'Document non trouvé / refusée'

    agent              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='demandes_recherche',
        verbose_name='Agent demandeur',
    )
    categorie          = models.ForeignKey(
        CategorieDocument, null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Catégorie documentaire',
    )
    service_producteur = models.ForeignKey(
        'users.Departement',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recherches_documentaires',
        verbose_name='Service producteur / déposant',
        help_text='Service ou département qui a produit ou déposé le document',
    )
    motif              = models.TextField(verbose_name='Motif de la demande')
    description        = models.TextField(
        verbose_name='Description du document recherché',
        help_text='Titre approximatif, période, contenu, contexte…',
    )
    statut             = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        verbose_name='Statut', db_index=True,
    )
    date_demande       = models.DateTimeField(auto_now_add=True, verbose_name='Date de la demande')
    date_traitement    = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    traite_par         = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recherches_traitees',
        verbose_name='Traitée par',
    )
    motif_refus        = models.TextField(blank=True, verbose_name='Motif du refus / document non trouvé')
    document_fourni    = models.ForeignKey(
        Document, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recherches',
        verbose_name='Document trouvé',
    )
    pret_cree          = models.OneToOneField(
        DemandePret, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recherche_source',
        verbose_name='Demande de prêt créée',
    )

    class Meta:
        verbose_name        = 'Demande de recherche documentaire'
        verbose_name_plural = 'Demandes de recherche documentaire'
        ordering            = ['-date_demande']

    def __str__(self):
        return f"Recherche #{self.pk} — {self.agent} — {self.get_statut_display()}"


# =============================================================================
# 14. RÉTENTION JURIDIQUE (LEGAL HOLD)
# =============================================================================

class RetentionJuridique(models.Model):
    """
    Blocage légal d'un document : même si la DUA est échue, le document
    ne peut être ni éliminé ni versé tant qu'une rétention active existe.
    Ex : document sous scellé judiciaire, audit de la Cour des Comptes.
    """

    document   = models.ForeignKey(Document, on_delete=models.PROTECT, related_name='retentions', verbose_name='Document')
    motif      = models.TextField(verbose_name='Motif de la rétention')
    autorite   = models.CharField(max_length=200, verbose_name='Autorité ordonnante', help_text='Ex : Tribunal régional de Dakar, Cour des Comptes...')
    reference  = models.CharField(max_length=100, blank=True, verbose_name='Référence du texte juridique')
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin   = models.DateField(null=True, blank=True, verbose_name='Date de fin (vide = indéfinie)')
    active     = models.BooleanField(default=True, verbose_name='Active')
    cree_par   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Enregistrée par')

    class Meta:
        verbose_name        = 'Rétention juridique'
        verbose_name_plural = 'Rétentions juridiques'
        ordering            = ['-date_debut']

    def __str__(self):
        etat = 'ACTIVE' if self.active else 'Levée'
        return f"[{etat}] {self.document.identifiant} — {self.autorite}"

    @property
    def est_active(self):
        if not self.active:
            return False
        if self.date_fin:
            return timezone.now().date() <= self.date_fin
        return True


# =============================================================================
# 14. VÉRIFICATION D'INTÉGRITÉ
# =============================================================================

class VerificationIntegrite(models.Model):
    """
    Journal des vérifications périodiques SHA-256 des fichiers numériques.
    Permet de prouver qu'aucun fichier n'a été altéré depuis son archivage.
    """

    class Resultat(models.TextChoices):
        OK     = 'OK',     'Intégrité vérifiée ✓'
        ECHOUE = 'ECHOUE', 'Altération détectée ✗'
        ERREUR = 'ERREUR', 'Erreur technique'

    document             = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='verifications_integrite', verbose_name='Document')
    date_verification    = models.DateTimeField(auto_now_add=True, verbose_name='Date de vérification', db_index=True)
    resultat             = models.CharField(max_length=10, choices=Resultat.choices, verbose_name='Résultat')
    empreinte_calculee   = models.CharField(max_length=64, blank=True, verbose_name='Empreinte SHA-256 calculée')
    empreinte_reference  = models.CharField(max_length=64, blank=True, verbose_name='Empreinte SHA-256 de référence')
    verifie_par          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Vérifié par')
    message              = models.TextField(blank=True, verbose_name='Message / Détails')

    class Meta:
        verbose_name        = "Vérification d'intégrité"
        verbose_name_plural = "Vérifications d'intégrité"
        ordering            = ['-date_verification']
        default_permissions = ('add', 'view')

    def __str__(self):
        return f"{self.get_resultat_display()} — {self.document.identifiant} — {self.date_verification.strftime('%d/%m/%Y %H:%M')}"


# =============================================================================
# 15. TOKEN D'AUDIT TEMPORAIRE (Mode accès contrôlé pour auditeurs)
# =============================================================================

class AuditToken(models.Model):
    """
    Accès temporaire sécurisé pour commissaires aux comptes, inspecteurs CAMES,
    auditeurs MESRI. Limité à un périmètre précis, durée bornée (1–30 jours).
    Workflow : Création → Activation → Expiration automatique.
    """

    class Perimetre(models.TextChoices):
        TOUS          = 'TOUS',          'Tous les documents autorisés'
        CATEGORIE     = 'CATEGORIE',     'Par catégorie documentaire'
        PLAN          = 'PLAN',          'Par plan de classement'
        SELECTION     = 'SELECTION',     'Sélection manuelle'

    token          = models.CharField(max_length=64, unique=True, editable=False, verbose_name='Token d\'accès')
    description    = models.CharField(max_length=300, verbose_name='Objet / Mission d\'audit')
    auditeur_nom   = models.CharField(max_length=200, verbose_name='Nom de l\'auditeur / organisme')
    auditeur_email = models.EmailField(blank=True, verbose_name='Email de l\'auditeur')

    # Périmètre d'accès
    perimetre      = models.CharField(max_length=20, choices=Perimetre.choices, default=Perimetre.TOUS, verbose_name='Périmètre d\'accès')
    categories     = models.ManyToManyField('CategorieDocument', blank=True, verbose_name='Catégories autorisées')
    plans          = models.ManyToManyField('PlanClassement', blank=True, verbose_name='Plans de classement autorisés')
    documents      = models.ManyToManyField('Document', blank=True, related_name='audit_tokens', verbose_name='Documents autorisés (sélection)')

    # Confidentialité maximale accessible
    confidentialite_max = models.CharField(
        max_length=20,
        choices=[('INTERNE','Interne'), ('CONFIDENTIEL','Confidentiel'), ('SECRET','Secret')],
        default='INTERNE',
        verbose_name='Confidentialité maximale accessible',
    )

    # Durée de validité
    date_creation  = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    date_debut     = models.DateTimeField(verbose_name='Valide à partir du')
    date_expiration = models.DateTimeField(verbose_name='Expire le')
    actif          = models.BooleanField(default=True, verbose_name='Actif')

    # Traçabilité
    cree_par       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_tokens_crees', verbose_name='Créé par')
    nb_consultations = models.PositiveIntegerField(default=0, verbose_name='Nombre de consultations')
    derniere_consultation = models.DateTimeField(null=True, blank=True, verbose_name='Dernière consultation')

    class Meta:
        verbose_name        = "Token d'audit"
        verbose_name_plural = "Tokens d'audit"
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Audit — {self.auditeur_nom} — {self.date_expiration.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @property
    def est_valide(self):
        now = timezone.now()
        return self.actif and self.date_debut <= now <= self.date_expiration

    @property
    def jours_restants(self):
        delta = self.date_expiration - timezone.now()
        return max(0, delta.days)


# =============================================================================
# 16. COURRIER (MODULE COURRIER — ARRIVÉE / DÉPART)
# =============================================================================

class Courrier(models.Model):
    """
    Entité indépendante gérant les courriers arrivée et départ du secrétariat.
    - Un courrier DÉPART peut être lié à un courrier ARRIVÉE (en réponse).
    - Cycle de vie : Enregistré → En traitement → Traité → Archivé → Versé/Éliminé.
    - Accessible uniquement aux secrétaires et archivistes.
    """

    class Sens(models.TextChoices):
        ARRIVEE = 'ARRIVEE', 'Arrivée'
        DEPART  = 'DEPART',  'Départ'

    class Statut(models.TextChoices):
        ENREGISTRE    = 'ENREGISTRE',    'Enregistré'
        EN_TRAITEMENT = 'EN_TRAITEMENT', 'En traitement'
        TRAITE        = 'TRAITE',        'Traité'
        ARCHIVE       = 'ARCHIVE',       'Archivé'
        VERSE         = 'VERSE',         'Versé aux Archives nationales'
        ELIMINE       = 'ELIMINE',       'Éliminé'

    class Confidentialite(models.TextChoices):
        PUBLIC       = 'PUBLIC',       'Public'
        INTERNE      = 'INTERNE',      'Usage interne'
        CONFIDENTIEL = 'CONFIDENTIEL', 'Confidentiel'

    class SortFinal(models.TextChoices):
        CONSERVATION = 'CONSERVATION', 'Conservation définitive'
        ELIMINATION  = 'ELIMINATION',  'Élimination'
        TRI          = 'TRI',          'Tri'
        EN_ATTENTE   = 'EN_ATTENTE',   'En attente de décision'

    # --- Identifiant pérenne ---
    numero_enregistrement = models.CharField(
        max_length=40, unique=True, editable=False,
        verbose_name='Numéro d\'enregistrement',
        help_text='Format : ENSMG-ARR-AAAA-XXXXX ou ENSMG-DEP-AAAA-XXXXX',
        db_index=True,
    )

    # --- Caractéristiques du courrier ---
    sens              = models.CharField(max_length=10, choices=Sens.choices, verbose_name='Sens', db_index=True)
    objet             = models.CharField(max_length=500, verbose_name='Objet')
    date_courrier     = models.DateField(verbose_name='Date du courrier')
    date_enregistrement = models.DateTimeField(auto_now_add=True, verbose_name='Date d\'enregistrement', db_index=True)
    reference_expediteur = models.CharField(max_length=100, blank=True, verbose_name='Référence expéditeur',
                                             help_text='Référence figurant sur le document original')
    expediteur        = models.CharField(max_length=300, verbose_name='Expéditeur')
    destinataire      = models.CharField(max_length=300, verbose_name='Destinataire')
    service_interne   = models.CharField(max_length=200, blank=True, verbose_name='Service interne concerné',
                                          help_text='Service ENSMG destinataire (arrivée) ou expéditeur (départ)')
    ampliation        = models.TextField(blank=True, verbose_name='Ampliation',
                                          help_text='Services mis en copie, séparés par des virgules')
    instructions      = models.TextField(blank=True, verbose_name='Instructions de traitement')
    description       = models.TextField(blank=True, verbose_name='Description / Résumé')
    mots_cles         = models.TextField(blank=True, verbose_name='Mots-clés', help_text='Séparés par des virgules')

    # --- Lien réponse (DÉPART → ARRIVÉE) ---
    en_reponse_a = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reponses',
        limit_choices_to={'sens': 'ARRIVEE'},
        verbose_name='En réponse au courrier arrivée',
        help_text='Renseigner uniquement pour un courrier DÉPART qui répond à un courrier ARRIVÉE',
    )

    # --- Délai de réponse (ARRIVÉE seulement) ---
    delai_reponse = models.DateField(
        null=True, blank=True,
        verbose_name='Délai de réponse',
        help_text='Date limite de réponse attendue (courrier arrivée uniquement)',
    )
    accuse_reception = models.BooleanField(
        default=False,
        verbose_name='Accusé de réception envoyé',
    )

    # --- Fichier numérique ---
    fichier              = models.FileField(upload_to='courriers/%Y/%m/', null=True, blank=True, verbose_name='Fichier numérique (scan)')
    nom_fichier_original = models.CharField(max_length=255, blank=True, verbose_name='Nom du fichier original')
    taille_fichier       = models.BigIntegerField(null=True, blank=True, verbose_name='Taille (octets)')
    empreinte_sha256     = models.CharField(max_length=64, blank=True, verbose_name='Empreinte SHA-256')

    # --- Localisation physique ---
    localisation_physique = models.CharField(
        max_length=300, blank=True,
        verbose_name='Localisation physique',
        help_text='Ex : Classeur n°3, Registre 2026, Intercalaire Mai',
    )

    # --- Gestion ---
    statut          = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ENREGISTRE, verbose_name='Statut', db_index=True)
    confidentialite = models.CharField(max_length=20, choices=Confidentialite.choices, default=Confidentialite.INTERNE, verbose_name='Confidentialité')

    # --- DUA et sort final ---
    tableau_gestion = models.ForeignKey(
        TableauGestion,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Tableau de gestion (DUA)',
    )
    date_fin_dua = models.DateField(null=True, blank=True, verbose_name='Date de fin de DUA')
    sort_final   = models.CharField(max_length=20, choices=SortFinal.choices, default=SortFinal.EN_ATTENTE, verbose_name='Sort final')

    # --- Traçabilité ---
    cree_par    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='courriers_crees', verbose_name='Enregistré par',
    )
    traite_par  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='courriers_traites', verbose_name='Traité par',
    )
    date_traitement = models.DateTimeField(null=True, blank=True, verbose_name='Date de traitement')
    date_archivage  = models.DateTimeField(null=True, blank=True, verbose_name='Date d\'archivage')

    # --- Corbeille (soft delete) ---
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Mis en corbeille le',
        help_text='Suppression logique — purge automatique après 30 jours.',
    )

    class Meta:
        verbose_name        = 'Courrier'
        verbose_name_plural = 'Courriers'
        ordering            = ['-date_enregistrement']
        permissions         = [
            ('can_enregistrer_courrier', 'Peut enregistrer un courrier'),
            ('can_traiter_courrier',     'Peut traiter un courrier'),
            ('can_archiver_courrier',    'Peut archiver un courrier'),
            ('can_verse_courrier',       'Peut verser des courriers'),
            ('can_eliminer_courrier',    'Peut éliminer des courriers'),
        ]

    def __str__(self):
        return f"[{self.numero_enregistrement}] {self.objet[:80]}"

    def save(self, *args, **kwargs):
        # 1. Génération du numéro d'enregistrement pérenne
        if not self.numero_enregistrement:
            annee   = self.date_courrier.year if self.date_courrier else timezone.now().year
            prefix  = 'ARR' if self.sens == 'ARRIVEE' else 'DEP'
            uid     = uuid.uuid4().hex[:5].upper()
            self.numero_enregistrement = f"ENSMG-{prefix}-{annee}-{uid}"

        # 2. Calcul automatique de la date de fin de DUA
        if self.tableau_gestion and self.date_courrier and not self.date_fin_dua:
            duree = self.tableau_gestion.duree_totale
            try:
                self.date_fin_dua = self.date_courrier.replace(
                    year=self.date_courrier.year + duree
                )
            except ValueError:
                self.date_fin_dua = self.date_courrier.replace(
                    year=self.date_courrier.year + duree, day=28
                )

        # 3. Empreinte SHA-256 et métadonnées du fichier
        if self.fichier and not self.empreinte_sha256:
            try:
                sha256 = hashlib.sha256()
                for chunk in self.fichier.chunks():
                    sha256.update(chunk)
                self.empreinte_sha256     = sha256.hexdigest()
                self.taille_fichier       = self.fichier.size
                self.nom_fichier_original = self.fichier.name.split('/')[-1]
            except Exception:
                pass

        super().save(*args, **kwargs)

    @property
    def est_en_retard(self):
        """Vrai si le délai de réponse est dépassé et le courrier non traité."""
        if self.delai_reponse and self.statut in ('ENREGISTRE', 'EN_TRAITEMENT'):
            return timezone.now().date() > self.delai_reponse
        return False

    @property
    def est_en_fin_de_dua(self):
        if self.date_fin_dua:
            return timezone.now().date() >= self.date_fin_dua
        return False

    @property
    def taille_lisible(self):
        if not self.taille_fichier:
            return '—'
        for unite, seuil in [('Go', 1_073_741_824), ('Mo', 1_048_576), ('Ko', 1024)]:
            if self.taille_fichier >= seuil:
                return f"{self.taille_fichier / seuil:.1f} {unite}"
        return f"{self.taille_fichier} o"


# =============================================================================
# 17. JOURNAL D'AUDIT — MOUVEMENT COURRIER
# =============================================================================

class MouvementCourrier(models.Model):
    """
    Journal d'audit immuable pour les courriers.
    Trace toutes les actions : enregistrement, consultation, traitement, archivage, etc.
    """

    class Action(models.TextChoices):
        ENREGISTREMENT = 'ENREGISTREMENT', 'Enregistrement'
        MODIFICATION   = 'MODIFICATION',   'Modification'
        CONSULTATION   = 'CONSULTATION',   'Consultation'
        TRAITEMENT     = 'TRAITEMENT',     'Traitement'
        ARCHIVAGE      = 'ARCHIVAGE',      'Archivage'
        VERSEMENT      = 'VERSEMENT',      'Versement'
        ELIMINATION    = 'ELIMINATION',    'Élimination'
        RESTAURATION   = 'RESTAURATION',   'Restauration depuis la corbeille'
        TELECHARGEMENT = 'TELECHARGEMENT', 'Téléchargement'

    courrier    = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name='mouvements', verbose_name='Courrier')
    action      = models.CharField(max_length=30, choices=Action.choices, verbose_name='Action')
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Utilisateur')
    date_action = models.DateTimeField(auto_now_add=True, verbose_name='Date et heure', db_index=True)
    commentaire = models.TextField(blank=True, verbose_name='Commentaire')
    details     = models.JSONField(default=dict, verbose_name='Détails (avant/après)')
    adresse_ip  = models.GenericIPAddressField(null=True, blank=True, verbose_name='Adresse IP')

    class Meta:
        verbose_name        = "Journal d'audit — Courrier"
        verbose_name_plural = "Journal d'audit — Courriers"
        ordering            = ['-date_action']
        default_permissions = ('add', 'view')

    def __str__(self):
        h = self.date_action.strftime('%d/%m/%Y %H:%M') if self.date_action else '?'
        return f"{self.get_action_display()} — {self.courrier.numero_enregistrement} — {h}"


# =============================================================================
# 18. BORDEREAU DE VERSEMENT — COURRIERS (Loi 2006-19)
# =============================================================================

class BordereauVersementCourrier(models.Model):
    """
    Bordereau de versement des courriers aux Archives nationales du Sénégal.
    Workflow identique aux documents : Brouillon → En validation → Validé → Exécuté.
    Créé exclusivement par l'archiviste.
    """

    class Statut(models.TextChoices):
        BROUILLON     = 'BROUILLON',     'Brouillon'
        EN_VALIDATION = 'EN_VALIDATION', 'En attente de validation'
        VALIDE        = 'VALIDE',        'Validé'
        EXECUTE       = 'EXECUTE',       'Exécuté'
        REJETE        = 'REJETE',        'Rejeté'

    numero               = models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')
    date_creation        = models.DateField(auto_now_add=True, verbose_name='Date de création')
    service_versant      = models.CharField(max_length=200, default='Secrétariat ENSMG', verbose_name='Service versant')
    service_destinataire = models.CharField(max_length=200, default='Archives nationales du Sénégal', verbose_name='Service destinataire')
    statut               = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut')
    courriers            = models.ManyToManyField(Courrier, related_name='bordereaux_versement', verbose_name='Courriers versés')
    observations         = models.TextField(blank=True, verbose_name='Observations')
    cree_par             = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='bv_courriers_crees', verbose_name='Créé par',
    )
    valide_par  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bv_courriers_valides', verbose_name='Validé par',
    )
    date_validation = models.DateField(null=True, blank=True, verbose_name='Date de validation')

    class Meta:
        verbose_name        = 'Bordereau de versement (Courriers)'
        verbose_name_plural = 'Bordereaux de versement (Courriers)'
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Versement courriers {self.numero} — {self.get_statut_display()}"

    @property
    def nb_courriers(self):
        return self.courriers.count()


# =============================================================================
# 19. BORDEREAU D'ÉLIMINATION — COURRIERS (Loi 2006-19)
# =============================================================================

class BordereauEliminationCourrier(models.Model):
    """
    Bordereau d'élimination des courriers.
    Visa DAS obligatoire avant toute destruction, conformément à la loi 2006-19.
    Workflow : Brouillon → En validation → Visa obtenu → Exécuté.
    Créé exclusivement par l'archiviste.
    """

    class Statut(models.TextChoices):
        BROUILLON     = 'BROUILLON',     'Brouillon'
        EN_VALIDATION = 'EN_VALIDATION', 'En attente de visa archivistique (DAS)'
        VISA_OBTENU   = 'VISA_OBTENU',   'Visa obtenu — Élimination autorisée'
        EXECUTE       = 'EXECUTE',       'Élimination exécutée'
        REJETE        = 'REJETE',        'Rejeté par la DAS'

    numero             = models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')
    date_creation      = models.DateField(auto_now_add=True, verbose_name='Date de création')
    service_producteur = models.CharField(max_length=200, default='Secrétariat ENSMG', verbose_name='Service producteur')
    statut             = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut')
    courriers          = models.ManyToManyField(Courrier, related_name='bordereaux_elimination', verbose_name='Courriers à éliminer')
    motif              = models.TextField(verbose_name="Motif d'élimination")
    observations       = models.TextField(blank=True, verbose_name='Observations')
    cree_par           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='be_courriers_crees', verbose_name='Créé par',
    )
    # Visa obligatoire DAS
    visa_das        = models.BooleanField(default=False, verbose_name='Visa DAS obtenu')
    date_visa       = models.DateField(null=True, blank=True, verbose_name='Date du visa')
    reference_visa  = models.CharField(max_length=100, blank=True, verbose_name='Référence du visa')
    date_elimination = models.DateField(null=True, blank=True, verbose_name="Date d'élimination effective")

    class Meta:
        verbose_name        = "Bordereau d'élimination (Courriers)"
        verbose_name_plural = "Bordereaux d'élimination (Courriers)"
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Élimination courriers {self.numero} — {self.get_statut_display()}"

    @property
    def nb_courriers(self):
        return self.courriers.count()


# =============================================================================
# 20. MESSAGERIE INTERNE ENTRE AGENTS
# =============================================================================

class Message(models.Model):
    """
    Messagerie interne entre agents et archivistes de l'ENSMG.
    - Un message peut avoir plusieurs destinataires.
    - Les réponses sont chaînées via `parent`.
    - Chaque destinataire a son propre statut lu/non-lu et corbeille.
    - Peut être lié à un Document ou un Courrier (contexte métier).
    """

    expediteur    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='messages_envoyes',
        verbose_name='Expéditeur',
    )
    destinataires = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MessageDestinataire',
        related_name='messages_recus',
        verbose_name='Destinataires',
    )
    objet      = models.CharField(max_length=300, verbose_name='Objet')
    corps      = models.TextField(verbose_name='Corps du message')
    date_envoi = models.DateTimeField(auto_now_add=True, verbose_name='Date d\'envoi', db_index=True)

    # Pièce jointe légère (optionnel)
    piece_jointe     = models.FileField(upload_to='messagerie/%Y/%m/', null=True, blank=True, verbose_name='Pièce jointe')
    nom_piece_jointe = models.CharField(max_length=255, blank=True, verbose_name='Nom du fichier joint')

    # Fil de discussion (réponses chaînées)
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reponses',
        verbose_name='En réponse à',
    )

    # Liens optionnels vers les entités métier
    document = models.ForeignKey(
        'Document', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='messages_lies',
        verbose_name='Document lié',
    )
    courrier = models.ForeignKey(
        'Courrier', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='messages_lies',
        verbose_name='Courrier lié',
    )

    class Meta:
        verbose_name        = 'Message interne'
        verbose_name_plural = 'Messages internes'
        ordering            = ['-date_envoi']
        default_permissions = ('add', 'view')

    def __str__(self):
        return f"[{self.date_envoi.strftime('%d/%m/%Y %H:%M')}] {self.expediteur} — {self.objet[:60]}"

    def save(self, *args, **kwargs):
        if self.piece_jointe and not self.nom_piece_jointe:
            self.nom_piece_jointe = self.piece_jointe.name.split('/')[-1]
        super().save(*args, **kwargs)

    @property
    def est_reponse(self):
        return self.parent_id is not None

    @property
    def nb_reponses(self):
        return self.reponses.count()


class MessageDestinataire(models.Model):
    """
    Table de liaison Message ↔ Destinataire.
    Stocke le statut individuel : lu, date de lecture, corbeille.
    """
    message      = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name='Message')
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Destinataire',
    )
    lu           = models.BooleanField(default=False, verbose_name='Lu', db_index=True)
    date_lecture = models.DateTimeField(null=True, blank=True, verbose_name='Date de lecture')
    en_corbeille = models.BooleanField(default=False, verbose_name='En corbeille', db_index=True)

    class Meta:
        verbose_name        = 'Destinataire du message'
        verbose_name_plural = 'Destinataires des messages'
        unique_together     = ('message', 'destinataire')
        ordering            = ['-message__date_envoi']

    def __str__(self):
        statut = '✓' if self.lu else '●'
        return f"{statut} {self.destinataire} ← {self.message.objet[:40]}"

    def marquer_lu(self):
        if not self.lu:
            self.lu = True
            self.date_lecture = timezone.now()
            self.save(update_fields=['lu', 'date_lecture'])
