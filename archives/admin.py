"""
Configuration de l'interface d'administration Django — Archives ENSMG.
Intègre le contrôle d'accès basé sur les rôles (RBAC).
"""

from django.contrib import admin
from django.utils.html import format_html, mark_safe

from .models import (
    CategorieDocument,
    PlanClassement,
    TableauGestion,
    Document,
    MouvementDocument,
    BordereauVersement,
    BordereauElimination,
    DepotDocument,
    Notification,
    AccesDocument,
    DemandePret,
    PretDocument,
    RetentionJuridique,
    VerificationIntegrite,
)
from .permissions import (
    RBACAdminMixin,
    LectureSeuleAdminMixin,
    a_acces_gestion,
    a_acces_lecture_etendue,
    est_admin,
    est_archiviste,
    est_direction,
    get_confidentialites_autorisees,
    peut_voir_document,
)


# =============================================================================
# CATÉGORIES DOCUMENTAIRES
# =============================================================================

@admin.register(CategorieDocument)
class CategorieDocumentAdmin(LectureSeuleAdminMixin, admin.ModelAdmin):
    list_display  = ('code', 'nom', 'description')
    search_fields = ('code', 'nom')
    ordering      = ('code',)


# =============================================================================
# PLAN DE CLASSEMENT
# =============================================================================

@admin.register(PlanClassement)
class PlanClassementAdmin(LectureSeuleAdminMixin, admin.ModelAdmin):
    list_display  = ('code', 'intitule', 'niveau_badge', 'categorie', 'parent', 'actif')
    list_filter   = ('niveau', 'actif', 'categorie')
    search_fields = ('code', 'intitule')
    ordering      = ('code',)
    list_editable = ('actif',)

    NIVEAU_COLORS = {
        1: '#1d4ed8',
        2: '#0284c7',
        3: '#0891b2',
        4: '#059669',
    }

    def get_list_editable(self, request):
        if a_acces_gestion(request.user):
            return ('actif',)
        return ()

    @admin.display(description='Niveau')
    def niveau_badge(self, obj):
        color = self.NIVEAU_COLORS.get(obj.niveau, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:0.82em;">{}</span>',
            color, obj.get_niveau_display(),
        )


# =============================================================================
# TABLEAU DE GESTION (DUA)
# =============================================================================

@admin.register(TableauGestion)
class TableauGestionAdmin(LectureSeuleAdminMixin, admin.ModelAdmin):
    list_display  = ('intitule', 'type_document', 'duree_courante', 'duree_intermediaire', 'duree_totale_aff', 'sort_final_badge')
    list_filter   = ('sort_final', 'type_document')
    search_fields = ('intitule', 'observations')
    ordering      = ('type_document', 'intitule')

    SORT_COLORS = {
        'CONSERVATION': ('#059669', '#fff'),
        'ELIMINATION':  ('#dc2626', '#fff'),
        'TRI':          ('#d97706', '#fff'),
    }

    @admin.display(description='DUA totale')
    def duree_totale_aff(self, obj):
        return f"{obj.duree_totale} ans"

    @admin.display(description='Sort final')
    def sort_final_badge(self, obj):
        bg, fg = self.SORT_COLORS.get(obj.sort_final, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.82em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_sort_final_display(),
        )


# =============================================================================
# DOCUMENT D'ARCHIVES
# =============================================================================

class MouvementInline(admin.TabularInline):
    model           = MouvementDocument
    extra           = 0
    readonly_fields = ('action', 'utilisateur', 'date_action', 'commentaire', 'adresse_ip')
    can_delete      = False
    max_num         = 0
    ordering        = ('-date_action',)
    verbose_name        = "Entrée du journal d'audit"
    verbose_name_plural = "Journal d'audit"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'identifiant', 'titre_tronque', 'categorie', 'plan_classement',
        'statut_badge', 'confidentialite_badge', 'support',
        'dua_alerte', 'date_creation', 'cree_par',
    )
    list_filter   = ('statut', 'confidentialite', 'support', 'categorie', 'sort_final')
    search_fields = ('identifiant', 'titre', 'producteur', 'mots_cles', 'description')
    date_hierarchy = 'date_creation'
    ordering      = ('-date_enregistrement',)
    readonly_fields = (
        'identifiant', 'date_enregistrement', 'date_modification',
        'empreinte_sha256', 'taille_fichier', 'nom_fichier_original',
        'cree_par', 'modifie_par',
    )
    inlines = [MouvementInline]

    fieldsets = (
        ('Identification', {
            'fields': ('identifiant', 'titre', 'producteur', 'description', 'mots_cles', 'langue'),
        }),
        ('Classification', {
            'fields': ('categorie', 'plan_classement'),
        }),
        ('Gestion et statut', {
            'fields': ('statut', 'confidentialite', 'support', 'localisation_physique'),
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_reception', 'date_enregistrement', 'date_modification'),
        }),
        ('Fichier numérique', {
            'fields': ('fichier', 'nom_fichier_original', 'taille_fichier', 'empreinte_sha256'),
            'classes': ('collapse',),
        }),
        ('Cycle de vie (DUA)', {
            'fields': ('tableau_gestion', 'date_fin_dua', 'sort_final'),
        }),
        ('Traçabilité', {
            'fields': ('cree_par', 'modifie_par'),
            'classes': ('collapse',),
        }),
    )

    # ── Couleurs ─────────────────────────────────────────────────────────────

    STATUT_COLORS = {
        'COURANT':        ('#2563eb', '#fff'),
        'INTERMEDIAIRE':  ('#7c3aed', '#fff'),
        'DEFINITIF':      ('#059669', '#fff'),
        'EN_VERSEMENT':   ('#d97706', '#fff'),
        'VERSE':          ('#065f46', '#fff'),
        'EN_ELIMINATION': ('#dc2626', '#fff'),
        'ELIMINE':        ('#374151', '#fff'),
    }
    CONF_COLORS = {
        'PUBLIC':       ('#6b7280', '#fff'),
        'INTERNE':      ('#0284c7', '#fff'),
        'CONFIDENTIEL': ('#d97706', '#fff'),
        'SECRET':       ('#dc2626', '#fff'),
    }

    # ── RBAC : filtrage du queryset selon le rôle ────────────────────────────

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if est_admin(user):
            return qs

        niveaux = get_confidentialites_autorisees(user)
        qs = qs.filter(confidentialite__in=niveaux)

        # Le Personnel voit uniquement les documents de son propre département (INTERNE)
        from users.models import CustomUser
        if user.role == CustomUser.Role.PERSONNEL and user.departement:
            from django.db.models import Q
            qs = qs.filter(
                Q(confidentialite='PUBLIC') |
                Q(confidentialite='INTERNE', producteur__icontains=user.departement.nom)
            )

        # L'Enseignant voit uniquement les documents publics
        if user.role == CustomUser.Role.ENSEIGNANT:
            qs = qs.filter(confidentialite='PUBLIC')

        return qs

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return request.user.is_authenticated
        return peut_voir_document(request.user, obj)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    # ── Colonnes d'affichage ─────────────────────────────────────────────────

    @admin.display(description='Titre')
    def titre_tronque(self, obj):
        return obj.titre[:60] + '…' if len(obj.titre) > 60 else obj.titre

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        bg, fg = self.STATUT_COLORS.get(obj.statut, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_statut_display(),
        )

    @admin.display(description='Confidentialité')
    def confidentialite_badge(self, obj):
        bg, fg = self.CONF_COLORS.get(obj.confidentialite, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_confidentialite_display(),
        )

    @admin.display(description='DUA')
    def dua_alerte(self, obj):
        if not obj.date_fin_dua:
            return mark_safe('<span style="color:#9ca3af">—</span>')
        if obj.est_en_fin_de_dua:
            return format_html(
                '<span style="color:#dc2626;font-weight:bold" title="DUA échue le {}">⚠ Échue</span>',
                obj.date_fin_dua.strftime('%d/%m/%Y'),
            )
        return format_html(
            '<span style="color:#059669" title="DUA échue le {}">✓ {}</span>',
            obj.date_fin_dua.strftime('%d/%m/%Y'),
            obj.date_fin_dua.strftime('%d/%m/%Y'),
        )

    # ── Sauvegarde avec traçabilité automatique ──────────────────────────────

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        obj.modifie_par = request.user
        super().save_model(request, obj, form, change)
        action = MouvementDocument.Action.MODIFICATION if change else MouvementDocument.Action.CREATION
        MouvementDocument.objects.create(
            document    = obj,
            action      = action,
            utilisateur = request.user,
            commentaire = 'Via interface d\'administration',
            adresse_ip  = request.META.get('REMOTE_ADDR'),
        )


# =============================================================================
# JOURNAL D'AUDIT — LECTURE SEULE POUR TOUS
# =============================================================================

@admin.register(MouvementDocument)
class MouvementDocumentAdmin(admin.ModelAdmin):
    list_display  = ('date_action', 'action_badge', 'document', 'utilisateur', 'commentaire_court', 'adresse_ip')
    list_filter   = ('action', 'date_action')
    search_fields = ('document__identifiant', 'document__titre', 'utilisateur__username', 'commentaire')
    date_hierarchy = 'date_action'
    readonly_fields = ('document', 'action', 'utilisateur', 'date_action', 'commentaire', 'details', 'adresse_ip')

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    ACTION_COLORS = {
        'CREATION':          ('#059669', '#fff'),
        'MODIFICATION':      ('#2563eb', '#fff'),
        'CONSULTATION':      ('#6b7280', '#fff'),
        'CHANGEMENT_STATUT': ('#7c3aed', '#fff'),
        'VERSEMENT':         ('#0284c7', '#fff'),
        'ELIMINATION':       ('#dc2626', '#fff'),
        'TELECHARGEMENT':    ('#d97706', '#fff'),
    }

    @admin.display(description='Action')
    def action_badge(self, obj):
        bg, fg = self.ACTION_COLORS.get(obj.action, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_action_display(),
        )

    @admin.display(description='Commentaire')
    def commentaire_court(self, obj):
        return obj.commentaire[:50] + '…' if len(obj.commentaire) > 50 else obj.commentaire or '—'


# =============================================================================
# BORDEREAUX DE VERSEMENT
# =============================================================================

@admin.register(BordereauVersement)
class BordereauVersementAdmin(admin.ModelAdmin):
    list_display      = ('numero', 'service_versant', 'service_destinataire', 'nb_docs', 'statut_badge', 'date_creation', 'cree_par')
    list_filter       = ('statut',)
    search_fields     = ('numero', 'service_versant', 'observations')
    readonly_fields   = ('date_creation', 'cree_par')
    filter_horizontal = ('documents',)

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        # La Direction peut valider mais pas modifier le contenu
        if est_direction(request.user) and obj:
            return obj.statut == 'EN_VALIDATION'
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    STATUT_COLORS = {
        'BROUILLON':     ('#6b7280', '#fff'),
        'EN_VALIDATION': ('#d97706', '#fff'),
        'VALIDE':        ('#2563eb', '#fff'),
        'EXECUTE':       ('#059669', '#fff'),
        'REJETE':        ('#dc2626', '#fff'),
    }

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        bg, fg = self.STATUT_COLORS.get(obj.statut, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.82em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_statut_display(),
        )

    @admin.display(description='Documents')
    def nb_docs(self, obj):
        return obj.documents.count()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


# =============================================================================
# BORDEREAUX D'ÉLIMINATION
# =============================================================================

@admin.register(BordereauElimination)
class BordereauEliminationAdmin(admin.ModelAdmin):
    list_display      = ('numero', 'service_producteur', 'nb_docs', 'statut_badge', 'visa_das', 'date_visa', 'date_creation', 'cree_par')
    list_filter       = ('statut', 'visa_das')
    search_fields     = ('numero', 'service_producteur', 'motif', 'reference_visa')
    readonly_fields   = ('date_creation', 'cree_par')
    filter_horizontal = ('documents',)

    fieldsets = (
        ('Identification', {
            'fields': ('numero', 'service_producteur', 'statut', 'motif', 'observations'),
        }),
        ('Documents concernés', {
            'fields': ('documents',),
        }),
        ('Visa archivistique (DAS)', {
            'fields': ('visa_das', 'date_visa', 'reference_visa'),
            'description': '⚠ L\'élimination est subordonnée au visa de la Direction des Archives du Sénégal (Loi 2006-19 art. 16).',
        }),
        ('Exécution', {
            'fields': ('date_elimination',),
        }),
        ('Traçabilité', {
            'fields': ('cree_par', 'date_creation'),
            'classes': ('collapse',),
        }),
    )

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        if est_direction(request.user) and obj:
            return obj.statut == 'EN_VALIDATION'
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    STATUT_COLORS = {
        'BROUILLON':     ('#6b7280', '#fff'),
        'EN_VALIDATION': ('#d97706', '#fff'),
        'VISA_OBTENU':   ('#2563eb', '#fff'),
        'EXECUTE':       ('#059669', '#fff'),
        'REJETE':        ('#dc2626', '#fff'),
    }

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        bg, fg = self.STATUT_COLORS.get(obj.statut, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.82em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_statut_display(),
        )

    @admin.display(description='Documents')
    def nb_docs(self, obj):
        return obj.documents.count()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


# =============================================================================
# DÉPÔTS DE DOCUMENTS (agents → archiviste)
# =============================================================================

@admin.register(DepotDocument)
class DepotDocumentAdmin(admin.ModelAdmin):
    list_display  = ('numero_recepisse', 'titre_court', 'agent', 'categorie', 'statut_badge', 'date_depot', 'traite_par')
    list_filter   = ('statut', 'categorie', 'date_depot')
    search_fields = ('numero_recepisse', 'titre', 'agent__username', 'agent__last_name')
    date_hierarchy = 'date_depot'
    readonly_fields = ('numero_recepisse', 'date_depot', 'date_traitement', 'agent')

    fieldsets = (
        ('Récépissé', {
            'fields': ('numero_recepisse', 'agent', 'date_depot'),
        }),
        ('Document déposé', {
            'fields': ('fichier', 'titre', 'date_reception', 'categorie', 'description'),
        }),
        ('Traitement archivistique', {
            'fields': ('statut', 'traite_par', 'date_traitement', 'motif_rejet', 'document_archive'),
        }),
    )

    STATUT_COLORS = {
        'EN_ATTENTE': ('#d97706', '#fff'),
        'ARCHIVE':    ('#059669', '#fff'),
        'REJETE':     ('#dc2626', '#fff'),
    }

    def has_view_permission(self, request, obj=None):
        # L'agent voit ses propres dépôts ; archiviste/admin voient tout
        if a_acces_gestion(request.user):
            return True
        if obj is not None:
            return obj.agent_id == request.user.pk
        return request.user.is_authenticated

    def has_add_permission(self, request):
        return request.user.is_authenticated and request.user.is_active

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if a_acces_gestion(request.user):
            return qs
        return qs.filter(agent=request.user)

    @admin.display(description='Titre')
    def titre_court(self, obj):
        return obj.titre[:55] + '…' if len(obj.titre) > 55 else obj.titre

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        bg, fg = self.STATUT_COLORS.get(obj.statut, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_statut_display(),
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.agent = request.user
        super().save_model(request, obj, form, change)


# =============================================================================
# NOTIFICATIONS INTERNES
# =============================================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('date_creation', 'type_badge', 'titre', 'destinataire', 'lue_badge')
    list_filter   = ('type', 'lue', 'date_creation')
    search_fields = ('titre', 'message', 'destinataire__username', 'destinataire__last_name')
    date_hierarchy = 'date_creation'
    readonly_fields = ('date_creation', 'destinataire', 'type', 'titre', 'message', 'url', 'depot', 'document')

    def has_add_permission(self, request):
        return False   # Les notifications sont créées programmatiquement

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if a_acces_gestion(request.user):
            return True
        if obj is not None:
            return obj.destinataire_id == request.user.pk
        return request.user.is_authenticated

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if a_acces_gestion(request.user):
            return qs
        return qs.filter(destinataire=request.user)

    TYPE_COLORS = {
        'NOUVEAU_DEPOT': ('#2563eb', '#fff'),
        'DEPOT_ARCHIVE': ('#059669', '#fff'),
        'DEPOT_REJETE':  ('#dc2626', '#fff'),
        'ACCES_ACCORDE': ('#7c3aed', '#fff'),
        'ACCES_EXPIRE':  ('#6b7280', '#fff'),
        'DEMANDE_PRET':  ('#0284c7', '#fff'),
        'PRET_ACCORDE':  ('#059669', '#fff'),
        'PRET_REFUSE':   ('#dc2626', '#fff'),
        'PRET_RAPPEL':   ('#d97706', '#fff'),
        'PRET_RETARD':   ('#b91c1c', '#fff'),
        'ALERTE_DUA':    ('#d97706', '#fff'),
        'DUA_ECHUE':     ('#dc2626', '#fff'),
        'INTEGRITE_KO':  ('#7f1d1d', '#fff'),
    }

    @admin.display(description='Type')
    def type_badge(self, obj):
        bg, fg = self.TYPE_COLORS.get(obj.type, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.78em;">{}</span>',
            bg, fg, obj.get_type_display(),
        )

    @admin.display(description='Lue', boolean=True)
    def lue_badge(self, obj):
        return obj.lue


# =============================================================================
# ACCÈS SPÉCIAUX DOCUMENTS (ABAC)
# =============================================================================

@admin.register(AccesDocument)
class AccesDocumentAdmin(admin.ModelAdmin):
    list_display  = ('document', 'utilisateur', 'type_acces', 'date_debut', 'date_fin_aff', 'actif_badge', 'accorde_par')
    list_filter   = ('type_acces', 'actif')
    search_fields = ('document__identifiant', 'document__titre', 'utilisateur__username', 'utilisateur__last_name')
    readonly_fields = ('date_debut', 'accorde_par')
    autocomplete_fields = ('document', 'utilisateur')

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.accorde_par = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Fin d'accès")
    def date_fin_aff(self, obj):
        if obj.date_fin is None:
            return format_html('<span style="color:#059669">Permanent</span>')
        from django.utils import timezone as tz
        if tz.now() >= obj.date_fin:
            return format_html('<span style="color:#dc2626">{} (expiré)</span>', obj.date_fin.strftime('%d/%m/%Y %H:%M'))
        return obj.date_fin.strftime('%d/%m/%Y %H:%M')

    @admin.display(description='Actif', boolean=True)
    def actif_badge(self, obj):
        return obj.actif and not obj.est_expire


# =============================================================================
# DEMANDES DE PRÊT / ACCÈS NUMÉRIQUE
# =============================================================================

@admin.register(DemandePret)
class DemandePretAdmin(admin.ModelAdmin):
    list_display  = ('date_demande', 'demandeur', 'document', 'type_demande_badge', 'statut_badge', 'traite_par')
    list_filter   = ('type_demande', 'statut', 'date_demande')
    search_fields = ('demandeur__username', 'demandeur__last_name', 'document__identifiant', 'document__titre', 'motif')
    date_hierarchy = 'date_demande'
    readonly_fields = ('date_demande', 'demandeur', 'date_traitement')

    fieldsets = (
        ('Demande', {
            'fields': ('demandeur', 'document', 'type_demande', 'motif', 'duree_acces_heures', 'date_demande'),
        }),
        ('Traitement archiviste', {
            'fields': ('statut', 'traite_par', 'date_traitement', 'motif_refus'),
        }),
    )

    STATUT_COLORS = {
        'EN_ATTENTE': ('#d97706', '#fff'),
        'ACCORDEE':   ('#059669', '#fff'),
        'REFUSEE':    ('#dc2626', '#fff'),
        'CLOTUREE':   ('#6b7280', '#fff'),
    }
    TYPE_COLORS = {
        'PHYSIQUE':  ('#0284c7', '#fff'),
        'NUMERIQUE': ('#7c3aed', '#fff'),
    }

    def has_view_permission(self, request, obj=None):
        if a_acces_gestion(request.user):
            return True
        if obj is not None:
            return obj.demandeur_id == request.user.pk
        return request.user.is_authenticated

    def has_add_permission(self, request):
        return request.user.is_authenticated and request.user.is_active

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if a_acces_gestion(request.user):
            return qs
        return qs.filter(demandeur=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.demandeur = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Type')
    def type_demande_badge(self, obj):
        bg, fg = self.TYPE_COLORS.get(obj.type_demande, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_type_demande_display(),
        )

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        bg, fg = self.STATUT_COLORS.get(obj.statut, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, obj.get_statut_display(),
        )


# =============================================================================
# PRÊTS PHYSIQUES
# =============================================================================

@admin.register(PretDocument)
class PretDocumentAdmin(admin.ModelAdmin):
    list_display  = ('numero_bon', 'document', 'emprunteur', 'date_pret', 'date_retour_prevue', 'statut_badge', 'retard_aff', 'accorde_par')
    list_filter   = ('statut', 'date_pret')
    search_fields = ('numero_bon', 'document__identifiant', 'document__titre', 'emprunteur__username', 'emprunteur__last_name')
    date_hierarchy = 'date_pret'
    readonly_fields = ('numero_bon', 'date_pret', 'accorde_par')

    fieldsets = (
        ('Bon de prêt', {
            'fields': ('numero_bon', 'demande', 'document', 'emprunteur', 'accorde_par'),
        }),
        ('Dates', {
            'fields': ('date_pret', 'date_retour_prevue', 'date_retour_effective'),
        }),
        ('Suivi', {
            'fields': ('statut', 'observations'),
        }),
    )

    STATUT_COLORS = {
        'EN_COURS':  ('#2563eb', '#fff'),
        'RETOURNE':  ('#059669', '#fff'),
        'EN_RETARD': ('#dc2626', '#fff'),
        'PERDU':     ('#374151', '#fff'),
    }

    def has_view_permission(self, request, obj=None):
        if a_acces_lecture_etendue(request.user):
            return True
        if obj is not None:
            return obj.emprunteur_id == request.user.pk
        return request.user.is_authenticated

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if a_acces_lecture_etendue(request.user):
            return qs
        return qs.filter(emprunteur=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.accorde_par = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        # Priorité : retard détecté dynamiquement même si statut=EN_COURS
        statut = 'EN_RETARD' if obj.est_en_retard else obj.statut
        bg, fg = self.STATUT_COLORS.get(statut, ('#6b7280', '#fff'))
        label  = dict(PretDocument.Statut.choices).get(obj.statut, obj.statut)
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:0.80em;">{}</span>',
            bg, fg, label,
        )

    @admin.display(description='Retard', boolean=True)
    def retard_aff(self, obj):
        return obj.est_en_retard


# =============================================================================
# RÉTENTIONS JURIDIQUES (LEGAL HOLD)
# =============================================================================

@admin.register(RetentionJuridique)
class RetentionJuridiqueAdmin(admin.ModelAdmin):
    list_display  = ('document', 'autorite', 'reference', 'date_debut', 'date_fin', 'active_badge', 'cree_par')
    list_filter   = ('active',)
    search_fields = ('document__identifiant', 'document__titre', 'autorite', 'reference', 'motif')
    readonly_fields = ('cree_par',)
    autocomplete_fields = ('document',)

    fieldsets = (
        ('Document concerné', {
            'fields': ('document',),
        }),
        ('Autorité ordonnante', {
            'fields': ('autorite', 'reference', 'motif'),
        }),
        ('Période', {
            'fields': ('date_debut', 'date_fin', 'active'),
        }),
        ('Traçabilité', {
            'fields': ('cree_par',),
            'classes': ('collapse',),
        }),
    )

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Active', boolean=True)
    def active_badge(self, obj):
        return obj.est_active


# =============================================================================
# VÉRIFICATIONS D'INTÉGRITÉ SHA-256
# =============================================================================

@admin.register(VerificationIntegrite)
class VerificationIntegriteAdmin(admin.ModelAdmin):
    list_display  = ('date_verification', 'document', 'resultat_badge', 'verifie_par', 'empreinte_ok')
    list_filter   = ('resultat', 'date_verification')
    search_fields = ('document__identifiant', 'document__titre', 'verifie_par__username', 'message')
    date_hierarchy = 'date_verification'
    readonly_fields = (
        'document', 'date_verification', 'resultat', 'verifie_par',
        'empreinte_calculee', 'empreinte_reference', 'message',
    )

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)   # Lancé via script Celery ou manuellement

    def has_change_permission(self, request, obj=None):
        return False    # Journal immuable

    def has_delete_permission(self, request, obj=None):
        return False    # Journal immuable

    def has_view_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    RESULTAT_COLORS = {
        'OK':     ('#059669', '#fff'),
        'ECHOUE': ('#dc2626', '#fff'),
        'ERREUR': ('#d97706', '#fff'),
    }

    @admin.display(description='Résultat')
    def resultat_badge(self, obj):
        bg, fg = self.RESULTAT_COLORS.get(obj.resultat, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.82em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_resultat_display(),
        )

    @admin.display(description='Empreinte cohérente', boolean=True)
    def empreinte_ok(self, obj):
        return obj.empreinte_calculee == obj.empreinte_reference


# =============================================================================
# PERSONNALISATION DU SITE ADMIN
# =============================================================================

admin.site.site_header = "ENSMG — Système de Gestion des Archives"
admin.site.site_title  = "Archives ENSMG"
admin.site.index_title = "Tableau de bord archivistique"
