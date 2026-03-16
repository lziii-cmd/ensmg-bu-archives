"""
archives/urls.py — Routage URL de l'application archives ENSMG
"""
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from archives import views

app_name = 'archives'

urlpatterns = [
    # ── Racine : redirige vers le tableau de bord (lui-même redirige vers login si non connecté)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='index'),

    # ── Authentification ──────────────────────────────────────────────────────
    path(
        'auth/login/',
        auth_views.LoginView.as_view(template_name='archives/auth/login.html'),
        name='login',
    ),
    path(
        'auth/logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),

    # ── Tableau de bord ───────────────────────────────────────────────────────
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # ── Documents ─────────────────────────────────────────────────────────────
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/<int:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('documents/<int:pk>/telecharger/', views.document_telecharger, name='document_telecharger'),
    path('documents/<int:pk>/viewer/', views.document_viewer, name='document_viewer'),
    path('documents/<int:pk>/serve/', views.document_serve, name='document_serve'),
    path('documents/<int:pk>/acces/', views.accorder_acces_direct, name='accorder_acces'),

    # ── Dépôts — côté agent ───────────────────────────────────────────────────
    path('depots/nouveau/', views.NouveauDepotView.as_view(), name='nouveau_depot'),
    path('depots/mes-depots/', views.MesDepotsView.as_view(), name='mes_depots'),
    path('depots/service/', views.DepotServiceView.as_view(), name='depots_service'),
    path('depots/<int:pk>/reformuler/', views.RetryDepotView.as_view(), name='retry_depot'),

    # ── Dépôts — côté archiviste ──────────────────────────────────────────────
    path('archiviste/depots/', views.ArchivisteDepotsListView.as_view(), name='archiviste_depots'),
    path(
        'archiviste/depots/<int:pk>/',
        views.ArchivisteDepotDetailView.as_view(),
        name='archiviste_depot_detail',
    ),

    # ── Prêts — côté agent ────────────────────────────────────────────────────
    path(
        'documents/<int:pk>/pret/',
        views.NouvelleDemandePreView.as_view(),
        name='nouvelle_demande_pret',
    ),
    path('prets/mes-prets/', views.MesPretsView.as_view(), name='mes_prets'),

    # ── Prêts — côté archiviste ───────────────────────────────────────────────
    path('archiviste/prets/', views.ArchivistePretsListView.as_view(), name='archiviste_prets'),
    path(
        'archiviste/prets/<int:pk>/',
        views.ArchivistePretDetailView.as_view(),
        name='archiviste_pret_detail',
    ),
    path(
        'archiviste/prets/<int:pk>/retour/',
        views.retour_pret,
        name='retour_pret',
    ),

    # ── Recherche documentaire — côté agent ───────────────────────────────────
    path('recherche/nouvelle/', views.DemandeRechercheCreateView.as_view(), name='nouvelle_recherche'),
    path('recherche/mes-demandes/', views.MesRecherchesView.as_view(), name='mes_recherches'),

    # ── Recherche documentaire — côté archiviste ──────────────────────────────
    path('archiviste/recherches/', views.ArchivisteRecherchesListView.as_view(), name='archiviste_recherches'),
    path('archiviste/recherches/<int:pk>/', views.ArchivisteRechercheDetailView.as_view(), name='archiviste_recherche_detail'),

    # ── Notifications ─────────────────────────────────────────────────────────
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/lue/', views.notif_marquer_lue, name='notif_marquer_lue'),

    # ── Profil utilisateur ────────────────────────────────────────────────────
    path('profil/', views.MonProfilView.as_view(), name='mon_profil'),

    # ── Administration métier ─────────────────────────────────────────────────
    # NOTE: préfixe "gestion/" et non "admin/" → évite le conflit avec
    # path('admin/', admin.site.urls) déclaré dans le urls.py du projet.
    # Catégories de documents
    path('gestion/categories/', views.admin_categories_list, name='admin_categories'),
    path('gestion/categories/creer/', views.admin_categorie_create, name='admin_categorie_create'),
    path('gestion/categories/<int:pk>/modifier/', views.admin_categorie_edit, name='admin_categorie_edit'),
    path('gestion/categories/<int:pk>/supprimer/', views.admin_categorie_delete, name='admin_categorie_delete'),

    # Plan de classement
    path('gestion/plans/', views.admin_plans_list, name='admin_plans'),
    path('gestion/plans/creer/', views.admin_plan_create, name='admin_plan_create'),
    path('gestion/plans/<int:pk>/modifier/', views.admin_plan_edit, name='admin_plan_edit'),
    path('gestion/plans/<int:pk>/supprimer/', views.admin_plan_delete, name='admin_plan_delete'),

    # Journal d'audit
    path('gestion/journal/', views.admin_journal, name='admin_journal'),

    # Provenance externe (AJAX + création depuis popup dépôt)
    path('gestion/provenance/ajax-create/', views.admin_provenance_create_ajax, name='admin_provenance_ajax'),

    # ── Bordereaux de versement ───────────────────────────────────────────────
    path('gestion/versements/', views.admin_bordereaux_versement, name='admin_bordereaux_versement'),
    path('gestion/versements/generer/', views.admin_bordereau_versement_generer, name='admin_bordereau_versement_generer'),
    path('gestion/versements/<int:pk>/', views.admin_bordereau_versement_detail, name='admin_bordereau_versement_detail'),

    # ── Bordereaux d'élimination ──────────────────────────────────────────────
    path('gestion/eliminations/', views.admin_bordereaux_elimination, name='admin_bordereaux_elimination'),
    path('gestion/eliminations/creer/', views.admin_bordereau_elimination_create, name='admin_bordereau_elimination_create'),
    path('gestion/eliminations/<int:pk>/', views.admin_bordereau_elimination_detail, name='admin_bordereau_elimination_detail'),

    # ── Corbeille (soft delete) ───────────────────────────────────────────────
    path('gestion/corbeille/', views.corbeille_list, name='corbeille'),
    path('gestion/corbeille/<int:pk>/restaurer/', views.corbeille_restaurer, name='corbeille_restaurer'),
    path('documents/<int:pk>/supprimer/', views.document_supprimer, name='document_supprimer'),

    # ── Mode Audit temporaire ─────────────────────────────────────────────────
    path('gestion/audit/', views.audit_tokens_list, name='audit_tokens'),
    path('gestion/audit/creer/', views.audit_token_create, name='audit_token_create'),
    path('gestion/audit/<int:pk>/', views.audit_token_detail, name='audit_token_detail'),
    path('audit/<str:token_str>/', views.audit_acces, name='audit_acces'),

    # ── Actions en masse + Stats API ─────────────────────────────────────────
    path('api/documents/bulk-action/', views.documents_bulk_action, name='documents_bulk_action'),
    path('api/dashboard/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),

    # ── Module Courrier ───────────────────────────────────────────────────────
    path('courriers/', views.courrier_liste, name='courrier_liste'),
    path('courriers/nouveau/', views.courrier_enregistrer, name='courrier_enregistrer'),
    path('courriers/<int:pk>/', views.courrier_detail, name='courrier_detail'),
    path('courriers/<int:pk>/modifier/', views.courrier_modifier, name='courrier_modifier'),
    path('courriers/<int:pk>/action/', views.courrier_action, name='courrier_action'),
    path('courriers/<int:pk>/supprimer/', views.courrier_supprimer, name='courrier_supprimer'),

    # Bordereaux versement courriers
    path('courriers/versements/', views.courrier_bv_liste, name='courrier_bv_liste'),
    path('courriers/versements/nouveau/', views.courrier_bv_creer, name='courrier_bv_creer'),
    path('courriers/versements/<int:pk>/', views.courrier_bv_detail, name='courrier_bv_detail'),

    # Bordereaux élimination courriers
    path('courriers/eliminations/', views.courrier_be_liste, name='courrier_be_liste'),
    path('courriers/eliminations/nouveau/', views.courrier_be_creer, name='courrier_be_creer'),
    path('courriers/eliminations/<int:pk>/', views.courrier_be_detail, name='courrier_be_detail'),

    # ── Messagerie interne ────────────────────────────────────────────────────
    path('messagerie/', views.messagerie_reception, name='messagerie_reception'),
    path('messagerie/envoyes/', views.messagerie_envoyes, name='messagerie_envoyes'),
    path('messagerie/nouveau/', views.messagerie_nouveau, name='messagerie_nouveau'),
    path('messagerie/corbeille/', views.messagerie_corbeille, name='messagerie_corbeille'),
    path('messagerie/<int:pk>/', views.messagerie_detail, name='messagerie_detail'),
    path('messagerie/<int:pk>/repondre/', views.messagerie_repondre, name='messagerie_repondre'),
    path('messagerie/<int:pk>/supprimer/', views.messagerie_supprimer, name='messagerie_supprimer'),
]
