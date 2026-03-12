from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import CustomUser, Departement


# =============================================================================
# DÉPARTEMENTS / SERVICES
# =============================================================================

@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display  = ('code', 'nom', 'type_badge', 'actif')
    list_filter   = ('type', 'actif')
    search_fields = ('code', 'nom', 'description')
    ordering      = ('type', 'nom')
    list_editable = ('actif',)

    TYPE_COLORS = {
        'DIRECTION':     ('#7c3aed', '#fff'),
        'PEDAGOGIQUE':   ('#2563eb', '#fff'),
        'SCIENTIFIQUE':  ('#0891b2', '#fff'),
        'ADMINISTRATIF': ('#059669', '#fff'),
        'SUPPORT':       ('#d97706', '#fff'),
    }

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description='Type')
    def type_badge(self, obj):
        bg, fg = self.TYPE_COLORS.get(obj.type, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.82em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_type_display(),
        )


# =============================================================================
# UTILISATEURS
# =============================================================================

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Administration des utilisateurs ENSMG.
    Accès réservé aux Administrateurs système.
    """

    list_display  = ('username', 'nom_complet', 'role_badge', 'departement', 'email', 'is_active')
    list_filter   = ('role', 'departement', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'departement__nom')
    ordering      = ('last_name', 'first_name')

    ROLE_COLORS = {
        'ADMIN':      ('#dc2626', '#fff'),
        'ARCHIVISTE': ('#2563eb', '#fff'),
        'DIRECTION':  ('#7c3aed', '#fff'),
        'PERSONNEL':  ('#059669', '#fff'),
        'ENSEIGNANT': ('#d97706', '#fff'),
    }

    fieldsets = UserAdmin.fieldsets + (
        ('Informations ENSMG', {
            'fields': ('role', 'departement', 'telephone'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations ENSMG', {
            'fields': ('role', 'departement', 'telephone'),
        }),
    )

    # ── RBAC ─────────────────────────────────────────────────────────────────

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN

    def has_add_permission(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN

    def has_change_permission(self, request, obj=None):
        if obj and obj == request.user:
            return True
        return request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN

    def has_delete_permission(self, request, obj=None):
        if obj and obj == request.user:
            return False
        return request.user.is_superuser

    # ── Affichage ─────────────────────────────────────────────────────────────

    @admin.display(description='Nom complet')
    def nom_complet(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Rôle')
    def role_badge(self, obj):
        bg, fg = self.ROLE_COLORS.get(obj.role, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.85em;font-weight:bold;">{}</span>',
            bg, fg, obj.get_role_display(),
        )
