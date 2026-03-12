"""
Logique RBAC (Role-Based Access Control) centralisée pour le système d'archives ENSMG.

Matrice des permissions :
┌─────────────────────────┬────────┬────────────┬──────────┬───────────┬────────────┐
│ Ressource               │ ADMIN  │ ARCHIVISTE │ DIRECTION│ PERSONNEL │ ENSEIGNANT │
├─────────────────────────┼────────┼────────────┼──────────┼───────────┼────────────┤
│ Utilisateurs            │ CRUD   │ —          │ —        │ —         │ —          │
│ Catégories / Plan       │ CRUD   │ CRUD       │ R        │ R         │ —          │
│ Tableau DUA             │ CRUD   │ CRUD       │ R        │ —         │ —          │
│ Documents PUBLIC        │ CRUD   │ CRUD       │ R        │ R         │ R          │
│ Documents INTERNE       │ CRUD   │ CRUD       │ R        │ R (svc)   │ —          │
│ Documents CONFIDENTIEL  │ CRUD   │ CRUD       │ R        │ —         │ —          │
│ Documents SECRET        │ CRUD   │ CRUD       │ —        │ —         │ —          │
│ Journal d'audit         │ R      │ R          │ R        │ —         │ —          │
│ Bordereaux              │ CRUD   │ CRUD       │ R+valid. │ —         │ —          │
└─────────────────────────┴────────┴────────────┴──────────┴───────────┴────────────┘
"""

from users.models import CustomUser


# =============================================================================
# HELPERS DE RÔLE
# =============================================================================

def est_admin(user):
    return user.is_superuser or getattr(user, 'role', None) == CustomUser.Role.ADMIN

def est_archiviste(user):
    return getattr(user, 'role', None) == CustomUser.Role.ARCHIVISTE

def est_direction(user):
    return getattr(user, 'role', None) == CustomUser.Role.DIRECTION

def est_personnel(user):
    return getattr(user, 'role', None) == CustomUser.Role.PERSONNEL

def est_enseignant(user):
    return getattr(user, 'role', None) == CustomUser.Role.ENSEIGNANT

def a_acces_gestion(user):
    """Admin ou Archiviste — peuvent créer/modifier/supprimer."""
    return est_admin(user) or est_archiviste(user)

def a_acces_lecture_etendue(user):
    """Admin, Archiviste ou Direction — peuvent tout lire."""
    return est_admin(user) or est_archiviste(user) or est_direction(user)


# =============================================================================
# PERMISSIONS SUR LES DOCUMENTS
# =============================================================================

# Niveaux de confidentialité accessibles par rôle
CONFIDENTIALITE_AUTORISEE = {
    CustomUser.Role.ADMIN:      ['PUBLIC', 'INTERNE', 'CONFIDENTIEL', 'SECRET'],
    CustomUser.Role.ARCHIVISTE: ['PUBLIC', 'INTERNE', 'CONFIDENTIEL', 'SECRET'],
    CustomUser.Role.DIRECTION:  ['PUBLIC', 'INTERNE', 'CONFIDENTIEL'],
    CustomUser.Role.PERSONNEL:  ['PUBLIC', 'INTERNE'],
    CustomUser.Role.ENSEIGNANT: ['PUBLIC'],
}

def get_confidentialites_autorisees(user):
    """Retourne la liste des niveaux de confidentialité accessibles à cet utilisateur."""
    if user.is_superuser:
        return ['PUBLIC', 'INTERNE', 'CONFIDENTIEL', 'SECRET']
    role = getattr(user, 'role', CustomUser.Role.ENSEIGNANT)
    return CONFIDENTIALITE_AUTORISEE.get(role, ['PUBLIC'])

def peut_voir_document(user, document):
    """
    Vérifie si l'utilisateur peut consulter un document donné.

    Ordre d'évaluation :
      1. ABAC — AccesDocument individuel actif et non expiré → accès immédiat
         (permet d'accorder un accès temporaire à un document hors portée du rôle)
      2. RBAC — matrice rôle × confidentialité
      3. Restriction départementale pour le rôle PERSONNEL (documents INTERNE)
    """
    if not user.is_authenticated:
        return False

    # ── 1. ABAC : accès individuel accordé par l'archiviste ─────────────────
    # Import tardif pour éviter la dépendance circulaire (permissions ← models)
    try:
        from archives.models import AccesDocument
        from django.utils import timezone as tz
        acces = AccesDocument.objects.filter(
            document=document,
            utilisateur=user,
            actif=True,
        ).first()
        if acces is not None:
            # L'entrée existe : vérifier que l'accès n'est pas expiré
            if acces.date_fin is None or tz.now() < acces.date_fin:
                return True
            # Expiré → on continue vers la vérification RBAC classique
    except Exception:
        # En cas d'erreur ORM (ex. pendant les migrations) on passe en RBAC pur
        pass

    # ── 2. RBAC : matrice rôle × confidentialité ────────────────────────────
    niveaux_autorises = get_confidentialites_autorisees(user)
    if document.confidentialite not in niveaux_autorises:
        return False

    # ── 3. Restriction départementale pour PERSONNEL (documents INTERNE) ────
    if est_personnel(user) and document.confidentialite == 'INTERNE':
        if user.departement and document.producteur:
            return user.departement.nom.lower() in document.producteur.lower()
        return False

    return True

def peut_modifier_document(user, document=None):
    """Seuls Admin et Archiviste peuvent créer/modifier des documents."""
    return a_acces_gestion(user)

def peut_supprimer_document(user, document=None):
    """Seul l'Admin peut supprimer (l'archiviste déclenche une élimination formelle)."""
    return est_admin(user)

def peut_eliminer(user):
    """Archiviste et Admin peuvent déclencher une procédure d'élimination."""
    return a_acces_gestion(user)

def peut_verser(user):
    """Archiviste et Admin peuvent créer un bordereau de versement."""
    return a_acces_gestion(user)

def peut_valider_bordereau(user):
    """Direction, Archiviste et Admin peuvent valider un bordereau."""
    return a_acces_lecture_etendue(user)

def peut_deposer(user):
    """Tout utilisateur authentifié peut déposer un document."""
    return user.is_authenticated and user.is_active

def peut_traiter_depot(user):
    """Seuls l'Archiviste et l'Admin traitent (valident/rejettent) un dépôt."""
    return a_acces_gestion(user)

def peut_demander_pret(user):
    """
    Les agents (Personnel, Enseignant, Direction) peuvent faire une demande de prêt.
    Les Archivistes et Admins gèrent les prêts — ils n'en font pas eux-mêmes.
    """
    if not user.is_authenticated or not user.is_active:
        return False
    return not est_archiviste(user) and not est_admin(user)

def peut_gerer_prets(user):
    """Archiviste et Admin gèrent les prêts (accordent / rejettent / retour)."""
    return a_acces_gestion(user)

def peut_accorder_acces_special(user):
    """Seuls l'Archiviste et l'Admin peuvent créer un AccesDocument ABAC."""
    return a_acces_gestion(user)

def peut_poser_retention(user):
    """Seuls l'Admin et l'Archiviste enregistrent une rétention juridique."""
    return a_acces_gestion(user)

def peut_voir_notifications(user, notification):
    """Un utilisateur ne voit que ses propres notifications."""
    return user.is_authenticated and notification.destinataire_id == user.pk


# =============================================================================
# MIXIN POUR LES VUES D'ADMINISTRATION
# =============================================================================

class RBACAdminMixin:
    """
    Mixin à inclure dans les ModelAdmin pour appliquer la matrice RBAC.
    Surcharger `get_queryset`, `has_*_permission` selon les besoins.
    """

    def has_module_perms(self, request, app_label):
        return request.user.is_authenticated

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)


class LectureSeuleAdminMixin(RBACAdminMixin):
    """Mixin pour les ressources en lecture seule pour la Direction."""

    def has_add_permission(self, request):
        return a_acces_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return a_acces_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return est_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return a_acces_lecture_etendue(request.user)
