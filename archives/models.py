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

    code        = models.CharField(max_length=10, choices=Code.choices, unique=True, verbose_name='Code')
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

    def __str__(self):
        return f"[{self.identifiant}] {self.titre}"

    # --- Logique métier dans save() ---

    def save(self, *args, **kwargs):
        # 1. Génération de l'identifiant pérenne (unique, immuable)
        if not self.identifiant:
            annee       = self.date_creation.year if self.date_creation else timezone.now().year
            code_cat    = self.categorie.code if self.categorie_id else 'GEN'
            uid         = uuid.uuid4().hex[:8].upper()
            self.identifiant = f"ENSMG-{annee}-{code_cat}-{uid}"

        # 2. Calcul automatique de la date de fin de DUA
        if self.tableau_gestion and self.date_creation and not self.date_fin_dua:
            duree = self.tableau_gestion.duree_totale
            try:
                self.date_fin_dua = self.date_creation.replace(
                    year=self.date_creation.year + duree
                )
            except ValueError:
                # Cas du 29 février sur une année non bissextile
                self.date_fin_dua = self.date_creation.replace(
                    year=self.date_creation.year + duree, day=28
                )

        # 3. Calcul de l'empreinte SHA-256 et métadonnées du fichier
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

    numero              = models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')
    date_creation       = models.DateField(auto_now_add=True, verbose_name='Date de création')
    service_versant     = models.CharField(max_length=200, verbose_name='Service versant')
    service_destinataire = models.CharField(max_length=200, default='Archives nationales du Sénégal', verbose_name='Service destinataire')
    statut              = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON, verbose_name='Statut')
    documents           = models.ManyToManyField(Document, related_name='bordereaux_versement', verbose_name='Documents versés')
    observations        = models.TextField(blank=True, verbose_name='Observations')
    cree_par            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='bordereaux_versement_crees', verbose_name='Créé par')
    valide_par          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='bordereaux_versement_valides', verbose_name='Validé par')
    date_validation     = models.DateField(null=True, blank=True, verbose_name='Date de validation')

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
# 8. DÉPÔT DOCUMENT — VERSEMENT PAR UN AGENT
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
