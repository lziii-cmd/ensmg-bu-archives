"""
archives/urls.py — Routage URL de l'application archives ENSMG
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from archives import views

app_name = 'archives'

urlpatterns = [
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
]
