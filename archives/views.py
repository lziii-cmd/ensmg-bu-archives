"""
archives/views.py — Vues ENSMG — champs calés sur les vrais modèles.
Deux espaces distincts : ARCHIVISTE (bleu) / AGENT (mauve).
"""
import hashlib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from archives.forms import (
    DepotAgentForm, TraiterDepotForm,
    DemandePretForm, TraiterDemandePretForm,
    RetourPretForm, AccesDocumentForm, RechercheDocumentForm,
    DemandeRechercheForm, TraiterRechercheForm,
    CategorieDocumentForm, PlanClassementForm, ProvenanceExterneForm,
)
from archives.models import (
    Document, DepotDocument, DemandePret, PretDocument,
    AccesDocument, Notification, MouvementDocument,
    RetentionJuridique, PlanClassement, CategorieDocument, DemandeRecherche,
    ProvenanceExterne, BordereauVersement, BordereauElimination,
    AuditToken, TableauGestion, Message, MessageDestinataire,
    Courrier, MouvementCourrier, BordereauVersementCourrier, BordereauEliminationCourrier,
)
from archives.permissions import (
    peut_voir_document, peut_deposer, peut_traiter_depot,
    peut_demander_pret, peut_gerer_prets, peut_accorder_acces_special,
    est_archiviste, est_admin, est_direction, est_personnel, est_enseignant,
    get_confidentialites_autorisees,
)

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────────────
# Mixin de base
# ──────────────────────────────────────────────────────────────────────────────

class ArchiveMixin(LoginRequiredMixin):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        notifs_non_lues = Notification.objects.filter(destinataire=user, lue=False)
        ctx['nb_notifications']     = notifs_non_lues.count()
        ctx['notifs_recentes']      = notifs_non_lues.select_related(
            'depot', 'document'
        ).order_by('-date_creation')[:6]
        ctx['nb_messages_non_lus']  = MessageDestinataire.objects.filter(
            destinataire=user, lu=False, en_corbeille=False
        ).count()
        ctx['est_gestionnaire'] = est_archiviste(user) or est_admin(user)
        ctx['est_direction']    = est_direction(user)
        ctx['est_admin']        = est_admin(user)
        ctx['theme'] = 'archiviste' if (est_archiviste(user) or est_admin(user)) else 'agent'
        return ctx


def _notif_ctx(request):
    """Contexte minimal pour les vues Function-Based."""
    user = request.user
    notifs_non_lues = Notification.objects.filter(destinataire=user, lue=False)
    return {
        'nb_notifications': notifs_non_lues.count(),
        'notifs_recentes':  notifs_non_lues.select_related(
            'depot', 'document'
        ).order_by('-date_creation')[:6],
        'nb_messages_non_lus': MessageDestinataire.objects.filter(
            destinataire=user, lu=False, en_corbeille=False
        ).count(),
        'est_gestionnaire': est_archiviste(user) or est_admin(user),
        'est_direction':    est_direction(user),
        'est_admin':        est_admin(user),
        'theme': 'archiviste' if (est_archiviste(user) or est_admin(user)) else 'agent',
    }


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────────────────────

class DashboardView(ArchiveMixin, TemplateView):
    template_name = 'archives/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        if est_archiviste(user) or est_admin(user):
            ctx['nb_depots_en_attente'] = DepotDocument.objects.filter(statut='EN_ATTENTE').count()
            ctx['nb_prets_en_cours']    = PretDocument.objects.filter(statut='EN_COURS').count()
            ctx['nb_demandes_pret']     = DemandePret.objects.filter(statut='EN_ATTENTE').count()
            ctx['nb_documents']         = Document.objects.filter(deleted_at__isnull=True).exclude(statut='ELIMINE').count()
            ctx['derniers_depots']      = DepotDocument.objects.select_related('agent', 'categorie').order_by('-date_depot')[:10]
            ctx['prets_en_cours']       = PretDocument.objects.select_related(
                'emprunteur', 'document'
            ).filter(statut='EN_COURS').order_by('date_retour_prevue')[:10]
        else:
            # Dashboard agent : documents publics + ses dépôts/prêts
            ctx['docs_publics'] = Document.objects.filter(
                confidentialite='PUBLIC', deleted_at__isnull=True
            ).exclude(statut='ELIMINE').order_by('-date_enregistrement')[:8]
            ctx['form_recherche'] = RechercheDocumentForm(self.request.GET or None)
            ctx['mes_depots']         = DepotDocument.objects.filter(agent=user).order_by('-date_depot')[:5]
            ctx['mes_demandes_pret']  = DemandePret.objects.filter(
                demandeur=user
            ).select_related('document').order_by('-date_demande')[:5]
            ctx['mes_demandes_recherche'] = DemandeRecherche.objects.filter(
                agent=user
            ).order_by('-date_demande')[:3]

        ctx['mes_notifications'] = Notification.objects.filter(
            destinataire=user
        ).order_by('-date_creation')[:5]
        return ctx


# ──────────────────────────────────────────────────────────────────────────────
# Documents
# ──────────────────────────────────────────────────────────────────────────────

class DocumentListView(ArchiveMixin, ListView):
    template_name = 'archives/documents/list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        niveaux = get_confidentialites_autorisees(user)
        qs = Document.objects.filter(
            confidentialite__in=niveaux, deleted_at__isnull=True
        ).exclude(statut='ELIMINE').select_related('categorie', 'plan_classement')

        # Accès ABAC individuels
        acces_ids = AccesDocument.objects.filter(
            utilisateur=user, actif=True
        ).filter(
            Q(date_fin__isnull=True) | Q(date_fin__gt=timezone.now())
        ).values_list('document_id', flat=True)
        qs = (qs | Document.objects.filter(pk__in=acces_ids, deleted_at__isnull=True)).distinct()

        form = RechercheDocumentForm(self.request.GET)
        if form.is_valid():
            q    = form.cleaned_data.get('q')
            cat  = form.cleaned_data.get('categorie')
            conf = form.cleaned_data.get('confidentialite')
            an   = form.cleaned_data.get('annee')
            if q:
                qs = qs.filter(
                    Q(titre__icontains=q) | Q(identifiant__icontains=q) |
                    Q(producteur__icontains=q) | Q(mots_cles__icontains=q)
                )
            if cat:
                qs = qs.filter(categorie_id=cat)
            if conf:
                qs = qs.filter(confidentialite=conf)
            if an:
                qs = qs.filter(date_creation__year=an)
        return qs.order_by('-date_enregistrement')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_recherche'] = RechercheDocumentForm(self.request.GET)
        return ctx


class DocumentDetailView(ArchiveMixin, DetailView):
    template_name = 'archives/documents/detail.html'
    context_object_name = 'document'
    model = Document

    def get_object(self, queryset=None):
        doc = get_object_or_404(Document, pk=self.kwargs['pk'])
        if not peut_voir_document(self.request.user, doc):
            raise PermissionDenied
        return doc

    def get(self, request, *args, **kwargs):
        resp = super().get(request, *args, **kwargs)
        MouvementDocument.objects.create(
            document=self.object,
            action=MouvementDocument.Action.CONSULTATION,
            utilisateur=request.user,
            commentaire="Consultation de la fiche détaillée",
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        doc  = self.object
        user = self.request.user
        ctx['peut_telecharger'] = peut_voir_document(user, doc) and bool(doc.fichier)
        ctx['retentions'] = RetentionJuridique.objects.filter(document=doc, active=True)
        if est_archiviste(user) or est_admin(user):
            ctx['acces_abac'] = AccesDocument.objects.filter(
                document=doc
            ).select_related('utilisateur').order_by('-date_debut')
            ctx['form_acces'] = AccesDocumentForm()
            ctx['peut_accorder_acces'] = True
        else:
            ctx['peut_accorder_acces'] = False
        ctx['mouvements'] = MouvementDocument.objects.filter(
            document=doc
        ).select_related('utilisateur').order_by('-date_action')[:20]
        ctx['peut_demander_pret'] = peut_demander_pret(user)
        if ctx['peut_demander_pret']:
            ctx['form_pret'] = DemandePretForm()
        return ctx


def document_telecharger(request, pk):
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(f"{djsettings.LOGIN_URL}?next={request.path}")
    doc = get_object_or_404(Document, pk=pk)
    if not peut_voir_document(request.user, doc):
        raise PermissionDenied
    if not doc.fichier:
        raise Http404("Aucun fichier numerique associe.")
    MouvementDocument.objects.create(
        document=doc, action=MouvementDocument.Action.TELECHARGEMENT,
        utilisateur=request.user, commentaire="Telechargement du fichier numerique",
    )
    try:
        return FileResponse(
            doc.fichier.open('rb'), as_attachment=True,
            filename=doc.fichier.name.split('/')[-1],
        )
    except FileNotFoundError:
        raise Http404("Le fichier est introuvable sur le serveur.")


def document_viewer(request, pk):
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(f"{djsettings.LOGIN_URL}?next={request.path}")
    doc = get_object_or_404(Document, pk=pk)
    if not peut_voir_document(request.user, doc):
        raise PermissionDenied
    if not doc.fichier:
        raise Http404("Aucun fichier numerique associe.")
    return render(request, 'archives/documents/viewer.html', {
        'document': doc,
        **_notif_ctx(request),
    })


def document_serve(request, pk):
    """Sert le fichier PDF en mode inline pour l'affichage navigateur natif."""
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(f"{djsettings.LOGIN_URL}?next={request.path}")
    doc = get_object_or_404(Document, pk=pk)
    if not peut_voir_document(request.user, doc):
        raise PermissionDenied
    if not doc.fichier:
        raise Http404("Aucun fichier numerique associe.")
    try:
        filename = doc.fichier.name.split('/')[-1]
        response = FileResponse(doc.fichier.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    except FileNotFoundError:
        raise Http404("Le fichier est introuvable sur le serveur.")


# ──────────────────────────────────────────────────────────────────────────────
# Dépôts — AGENT (formulaire simplifié)
# ──────────────────────────────────────────────────────────────────────────────

class NouveauDepotView(ArchiveMixin, View):
    template_name = 'archives/depots/form_agent.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_deposer(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, form=None):
        ctx = _notif_ctx(self.request)
        ctx['form'] = form or DepotAgentForm()
        return ctx

    def get(self, request):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request):
        form = DepotAgentForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, self.get_context_data(form))

        cat_id = form.cleaned_data.get('categorie')
        categorie = CategorieDocument.objects.filter(pk=cat_id).first() if cat_id else None

        prov_interne = form.cleaned_data.get('provenance_interne', True)
        prov_ext_pk  = form.cleaned_data.get('provenance_externe')
        prov_ext_obj = None
        if not prov_interne and prov_ext_pk:
            prov_ext_obj = ProvenanceExterne.objects.filter(pk=prov_ext_pk, actif=True).first()

        # ── Détection de doublons par SHA-256 ────────────────────────────────
        fichier_upload = request.FILES.get('fichier')
        doublon = None
        if fichier_upload:
            sha = hashlib.sha256()
            for chunk in fichier_upload.chunks():
                sha.update(chunk)
            empreinte = sha.hexdigest()
            fichier_upload.seek(0)  # rembobiner pour la sauvegarde
            doublon = Document.objects.filter(
                empreinte_sha256=empreinte,
                deleted_at__isnull=True,
            ).exclude(statut='ELIMINE').first()
            if doublon:
                messages.warning(
                    request,
                    f"⚠️ Ce fichier semble être un doublon du document "
                    f"« {doublon.titre} » (réf. {doublon.identifiant}). "
                    f"Le dépôt a quand même été créé — l'archiviste décidera."
                )

        depot = DepotDocument.objects.create(
            agent=request.user,
            titre=form.cleaned_data['titre'],
            fichier=request.FILES['fichier'],
            date_reception=form.cleaned_data['date_reception'],
            categorie=categorie,
            description=form.cleaned_data.get('description', ''),
            mots_cles=form.cleaned_data.get('mots_cles', ''),
            statut='EN_ATTENTE',
            provenance_interne=bool(prov_interne),
            provenance_externe=prov_ext_obj,
        )
        for arch in User.objects.filter(role='ARCHIVISTE', is_active=True):
            Notification.objects.create(
                destinataire=arch,
                type=Notification.Type.NOUVEAU_DEPOT,
                titre="Nouveau depot a traiter",
                message=(f"L'agent {request.user.get_full_name() or request.user.username} "
                         f"a depose : \"{depot.titre}\"."),
                depot=depot,
            )
        messages.success(request, f"Depot enregistre (recepisse : {depot.numero_recepisse}).")
        return redirect('archives:mes_depots')


class MesDepotsView(ArchiveMixin, ListView):
    template_name = 'archives/depots/list_agent.html'
    context_object_name = 'depots'
    paginate_by = 20

    def get_queryset(self):
        return DepotDocument.objects.filter(agent=self.request.user).order_by('-date_depot')


# ──────────────────────────────────────────────────────────────────────────────
# Dépôts — ARCHIVISTE (traitement complet)
# ──────────────────────────────────────────────────────────────────────────────

class ArchivisteDepotsListView(ArchiveMixin, ListView):
    template_name = 'archives/depots/list_archiviste.html'
    context_object_name = 'depots'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_traiter_depot(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        statut = self.request.GET.get('statut', '')
        qs = DepotDocument.objects.select_related('agent', 'categorie')
        if statut in ('EN_ATTENTE', 'ARCHIVE', 'REJETE'):
            qs = qs.filter(statut=statut)
        return qs.order_by('-date_depot')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statut_filtre'] = self.request.GET.get('statut', '')
        ctx['nb_en_attente'] = DepotDocument.objects.filter(statut='EN_ATTENTE').count()
        return ctx


class ArchivisteDepotDetailView(ArchiveMixin, View):
    template_name = 'archives/depots/detail_archiviste.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_traiter_depot(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, depot, form=None):
        ctx = _notif_ctx(request)
        # Récupérer le service producteur automatiquement depuis le département de l'agent
        producteur_auto = ''
        if depot.agent_id:
            try:
                agent = User.objects.select_related('departement').get(pk=depot.agent_id)
                if agent.departement:
                    producteur_auto = agent.departement.nom
            except User.DoesNotExist:
                pass
        ctx.update({
            'depot': depot,
            'producteur_auto': producteur_auto,
            'form': form or TraiterDepotForm(
                initial={
                    'titre': depot.titre,
                    'date_creation': depot.date_reception,
                    'categorie': depot.categorie_id,
                    'producteur': producteur_auto,
                    'mots_cles': depot.mots_cles or '',
                    'statut': 'COURANT',
                    'support': 'NUMERIQUE' if depot.fichier else 'PAPIER',
                }
            )
        })
        return ctx

    def get(self, request, pk):
        depot = get_object_or_404(DepotDocument, pk=pk)
        return render(request, self.template_name, self._ctx(request, depot))

    def post(self, request, pk):
        depot = get_object_or_404(DepotDocument, pk=pk)
        if depot.statut != 'EN_ATTENTE':
            messages.warning(request, "Ce depot a deja ete traite.")
            return redirect('archives:archiviste_depots')

        form = TraiterDepotForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, depot, form))

        decision = form.cleaned_data['decision']

        if decision == 'REJETE':
            depot.statut      = 'REJETE'
            depot.motif_rejet = form.cleaned_data['motif_rejet']
            depot.traite_par  = request.user
            depot.date_traitement = timezone.now()
            depot.save()
            Notification.objects.create(
                destinataire=depot.agent,
                type=Notification.Type.DEPOT_REJETE,
                titre="Votre depot a ete rejete",
                message=(f"Votre depot \"{depot.titre}\" a ete rejete. "
                         f"Motif : {form.cleaned_data['motif_rejet']}"),
                depot=depot,
            )
            messages.warning(request, "Le depot a ete rejete.")
            return redirect('archives:archiviste_depots')

        # ARCHIVE — créer le Document d'archives
        plan = get_object_or_404(PlanClassement, pk=form.cleaned_data['plan_classement'])
        cat  = get_object_or_404(CategorieDocument, pk=form.cleaned_data['categorie'])

        # Récupérer le producteur depuis le département de l'agent si non renseigné manuellement
        producteur = form.cleaned_data.get('producteur', '').strip()
        if not producteur and depot.agent_id:
            try:
                agent = User.objects.select_related('departement').get(pk=depot.agent_id)
                if agent.departement:
                    producteur = agent.departement.nom
            except User.DoesNotExist:
                pass

        doc = Document(
            titre=depot.titre,
            producteur=producteur,
            date_creation=form.cleaned_data.get('date_creation') or depot.date_reception,
            description=depot.description,
            mots_cles=form.cleaned_data.get('mots_cles', '') or depot.mots_cles or '',
            categorie=cat,
            plan_classement=plan,
            confidentialite=form.cleaned_data['confidentialite'],
            statut=form.cleaned_data.get('statut', 'COURANT'),
            support=form.cleaned_data.get('support', 'NUMERIQUE'),
            sort_final=form.cleaned_data.get('sort_final', 'EN_ATTENTE'),
            localisation_physique=form.cleaned_data.get('localisation', ''),
            cree_par=request.user,
        )
        if depot.fichier:
            doc.fichier = depot.fichier
        doc.save()

        MouvementDocument.objects.create(
            document=doc, action=MouvementDocument.Action.CREATION,
            utilisateur=request.user,
            commentaire=f"Archive depuis le depot #{depot.numero_recepisse} — agent : {depot.agent}",
        )

        depot.statut          = 'ARCHIVE'
        depot.document_archive = doc
        depot.traite_par       = request.user
        depot.date_traitement  = timezone.now()
        depot.save()

        Notification.objects.create(
            destinataire=depot.agent,
            type=Notification.Type.DEPOT_ARCHIVE,
            titre="Votre depot a ete archive",
            message=(f"Votre depot \"{depot.titre}\" a ete archive "
                     f"(identifiant : {doc.identifiant})."),
            depot=depot, document=doc,
        )
        messages.success(request, f"Document archive avec succes (ID : {doc.identifiant}).")
        return redirect('archives:archiviste_depots')


# ──────────────────────────────────────────────────────────────────────────────
# Prêts — AGENT
# ──────────────────────────────────────────────────────────────────────────────

class NouvelleDemandePreView(ArchiveMixin, View):
    template_name = 'archives/prets/demande_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_demander_pret(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, document, form=None):
        ctx = _notif_ctx(request)
        ctx.update({'document': document, 'form': form or DemandePretForm()})
        return ctx

    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)
        if not peut_voir_document(request.user, doc):
            raise PermissionDenied
        return render(request, self.template_name, self._ctx(request, doc))

    def post(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)
        if not peut_voir_document(request.user, doc):
            raise PermissionDenied
        form = DemandePretForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, doc, form))

        demande = DemandePret.objects.create(
            document=doc,
            demandeur=request.user,
            type_demande=form.cleaned_data['type_demande'],
            motif=form.cleaned_data['motif'],
            duree_acces_heures=form.cleaned_data.get('duree_acces_heures') or 24,
            statut='EN_ATTENTE',
        )
        for arch in User.objects.filter(role='ARCHIVISTE', is_active=True):
            Notification.objects.create(
                destinataire=arch,
                type=Notification.Type.DEMANDE_PRET,
                titre="Nouvelle demande de pret",
                message=(f"{request.user.get_full_name() or request.user.username} "
                         f"demande l'acces a \"{doc.titre}\" ({demande.get_type_demande_display()})."),
                document=doc,
            )
        messages.success(request, "Votre demande de pret a ete transmise aux archivistes.")
        return redirect('archives:mes_prets')


class MesPretsView(ArchiveMixin, ListView):
    template_name = 'archives/prets/list_agent.html'
    context_object_name = 'demandes'
    paginate_by = 20

    def get_queryset(self):
        qs = DemandePret.objects.filter(
            demandeur=self.request.user
        ).select_related('document').order_by('-date_demande')
        statut = self.request.GET.get('statut', '')
        if statut in ('EN_ATTENTE', 'ACCORDEE', 'REFUSEE', 'CLOTUREE'):
            qs = qs.filter(statut=statut)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statut_filtre'] = self.request.GET.get('statut', '')
        return ctx


# ──────────────────────────────────────────────────────────────────────────────
# Prêts — ARCHIVISTE
# ──────────────────────────────────────────────────────────────────────────────

class ArchivistePretsListView(ArchiveMixin, ListView):
    template_name = 'archives/prets/list_archiviste.html'
    context_object_name = 'demandes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_gerer_prets(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        statut = self.request.GET.get('statut', 'EN_ATTENTE')
        qs = DemandePret.objects.select_related('document', 'demandeur')
        if statut in ('EN_ATTENTE', 'ACCORDEE', 'REFUSEE', 'CLOTUREE'):
            qs = qs.filter(statut=statut)
        return qs.order_by('-date_demande')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statut_filtre'] = self.request.GET.get('statut', 'EN_ATTENTE')
        return ctx


class ArchivistePretDetailView(ArchiveMixin, View):
    template_name = 'archives/prets/detail_archiviste.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_gerer_prets(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, demande, form=None):
        ctx = _notif_ctx(request)
        ctx.update({'demande': demande, 'form': form or TraiterDemandePretForm(
            initial={'duree_acces_heures': demande.duree_acces_heures}
        )})
        return ctx

    def get(self, request, pk):
        demande = get_object_or_404(DemandePret, pk=pk)
        return render(request, self.template_name, self._ctx(request, demande))

    def post(self, request, pk):
        demande = get_object_or_404(DemandePret, pk=pk)
        if demande.statut != 'EN_ATTENTE':
            messages.warning(request, "Cette demande a deja ete traitee.")
            return redirect('archives:archiviste_prets')

        form = TraiterDemandePretForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, demande, form))

        decision = form.cleaned_data['decision']

        if decision == 'REFUSEE':
            demande.statut         = 'REFUSEE'
            demande.motif_refus    = form.cleaned_data.get('motif_refus', '')
            demande.traite_par     = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            Notification.objects.create(
                destinataire=demande.demandeur,
                type=Notification.Type.PRET_REFUSE,
                titre="Demande de pret refusee",
                message=(f"Votre demande pour \"{demande.document.titre}\" a ete refusee. "
                         + (f"Motif : {demande.motif_refus}" if demande.motif_refus else "")),
                document=demande.document,
            )
            messages.warning(request, "La demande a ete refusee.")
            return redirect('archives:archiviste_prets')

        # ACCORDEE
        demande.statut         = 'ACCORDEE'
        demande.traite_par     = request.user
        demande.date_traitement = timezone.now()
        demande.save()

        if demande.type_demande == 'PHYSIQUE':
            date_retour = (
                form.cleaned_data.get('date_retour_prevue') or
                (timezone.now() + timedelta(days=14)).date()
            )
            PretDocument.objects.create(
                demande=demande,
                document=demande.document,
                emprunteur=demande.demandeur,
                accorde_par=request.user,
                date_retour_prevue=date_retour,
                statut='EN_COURS',
            )
            MouvementDocument.objects.create(
                document=demande.document, action=MouvementDocument.Action.TRANSFERT,
                utilisateur=request.user,
                commentaire=f"Pret physique accorde a {demande.demandeur} — retour prevu : {date_retour}",
            )
        else:  # NUMERIQUE
            heures   = form.cleaned_data.get('duree_acces_heures') or demande.duree_acces_heures or 24
            date_fin = timezone.now() + timedelta(hours=heures)
            AccesDocument.objects.update_or_create(
                document=demande.document, utilisateur=demande.demandeur,
                defaults={'actif': True, 'date_fin': date_fin,
                          'motif': f"Acces numerique — demande #{demande.pk}",
                          'accorde_par': request.user}
            )
            MouvementDocument.objects.create(
                document=demande.document, action=MouvementDocument.Action.CONSULTATION,
                utilisateur=request.user,
                commentaire=f"Acces numerique accorde a {demande.demandeur} pour {heures}h.",
            )

        Notification.objects.create(
            destinataire=demande.demandeur,
            type=Notification.Type.PRET_ACCORDE,
            titre="Demande de pret accordee",
            message=f"Votre demande pour \"{demande.document.titre}\" a ete accordee.",
            document=demande.document,
        )
        messages.success(request, "La demande de pret a ete accordee.")
        return redirect('archives:archiviste_prets')


def retour_pret(request, pk):
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(djsettings.LOGIN_URL)
    if not peut_gerer_prets(request.user):
        raise PermissionDenied
    pret = get_object_or_404(PretDocument, pk=pk, statut='EN_COURS')

    if request.method == 'POST':
        form = RetourPretForm(request.POST)
        if form.is_valid():
            pret.date_retour_effective = form.cleaned_data['date_retour_effective']
            pret.observations          = form.cleaned_data.get('observations', '')
            pret.statut                = 'RETOURNE'
            pret.save()
            pret.demande.statut = 'CLOTUREE'
            pret.demande.save()
            MouvementDocument.objects.create(
                document=pret.document, action=MouvementDocument.Action.RESTAURATION,
                utilisateur=request.user, commentaire="Retour du pret physique.",
            )
            messages.success(request, "Retour enregistre avec succes.")
            return redirect('archives:archiviste_prets')
    else:
        form = RetourPretForm()

    ctx = _notif_ctx(request)
    ctx.update({'pret': pret, 'form': form})
    return render(request, 'archives/prets/retour_form.html', ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Accès ABAC direct
# ──────────────────────────────────────────────────────────────────────────────

def accorder_acces_direct(request, pk):
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(djsettings.LOGIN_URL)
    if not peut_accorder_acces_special(request.user):
        raise PermissionDenied
    doc = get_object_or_404(Document, pk=pk)
    if request.method == 'POST':
        form = AccesDocumentForm(request.POST)
        if form.is_valid():
            utilisateur = get_object_or_404(User, pk=form.cleaned_data['utilisateur'])
            AccesDocument.objects.update_or_create(
                document=doc, utilisateur=utilisateur,
                defaults={'actif': True,
                          'date_fin': form.cleaned_data.get('date_fin'),
                          'motif': form.cleaned_data['motif'],
                          'accorde_par': request.user}
            )
            messages.success(request, f"Acces accorde a {utilisateur.get_full_name() or utilisateur.username}.")
        else:
            messages.error(request, "Erreur dans le formulaire d'acces.")
    return redirect('archives:document_detail', pk=pk)


# ──────────────────────────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────────────────────────

class NotificationListView(ArchiveMixin, ListView):
    template_name = 'archives/notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(
            destinataire=self.request.user
        ).order_by('-date_creation')

    def get(self, request, *args, **kwargs):
        Notification.objects.filter(destinataire=request.user, lue=False).update(lue=True)
        return super().get(request, *args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# Notification : marquer lue + rediriger
# ──────────────────────────────────────────────────────────────────────────────

def notif_marquer_lue(request, pk):
    """Marque une notification comme lue et redirige vers sa cible."""
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(djsettings.LOGIN_URL)

    notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    notif.marquer_lue()

    # Résoudre la cible de redirection selon le type
    from django.urls import reverse
    typ = notif.type
    try:
        if typ == Notification.Type.NOUVEAU_DEPOT and notif.depot_id:
            return redirect('archives:archiviste_depot_detail', pk=notif.depot_id)
        elif typ in (Notification.Type.DEPOT_ARCHIVE, Notification.Type.DEPOT_REJETE):
            if notif.depot_id:
                return redirect('archives:mes_depots')
        elif typ == Notification.Type.DEMANDE_PRET and notif.document_id:
            if est_archiviste(request.user) or est_admin(request.user):
                return redirect('archives:archiviste_prets')
            return redirect('archives:mes_prets')
        elif typ in (Notification.Type.PRET_ACCORDE, Notification.Type.PRET_REFUSE,
                     Notification.Type.PRET_RAPPEL, Notification.Type.PRET_RETARD):
            return redirect('archives:mes_prets')
        elif typ == Notification.Type.RECHERCHE_RECUE:
            if est_archiviste(request.user) or est_admin(request.user):
                return redirect('archives:archiviste_recherches')
        elif typ in (Notification.Type.RECHERCHE_ACCORDEE, Notification.Type.RECHERCHE_REFUSEE):
            if notif.document_id:
                return redirect('archives:document_detail', pk=notif.document_id)
            return redirect('archives:mes_recherches')
        elif notif.document_id:
            return redirect('archives:document_detail', pk=notif.document_id)
    except Exception:
        pass

    return redirect('archives:notifications')


# ──────────────────────────────────────────────────────────────────────────────
# Dépôts du service (agent voit les dépôts de son département)
# ──────────────────────────────────────────────────────────────────────────────

class DepotServiceView(ArchiveMixin, ListView):
    """Dépôts faits par tous les agents du même département que l'utilisateur."""
    template_name = 'archives/depots/list_service.html'
    context_object_name = 'depots'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        # Seulement les agents (pas les archivistes/admins)
        if est_archiviste(request.user) or est_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        dept = getattr(user, 'departement', None)
        if not dept:
            return DepotDocument.objects.none()
        return DepotDocument.objects.filter(
            agent__departement=dept
        ).select_related('agent', 'categorie').order_by('-date_depot')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['departement'] = getattr(user, 'departement', None)
        return ctx


# ──────────────────────────────────────────────────────────────────────────────
# Demande de recherche documentaire — AGENT
# ──────────────────────────────────────────────────────────────────────────────

class DemandeRechercheCreateView(ArchiveMixin, View):
    """Agent formule une demande de recherche sans connaître l'identifiant."""
    template_name = 'archives/prets/recherche_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_demander_pret(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, form=None):
        ctx = _notif_ctx(request)
        ctx['form'] = form or DemandeRechercheForm()
        return ctx

    def get(self, request):
        return render(request, self.template_name, self._ctx(request))

    def post(self, request):
        form = DemandeRechercheForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, form))

        cat_id = form.cleaned_data.get('categorie')
        categorie = CategorieDocument.objects.filter(pk=cat_id).first() if cat_id else None

        from users.models import Departement as DeptModel
        dept_id = form.cleaned_data.get('service_producteur')
        service_dept = DeptModel.objects.filter(pk=dept_id).first() if dept_id else None

        demande = DemandeRecherche.objects.create(
            agent=request.user,
            categorie=categorie,
            service_producteur=service_dept,
            motif=form.cleaned_data['motif'],
            description=form.cleaned_data['description'],
            statut='EN_ATTENTE',
        )
        for arch in User.objects.filter(role='ARCHIVISTE', is_active=True):
            Notification.objects.create(
                destinataire=arch,
                type=Notification.Type.RECHERCHE_RECUE,
                titre="Nouvelle demande de recherche documentaire",
                message=(
                    f"L'agent {request.user.get_full_name() or request.user.username} "
                    f"recherche un document : « {demande.description[:80]} »"
                ),
            )
        messages.success(request, "Votre demande de recherche a été transmise aux archivistes.")
        return redirect('archives:mes_recherches')


class MesRecherchesView(ArchiveMixin, ListView):
    """Liste des demandes de recherche de l'agent connecté."""
    template_name = 'archives/prets/mes_recherches.html'
    context_object_name = 'demandes'
    paginate_by = 20

    def get_queryset(self):
        return DemandeRecherche.objects.filter(
            agent=self.request.user
        ).select_related('categorie', 'document_fourni').order_by('-date_demande')


# ──────────────────────────────────────────────────────────────────────────────
# Demandes de recherche documentaire — ARCHIVISTE
# ──────────────────────────────────────────────────────────────────────────────

class ArchivisteRecherchesListView(ArchiveMixin, ListView):
    """Liste des demandes de recherche pour l'archiviste."""
    template_name = 'archives/prets/archiviste_recherches_list.html'
    context_object_name = 'demandes'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_gerer_prets(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        statut = self.request.GET.get('statut', 'EN_ATTENTE')
        qs = DemandeRecherche.objects.select_related('agent', 'categorie')
        if statut in ('EN_ATTENTE', 'ACCORDEE', 'REFUSEE'):
            qs = qs.filter(statut=statut)
        return qs.order_by('-date_demande')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statut_filtre'] = self.request.GET.get('statut', 'EN_ATTENTE')
        ctx['nb_en_attente'] = DemandeRecherche.objects.filter(statut='EN_ATTENTE').count()
        return ctx


class ArchivisteRechercheDetailView(ArchiveMixin, View):
    """Archiviste traite une demande de recherche : cherche le doc, crée le prêt."""
    template_name = 'archives/prets/archiviste_recherche_detail.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not peut_gerer_prets(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, demande, form=None):
        ctx = _notif_ctx(request)
        ctx.update({'demande': demande, 'form': form or TraiterRechercheForm()})
        return ctx

    def get(self, request, pk):
        demande = get_object_or_404(DemandeRecherche, pk=pk)
        return render(request, self.template_name, self._ctx(request, demande))

    def post(self, request, pk):
        demande = get_object_or_404(DemandeRecherche, pk=pk)
        if demande.statut != 'EN_ATTENTE':
            messages.warning(request, "Cette demande a déjà été traitée.")
            return redirect('archives:archiviste_recherches')

        form = TraiterRechercheForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, demande, form))

        decision = form.cleaned_data['decision']

        if decision == 'REFUSER':
            demande.statut         = 'REFUSEE'
            demande.motif_refus    = form.cleaned_data['motif_refus']
            demande.traite_par     = request.user
            demande.date_traitement = timezone.now()
            demande.save()
            Notification.objects.create(
                destinataire=demande.agent,
                type=Notification.Type.RECHERCHE_REFUSEE,
                titre="Recherche documentaire — document non trouvé",
                message=(
                    f"Votre demande de recherche n°{demande.pk} n'a pas abouti. "
                    f"Motif : {form.cleaned_data['motif_refus']}"
                ),
            )
            messages.warning(request, "La demande de recherche a été refusée.")
            return redirect('archives:archiviste_recherches')

        # ACCORDER — créer une DemandePret numérique directement accordée
        doc = get_object_or_404(Document, pk=form.cleaned_data['document_id'])

        pret_demande = DemandePret.objects.create(
            demandeur=demande.agent,
            document=doc,
            type_demande='NUMERIQUE',
            motif=f"Issu d'une demande de recherche #{demande.pk} : {demande.motif}",
            duree_acces_heures=24,
            statut='ACCORDEE',
            traite_par=request.user,
            date_traitement=timezone.now(),
        )

        demande.statut          = 'ACCORDEE'
        demande.document_fourni = doc
        demande.pret_cree       = pret_demande
        demande.traite_par      = request.user
        demande.date_traitement = timezone.now()
        demande.save()

        Notification.objects.create(
            destinataire=demande.agent,
            type=Notification.Type.RECHERCHE_ACCORDEE,
            titre="Recherche documentaire — document trouvé !",
            message=(
                f"Votre demande de recherche n°{demande.pk} a abouti. "
                f"Le document « {doc.titre} » ({doc.identifiant}) est disponible."
            ),
            document=doc,
        )
        messages.success(request, f"Prêt numérique accordé pour « {doc.titre} ».")
        return redirect('archives:archiviste_recherches')


# ──────────────────────────────────────────────────────────────────────────────
# Profil utilisateur
# ──────────────────────────────────────────────────────────────────────────────

class MonProfilView(ArchiveMixin, View):
    """Page profil de l'utilisateur connecté (lecture seule)."""
    template_name = 'archives/profil/mon_profil.html'

    def get(self, request):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        ctx = _notif_ctx(request)
        ctx['nb_depots'] = DepotDocument.objects.filter(agent=request.user).count()
        ctx['nb_prets'] = DemandePret.objects.filter(demandeur=request.user).count()
        ctx['nb_recherches'] = DemandeRecherche.objects.filter(agent=request.user).count()
        return render(request, self.template_name, ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Retry dépôt rejeté — l'agent reformule
# ──────────────────────────────────────────────────────────────────────────────

class RetryDepotView(ArchiveMixin, View):
    """
    L'agent peut reformuler un dépôt rejeté.
    Affiche le formulaire de dépôt pré-rempli avec les données du dépôt rejeté,
    en montrant clairement le motif de refus pour que l'agent comprenne quoi corriger.
    """
    template_name = 'archives/depots/retry_depot.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        depot = get_object_or_404(DepotDocument, pk=kwargs['pk'], agent=request.user)
        if depot.statut != 'REJETE':
            messages.warning(request, "Seuls les dépôts rejetés peuvent être reformulés.")
            return redirect('archives:mes_depots')
        self.depot_original = depot
        return super().dispatch(request, *args, **kwargs)

    def _ctx(self, request, form=None):
        ctx = _notif_ctx(request)
        ctx['depot_original'] = self.depot_original
        if form is None:
            form = DepotAgentForm(initial={
                'titre': self.depot_original.titre,
                'date_reception': self.depot_original.date_reception,
                'categorie': self.depot_original.categorie_id,
                'description': self.depot_original.description,
                'mots_cles': self.depot_original.mots_cles,
            })
        # Si un fichier original existe, le fichier n'est pas obligatoire
        if self.depot_original.fichier:
            form.fields['fichier'].required = False
            form.fields['fichier'].help_text = "Laissez vide pour conserver l'ancien fichier."
        ctx['form'] = form
        return ctx

    def get(self, request, pk):
        return render(request, self.template_name, self._ctx(request))

    def post(self, request, pk):
        form = DepotAgentForm(request.POST, request.FILES)
        # Rendre le fichier facultatif pour la reformulation
        form.fields['fichier'].required = not self.depot_original.fichier
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, form))

        cat_id = form.cleaned_data.get('categorie')
        categorie = CategorieDocument.objects.filter(pk=cat_id).first() if cat_id else None

        # Conserver l'ancien fichier si aucun nouveau n'est fourni
        fichier = request.FILES.get('fichier') or self.depot_original.fichier

        depot = DepotDocument.objects.create(
            agent=request.user,
            titre=form.cleaned_data['titre'],
            fichier=fichier,
            date_reception=form.cleaned_data.get('date_reception'),
            categorie=categorie,
            description=form.cleaned_data.get('description', ''),
            mots_cles=form.cleaned_data.get('mots_cles', ''),
            statut='EN_ATTENTE',
        )
        # Notifier les archivistes
        for arch in User.objects.filter(role='ARCHIVISTE', is_active=True):
            Notification.objects.create(
                destinataire=arch,
                type=Notification.Type.NOUVEAU_DEPOT,
                titre="Nouveau dépôt — reformulation",
                message=(
                    f"{request.user.get_full_name() or request.user.username} "
                    f"a reformulé son dépôt rejeté. "
                    f"Nouveau récépissé : {depot.numero_recepisse}"
                ),
                depot=depot,
            )
        messages.success(
            request,
            f"Votre dépôt reformulé a été soumis (récépissé : {depot.numero_recepisse})."
        )
        return redirect('archives:mes_depots')


# ──────────────────────────────────────────────────────────────────────────────
# Mixin d'administration — réservé aux archivistes et admins
# ──────────────────────────────────────────────────────────────────────────────

class AdminMixin(ArchiveMixin):
    """Mixin qui contrôle l'accès aux pages d'administration métier."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as djsettings
            return redirect(djsettings.LOGIN_URL)
        if not (est_archiviste(request.user) or est_admin(request.user)):
            raise PermissionDenied
        return super(ArchiveMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = _notif_ctx(self.request)
        ctx.update(kwargs)
        return ctx


def _admin_guard(request):
    """Vérification pour les vues FBV admin."""
    if not request.user.is_authenticated:
        from django.conf import settings as djsettings
        return redirect(djsettings.LOGIN_URL)
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Admin — Catégories de documents
# ──────────────────────────────────────────────────────────────────────────────

def admin_categories_list(request):
    guard = _admin_guard(request)
    if guard:
        return guard
    categories = CategorieDocument.objects.annotate(
        nb_documents=__import__('django.db.models', fromlist=['Count']).Count('document')
    ).order_by('code')
    ctx = _notif_ctx(request)
    ctx['categories'] = categories
    return render(request, 'archives/admin/categories/list.html', ctx)


def admin_categorie_create(request):
    guard = _admin_guard(request)
    if guard:
        return guard
    if request.method == 'POST':
        form = CategorieDocumentForm(request.POST)
        if form.is_valid():
            from django.db import IntegrityError
            try:
                cat = CategorieDocument.objects.create(
                    code=form.cleaned_data['code'],
                    nom=form.cleaned_data['nom'],
                    description=form.cleaned_data.get('description', ''),
                )
                messages.success(request, f"Catégorie [{cat.code}] créée avec succès.")
                return redirect('archives:admin_categories')
            except IntegrityError:
                form.add_error('code', "Ce code existe déjà.")
    else:
        form = CategorieDocumentForm()
    ctx = _notif_ctx(request)
    ctx.update({'form': form, 'action': 'Créer', 'titre_page': 'Nouvelle catégorie'})
    return render(request, 'archives/admin/categories/form.html', ctx)


def admin_categorie_edit(request, pk):
    guard = _admin_guard(request)
    if guard:
        return guard
    cat = get_object_or_404(CategorieDocument, pk=pk)
    if request.method == 'POST':
        form = CategorieDocumentForm(request.POST)
        if form.is_valid():
            from django.db import IntegrityError
            try:
                cat.code        = form.cleaned_data['code']
                cat.nom         = form.cleaned_data['nom']
                cat.description = form.cleaned_data.get('description', '')
                cat.save()
                messages.success(request, "Catégorie modifiée.")
                return redirect('archives:admin_categories')
            except IntegrityError:
                form.add_error('code', "Ce code existe déjà.")
    else:
        form = CategorieDocumentForm(initial={
            'code': cat.code, 'nom': cat.nom, 'description': cat.description
        })
    ctx = _notif_ctx(request)
    ctx.update({'form': form, 'objet': cat, 'action': 'Modifier', 'titre_page': f'Modifier [{cat.code}]'})
    return render(request, 'archives/admin/categories/form.html', ctx)


def admin_categorie_delete(request, pk):
    guard = _admin_guard(request)
    if guard:
        return guard
    cat = get_object_or_404(CategorieDocument, pk=pk)
    nb_docs = Document.objects.filter(categorie=cat, deleted_at__isnull=True).count()
    if request.method == 'POST':
        if nb_docs > 0:
            messages.error(request, f"Impossible : {nb_docs} document(s) utilisent cette catégorie.")
            return redirect('archives:admin_categories')
        nom = str(cat)
        cat.delete()
        messages.success(request, f"Catégorie «{nom}» supprimée.")
        return redirect('archives:admin_categories')
    ctx = _notif_ctx(request)
    ctx.update({'objet': cat, 'nb_docs': nb_docs, 'titre_page': 'Supprimer la catégorie'})
    return render(request, 'archives/admin/categories/confirm_delete.html', ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Admin — Plan de classement
# ──────────────────────────────────────────────────────────────────────────────

def admin_plans_list(request):
    guard = _admin_guard(request)
    if guard:
        return guard
    plans = PlanClassement.objects.select_related('parent', 'categorie').order_by('code')
    ctx = _notif_ctx(request)
    ctx['plans'] = plans
    return render(request, 'archives/admin/plans/list.html', ctx)


def admin_plan_create(request):
    guard = _admin_guard(request)
    if guard:
        return guard
    if request.method == 'POST':
        form = PlanClassementForm(request.POST)
        if form.is_valid():
            from django.db import IntegrityError
            try:
                parent_pk = form.cleaned_data.get('parent')
                cat_pk    = form.cleaned_data.get('categorie')
                plan = PlanClassement.objects.create(
                    code=form.cleaned_data['code'],
                    intitule=form.cleaned_data['intitule'],
                    niveau=form.cleaned_data['niveau'],
                    parent_id=parent_pk or None,
                    categorie_id=cat_pk or None,
                    description=form.cleaned_data.get('description', ''),
                    actif=form.cleaned_data.get('actif', True),
                )
                messages.success(request, f"Plan de classement «{plan.code}» créé.")
                return redirect('archives:admin_plans')
            except IntegrityError:
                form.add_error('code', "Cette cote existe déjà.")
    else:
        form = PlanClassementForm()
    ctx = _notif_ctx(request)
    ctx.update({'form': form, 'action': 'Créer', 'titre_page': 'Nouveau plan de classement'})
    return render(request, 'archives/admin/plans/form.html', ctx)


def admin_plan_edit(request, pk):
    guard = _admin_guard(request)
    if guard:
        return guard
    plan = get_object_or_404(PlanClassement, pk=pk)
    if request.method == 'POST':
        form = PlanClassementForm(request.POST)
        if form.is_valid():
            from django.db import IntegrityError
            try:
                parent_pk = form.cleaned_data.get('parent')
                cat_pk    = form.cleaned_data.get('categorie')
                plan.code        = form.cleaned_data['code']
                plan.intitule    = form.cleaned_data['intitule']
                plan.niveau      = form.cleaned_data['niveau']
                plan.parent_id   = parent_pk or None
                plan.categorie_id = cat_pk or None
                plan.description = form.cleaned_data.get('description', '')
                plan.actif       = form.cleaned_data.get('actif', True)
                plan.save()
                messages.success(request, "Plan de classement modifié.")
                return redirect('archives:admin_plans')
            except IntegrityError:
                form.add_error('code', "Cette cote existe déjà.")
    else:
        form = PlanClassementForm(initial={
            'code': plan.code, 'intitule': plan.intitule, 'niveau': plan.niveau,
            'parent': plan.parent_id, 'categorie': plan.categorie_id,
            'description': plan.description, 'actif': plan.actif,
        })
    ctx = _notif_ctx(request)
    ctx.update({'form': form, 'objet': plan, 'action': 'Modifier', 'titre_page': f'Modifier {plan.code}'})
    return render(request, 'archives/admin/plans/form.html', ctx)


def admin_plan_delete(request, pk):
    guard = _admin_guard(request)
    if guard:
        return guard
    plan = get_object_or_404(PlanClassement, pk=pk)
    nb_docs = Document.objects.filter(plan_classement=plan, deleted_at__isnull=True).count()
    nb_enfants = PlanClassement.objects.filter(parent=plan).count()
    if request.method == 'POST':
        if nb_docs > 0 or nb_enfants > 0:
            messages.error(request, f"Impossible : {nb_docs} document(s) et {nb_enfants} sous-rubrique(s) liés.")
            return redirect('archives:admin_plans')
        nom = str(plan)
        plan.delete()
        messages.success(request, f"Plan «{nom}» supprimé.")
        return redirect('archives:admin_plans')
    ctx = _notif_ctx(request)
    ctx.update({'objet': plan, 'nb_docs': nb_docs, 'nb_enfants': nb_enfants, 'titre_page': 'Supprimer le plan'})
    return render(request, 'archives/admin/plans/confirm_delete.html', ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Admin — Journal d'audit
# ──────────────────────────────────────────────────────────────────────────────

def admin_journal(request):
    guard = _admin_guard(request)
    if guard:
        return guard

    qs = MouvementDocument.objects.select_related('document', 'utilisateur').order_by('-date_action')

    # Filtres
    action_filtre = request.GET.get('action', '')
    user_filtre   = request.GET.get('utilisateur', '')
    doc_filtre    = request.GET.get('document', '').strip()
    date_debut    = request.GET.get('date_debut', '')
    date_fin      = request.GET.get('date_fin', '')

    if action_filtre and action_filtre in [a[0] for a in MouvementDocument.Action.choices]:
        qs = qs.filter(action=action_filtre)
    if user_filtre:
        qs = qs.filter(utilisateur_id=user_filtre)
    if doc_filtre:
        qs = qs.filter(
            Q(document__identifiant__icontains=doc_filtre) |
            Q(document__titre__icontains=doc_filtre)
        )
    if date_debut:
        try:
            from datetime import datetime
            qs = qs.filter(date_action__date__gte=datetime.strptime(date_debut, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_fin:
        try:
            from datetime import datetime
            qs = qs.filter(date_action__date__lte=datetime.strptime(date_fin, '%Y-%m-%d').date())
        except ValueError:
            pass

    from django.core.paginator import Paginator
    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    ctx = _notif_ctx(request)
    ctx.update({
        'page_obj':       page_obj,
        'mouvements':     page_obj,
        'actions':        MouvementDocument.Action.choices,
        'utilisateurs':   User.objects.filter(is_active=True).order_by('last_name'),
        'action_filtre':  action_filtre,
        'user_filtre':    user_filtre,
        'doc_filtre':     doc_filtre,
        'date_debut':     date_debut,
        'date_fin':       date_fin,
        'total':          qs.count(),
    })
    return render(request, 'archives/admin/journal/list.html', ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Admin — Provenance externe (AJAX endpoint + CRUD)
# ──────────────────────────────────────────────────────────────────────────────

def admin_provenance_create_ajax(request):
    """Endpoint AJAX pour créer une provenance externe via le popup du formulaire de dépôt."""
    from django.http import JsonResponse
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Non authentifié'}, status=401)
    if not (est_archiviste(request.user) or est_admin(request.user)):
        return JsonResponse({'ok': False, 'error': 'Accès refusé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Méthode non supportée'}, status=405)
    form = ProvenanceExterneForm(request.POST)
    if form.is_valid():
        from django.db import IntegrityError
        try:
            prov = ProvenanceExterne.objects.create(
                code=form.cleaned_data['code'],
                nom=form.cleaned_data['nom'],
                description=form.cleaned_data.get('description', ''),
                actif=form.cleaned_data.get('actif', True),
            )
            return JsonResponse({'ok': True, 'id': prov.pk, 'label': str(prov)})
        except IntegrityError:
            return JsonResponse({'ok': False, 'error': 'Ce code existe déjà.'}, status=400)
    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)


# ==============================================================================
# ==============================================================================
# BORDEREAUX DE VERSEMENT — AUTO-GÉNÉRÉS PAR SERVICE / EXERCICE (loi 2006-19)
# ==============================================================================

@login_required
def admin_bordereaux_versement(request):
    """Liste de tous les bordereaux de versement, groupés par exercice."""
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    import datetime
    qs = BordereauVersement.objects.select_related('cree_par', 'valide_par').order_by('-exercice', '-date_creation')

    # Services ayant des dépôts ARCHIVE non encore couverts par un BV cette année
    annee_courante = datetime.date.today().year
    depots_sans_bv = DepotDocument.objects.filter(
        statut='ARCHIVE',
        bordereaux_versement__isnull=True,
    ).values_list('agent__departement__nom', flat=True).distinct()

    return render(request, 'archives/admin/bordereaux/versement_list.html', {
        **_notif_ctx(request),
        'bordereaux':       qs,
        'annee_courante':   annee_courante,
        'services_en_attente': list(filter(None, depots_sans_bv)),
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'), ('Bordereaux de versement', None)],
    })


@login_required
def admin_bordereau_versement_generer(request):
    """
    Génère automatiquement un bordereau de versement pour un service et un exercice donnés.
    Tous les dépôts archivés de ce service pendant l'exercice sont inclus.
    """
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied

    import datetime
    annee_courante = datetime.date.today().year

    # Services qui ont des dépôts ARCHIVE
    from django.db.models import Count
    services_dispo = (
        DepotDocument.objects.filter(statut='ARCHIVE')
        .exclude(agent__isnull=True)
        .values('agent__departement__nom', 'agent__departement__pk')
        .annotate(nb=Count('pk'))
        .order_by('agent__departement__nom')
    )
    exercices_dispo = list(range(annee_courante, annee_courante - 6, -1))

    ctx = {
        **_notif_ctx(request),
        'services_dispo':  services_dispo,
        'exercices_dispo': exercices_dispo,
        'annee_courante':  annee_courante,
        'apercu': None,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Bordereaux versement', 'archives:admin_bordereaux_versement'),
                       ('Générer', None)],
    }

    if request.method == 'POST':
        action         = request.POST.get('action', 'apercu')
        service_nom    = request.POST.get('service', '').strip()
        exercice_str   = request.POST.get('exercice', str(annee_courante))
        observations   = request.POST.get('observations', '').strip()

        try:
            exercice = int(exercice_str)
        except ValueError:
            messages.error(request, "Exercice invalide.")
            return render(request, 'archives/admin/bordereaux/versement_form.html', ctx)

        # Dépôts éligibles : ARCHIVE, du service, de l'exercice
        depots_qs = DepotDocument.objects.filter(
            statut='ARCHIVE',
            date_depot__year=exercice,
        ).select_related('agent', 'agent__departement', 'categorie', 'document_archive')

        if service_nom:
            depots_qs = depots_qs.filter(agent__departement__nom=service_nom)

        # Exclure dépôts déjà couverts par un BV pour ce service+exercice
        bv_existant = BordereauVersement.objects.filter(
            service_versant=service_nom, exercice=exercice
        ).exclude(statut='REJETE').first()

        depots_deja_couverts = set()
        if bv_existant:
            depots_deja_couverts = set(bv_existant.depots.values_list('pk', flat=True))
        depots_qs = depots_qs.exclude(pk__in=depots_deja_couverts).order_by('date_depot')

        ctx.update({
            'service_nom':   service_nom,
            'exercice':      exercice,
            'observations':  observations,
            'apercu':        list(depots_qs),
            'bv_existant':   bv_existant,
        })

        if action == 'generer' and depots_qs.exists():
            numero = f"BV-{service_nom[:6].upper().replace(' ', '')}-{exercice}-{BordereauVersement.objects.count() + 1:04d}"
            bv = BordereauVersement.objects.create(
                numero=numero,
                service_versant=service_nom,
                service_destinataire='Service des Archives — ENSMG',
                exercice=exercice,
                observations=observations or f'Bordereau de versement — {service_nom} — Exercice {exercice}',
                cree_par=request.user,
            )
            bv.depots.set(depots_qs)
            # Lier aussi les documents d'archives issus des dépôts
            docs_archives = Document.objects.filter(
                depot_source__in=depots_qs
            )
            bv.documents.set(docs_archives)

            # Notification au service concerné
            agents_service = User.objects.filter(
                departement__nom=service_nom, is_active=True
            )[:1]
            for agent in agents_service:
                Notification.objects.create(
                    destinataire=agent,
                    type='SYSTEME',
                    titre=f'Bordereau de versement {numero} — {exercice}',
                    message=(
                        f'Un bordereau de versement ({numero}) a été établi pour votre service '
                        f'"{service_nom}" couvrant l\'exercice {exercice}. '
                        f'Il recense {depots_qs.count()} dépôt(s) effectué(s) durant cet exercice.'
                    ),
                )

            messages.success(request,
                f"Bordereau {numero} généré avec {depots_qs.count()} dépôt(s) — exercice {exercice}.")
            return redirect('archives:admin_bordereau_versement_detail', pk=bv.pk)

        if action == 'generer' and not depots_qs.exists():
            messages.warning(request, "Aucun dépôt éligible pour ce service et cet exercice.")

    return render(request, 'archives/admin/bordereaux/versement_form.html', ctx)


@login_required
def admin_bordereau_versement_detail(request, pk):
    """Détail d'un bordereau — workflow + impression institutionnelle."""
    bv = get_object_or_404(BordereauVersement, pk=pk)
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action')
        import datetime as dt
        if action == 'soumettre' and bv.statut == 'BROUILLON':
            bv.statut = 'EN_VALIDATION'
            bv.save()
            messages.info(request, "Bordereau soumis pour validation.")
        elif action == 'valider' and bv.statut == 'EN_VALIDATION':
            bv.statut = 'VALIDE'
            bv.valide_par = request.user
            bv.date_validation = dt.date.today()
            bv.save()
            messages.success(request, "Bordereau validé ✓")
        elif action == 'executer' and bv.statut == 'VALIDE':
            bv.statut = 'EXECUTE'
            bv.save()
            bv.documents.all().update(statut='VERSE')
            messages.success(request, "Versement exécuté.")
        elif action == 'rejeter':
            bv.statut = 'REJETE'
            bv.save()
            messages.warning(request, "Bordereau rejeté.")
        return redirect('archives:admin_bordereau_versement_detail', pk=pk)

    # Dépôts inclus triés chronologiquement
    depots = bv.depots.select_related(
        'agent', 'agent__departement', 'categorie', 'document_archive'
    ).order_by('date_depot')

    return render(request, 'archives/admin/bordereaux/versement_detail.html', {
        **_notif_ctx(request),
        'bv':     bv,
        'depots': depots,
        'docs':   bv.documents.select_related('categorie', 'plan_classement'),
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Bordereaux versement', 'archives:admin_bordereaux_versement'),
                       (bv.numero, None)],
    })


# ==============================================================================
# BORDEREAUX D'ÉLIMINATION — AUTORISATION DAS + CONSTAT DE DESTRUCTION
# ==============================================================================

@login_required
def admin_bordereaux_elimination(request):
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    qs = BordereauElimination.objects.select_related('cree_par').order_by('-date_creation')
    # Documents avec DUA échue et sort_final ELIMINATION non encore traités
    docs_a_traiter = Document.objects.filter(
        sort_final='ELIMINATION',
        deleted_at__isnull=True,
    ).exclude(statut__in=['ELIMINE', 'EN_ELIMINATION']).count()
    return render(request, 'archives/admin/bordereaux/elimination_list.html', {
        **_notif_ctx(request),
        'bordereaux':      qs,
        'docs_a_traiter':  docs_a_traiter,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'), ("Bordereaux d'élimination", None)],
    })


@login_required
def admin_bordereau_elimination_create(request):
    """
    L'archiviste sélectionne les documents physiques à éliminer.
    → Crée une DEMANDE D'AUTORISATION (statut BROUILLON).
    → Soumise à la Direction des Archives du Sénégal pour visa.
    """
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied

    docs_eligibles = Document.objects.filter(
        sort_final='ELIMINATION',
        deleted_at__isnull=True,
    ).exclude(statut__in=['ELIMINE', 'EN_ELIMINATION']).select_related(
        'categorie', 'plan_classement', 'tableau_gestion'
    ).order_by('date_creation')

    if request.method == 'POST':
        doc_ids      = request.POST.getlist('documents')
        service      = request.POST.get('service_producteur', 'ENSMG').strip()
        motif        = request.POST.get('motif', '').strip()
        observations = request.POST.get('observations', '').strip()
        if not doc_ids:
            messages.error(request, "Sélectionnez au moins un document.")
        elif not motif:
            messages.error(request, "Le motif d'élimination est obligatoire.")
        else:
            import datetime
            numero = f"BE-{datetime.date.today().strftime('%Y%m%d')}-{BordereauElimination.objects.count() + 1:04d}"
            be = BordereauElimination.objects.create(
                numero=numero,
                service_producteur=service,
                motif=motif,
                observations=observations,
                cree_par=request.user,
            )
            docs = Document.objects.filter(pk__in=doc_ids, deleted_at__isnull=True)
            be.documents.set(docs)
            docs.update(statut='EN_ELIMINATION')
            messages.success(request,
                f"Demande d'autorisation {numero} créée ({docs.count()} doc(s)). "
                "En attente du visa de la DAS.")
            return redirect('archives:admin_bordereau_elimination_detail', pk=be.pk)

    return render(request, 'archives/admin/bordereaux/elimination_form.html', {
        **_notif_ctx(request),
        'docs_eligibles': docs_eligibles,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ("Bordereaux élimination", 'archives:admin_bordereaux_elimination'),
                       ('Nouvelle demande', None)],
    })


@login_required
def admin_bordereau_elimination_detail(request, pk):
    """
    Détail d'un bordereau d'élimination + workflow :
      BROUILLON → EN_VALIDATION (soumis DAS) → VISA_OBTENU → EXECUTE (constat de destruction)
    """
    be = get_object_or_404(BordereauElimination, pk=pk)
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action')
        import datetime

        if action == 'soumettre' and be.statut == 'BROUILLON':
            be.statut = 'EN_VALIDATION'
            be.save()
            messages.info(request,
                "Demande soumise à la Direction des Archives du Sénégal. En attente du visa.")

        elif action == 'visa' and be.statut == 'EN_VALIDATION' and est_admin(request.user):
            ref = request.POST.get('reference_visa', '').strip()
            if not ref:
                messages.error(request, "La référence du visa DAS est obligatoire.")
            else:
                be.visa_das        = True
                be.date_visa       = datetime.date.today()
                be.reference_visa  = ref
                be.statut          = 'VISA_OBTENU'
                be.save()
                messages.success(request,
                    f"Visa DAS enregistré (réf. {ref}). L'archiviste est autorisé à procéder à la destruction.")

        elif action == 'executer' and be.statut == 'VISA_OBTENU':
            # ── CONSTAT DE DESTRUCTION ──────────────────────────────────────
            # Le jour J de la destruction physique, le bordereau est clôturé
            # et tous les documents sont définitivement éliminés.
            be.statut = 'EXECUTE'
            be.date_elimination = datetime.date.today()
            be.save()
            docs = be.documents.all()
            nb_elimines = docs.count()
            for doc in docs:
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'ELIMINATION',
                    utilisateur = request.user,
                    commentaire = (
                        f"Destruction physique le {be.date_elimination} — "
                        f"Bordereau {be.numero} — Visa DAS {be.reference_visa}"
                    ),
                    details = {
                        'bordereau':    be.numero,
                        'visa_das':     be.reference_visa,
                        'date_visa':    str(be.date_visa),
                        'date_destruction': str(be.date_elimination),
                    },
                    adresse_ip = request.META.get('REMOTE_ADDR'),
                )
                # Suppression physique du fichier numérique s'il existe
                if doc.fichier:
                    try:
                        doc.fichier.delete(save=False)
                    except Exception:
                        pass
            docs.update(statut='ELIMINE')
            messages.success(request,
                f"Constat de destruction établi. {nb_elimines} document(s) définitivement éliminé(s) "
                f"le {be.date_elimination:%d/%m/%Y}.")

        elif action == 'rejeter' and est_admin(request.user):
            be.statut = 'REJETE'
            be.save()
            be.documents.all().update(statut='DEFINITIF')
            messages.warning(request,
                "Visa refusé par la DAS. Documents remis en statut Définitif.")

        return redirect('archives:admin_bordereau_elimination_detail', pk=pk)

    docs = be.documents.select_related('categorie', 'plan_classement', 'tableau_gestion').order_by('titre')
    return render(request, 'archives/admin/bordereaux/elimination_detail.html', {
        **_notif_ctx(request),
        'be':   be,
        'docs': docs,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ("Bordereaux élimination", 'archives:admin_bordereaux_elimination'),
                       (be.numero, None)],
    })


# ==============================================================================
# CORBEILLE (soft delete / récupération)
# ==============================================================================

@login_required
def corbeille_list(request):
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    docs = Document.objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
    return render(request, 'archives/admin/corbeille/list.html', {
        **_notif_ctx(request),
        'docs': docs,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'), ('Corbeille', None)],
    })


@login_required
def corbeille_restaurer(request, pk):
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    doc = get_object_or_404(Document, pk=pk, deleted_at__isnull=False)
    if request.method == 'POST':
        doc.deleted_at = None
        doc.save()
        MouvementDocument.objects.create(
            document=doc, action='RESTAURATION',
            utilisateur=request.user,
            commentaire='Restauré depuis la corbeille',
            adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f"« {doc.titre} » restauré avec succès.")
        return redirect('archives:corbeille')
    return render(request, 'archives/admin/corbeille/confirmer_restauration.html', {
        **_notif_ctx(request), 'doc': doc,
    })


@login_required
def document_supprimer(request, pk):
    """Envoi en corbeille (soft delete)."""
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    doc = get_object_or_404(Document, pk=pk, deleted_at__isnull=True)
    if request.method == 'POST':
        doc.deleted_at = timezone.now()
        doc.save()
        MouvementDocument.objects.create(
            document=doc, action='MODIFICATION',
            utilisateur=request.user,
            commentaire='Envoyé en corbeille',
            adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.warning(request, f"« {doc.titre} » déplacé en corbeille. Récupérable sous 30 jours.")
        return redirect('archives:document_list')
    return render(request, 'archives/admin/corbeille/confirmer_suppression.html', {
        **_notif_ctx(request), 'doc': doc,
    })


# ==============================================================================
# MODE AUDIT TEMPORAIRE
# ==============================================================================

@login_required
def audit_tokens_list(request):
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    tokens = AuditToken.objects.select_related('cree_par').order_by('-date_creation')
    return render(request, 'archives/admin/audit/tokens_list.html', {
        **_notif_ctx(request),
        'tokens': tokens,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'), ('Accès auditeurs', None)],
    })


@login_required
def audit_token_create(request):
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    categories = CategorieDocument.objects.all()
    plans = PlanClassement.objects.all()

    if request.method == 'POST':
        import secrets as _secrets
        import datetime
        duree_jours = int(request.POST.get('duree_jours', 2))
        duree_jours = max(1, min(duree_jours, 30))
        now = timezone.now()

        token = AuditToken(
            description=request.POST.get('description', 'Mission d\'audit'),
            auditeur_nom=request.POST.get('auditeur_nom', ''),
            auditeur_email=request.POST.get('auditeur_email', ''),
            perimetre=request.POST.get('perimetre', 'TOUS'),
            confidentialite_max=request.POST.get('confidentialite_max', 'INTERNE'),
            date_debut=now,
            date_expiration=now + timezone.timedelta(days=duree_jours),
            cree_par=request.user,
        )
        token.save()

        if token.perimetre == 'CATEGORIE':
            cat_ids = request.POST.getlist('categories')
            token.categories.set(CategorieDocument.objects.filter(pk__in=cat_ids))
        elif token.perimetre == 'PLAN':
            plan_ids = request.POST.getlist('plans')
            token.plans.set(PlanClassement.objects.filter(pk__in=plan_ids))

        messages.success(
            request,
            f"Token créé — valide {duree_jours} jour(s). "
            f"Lien : /audit/{token.token}/"
        )
        return redirect('archives:audit_token_detail', pk=token.pk)

    return render(request, 'archives/admin/audit/token_form.html', {
        **_notif_ctx(request),
        'categories': categories,
        'plans': plans,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Accès auditeurs', 'archives:audit_tokens'),
                       ('Nouveau token', None)],
    })


@login_required
def audit_token_detail(request, pk):
    token = get_object_or_404(AuditToken, pk=pk)
    if not (est_archiviste(request.user) or est_admin(request.user)):
        raise PermissionDenied
    if request.method == 'POST' and request.POST.get('action') == 'revoquer':
        token.actif = False
        token.save()
        messages.warning(request, "Token révoqué.")
        return redirect('archives:audit_tokens')
    return render(request, 'archives/admin/audit/token_detail.html', {
        **_notif_ctx(request), 'token': token,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Accès auditeurs', 'archives:audit_tokens'),
                       (token.auditeur_nom[:30], None)],
    })


def audit_acces(request, token_str):
    """Vue publique (sans login) accessible via le token d'audit."""
    token = get_object_or_404(AuditToken, token=token_str, actif=True)
    if not token.est_valide:
        return render(request, 'archives/audit/expired.html', {'token': token}, status=403)

    # Incrémenter le compteur
    AuditToken.objects.filter(pk=token.pk).update(
        nb_consultations=token.nb_consultations + 1,
        derniere_consultation=timezone.now(),
    )

    # Construire le queryset selon le périmètre
    CONF_ORDER = ['PUBLIC', 'INTERNE', 'CONFIDENTIEL', 'SECRET']
    conf_max_idx = CONF_ORDER.index(token.confidentialite_max)
    niveaux_autorises = CONF_ORDER[:conf_max_idx + 1]

    docs = Document.objects.filter(
        confidentialite__in=niveaux_autorises,
        deleted_at__isnull=True,
    ).exclude(statut='ELIMINE').select_related('categorie', 'plan_classement')

    if token.perimetre == 'CATEGORIE' and token.categories.exists():
        docs = docs.filter(categorie__in=token.categories.all())
    elif token.perimetre == 'PLAN' and token.plans.exists():
        docs = docs.filter(plan_classement__in=token.plans.all())
    elif token.perimetre == 'SELECTION' and token.documents.exists():
        docs = docs.filter(pk__in=token.documents.all())

    return render(request, 'archives/audit/acces.html', {
        'token': token,
        'docs': docs.order_by('-date_enregistrement')[:200],
        'nb_docs': docs.count(),
    })


# ==============================================================================
# ACTIONS EN MASSE SUR LES DOCUMENTS
# ==============================================================================

@login_required
def documents_bulk_action(request):
    """Endpoint AJAX pour les actions en masse."""
    if not (est_archiviste(request.user) or est_admin(request.user)):
        return JsonResponse({'ok': False, 'error': 'Permission refusée.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    action = data.get('action')
    doc_ids = data.get('ids', [])

    if not doc_ids or not action:
        return JsonResponse({'ok': False, 'error': 'Paramètres manquants.'}, status=400)

    docs = Document.objects.filter(pk__in=doc_ids, deleted_at__isnull=True)
    count = docs.count()

    TRANSITION_MAP = {
        'courant':        'COURANT',
        'intermediaire':  'INTERMEDIAIRE',
        'definitif':      'DEFINITIF',
    }

    if action in TRANSITION_MAP:
        nouveau_statut = TRANSITION_MAP[action]
        for doc in docs:
            ancien = doc.statut
            doc.statut = nouveau_statut
            doc.save()
            MouvementDocument.objects.create(
                document=doc, action='CHANGEMENT_STATUT',
                utilisateur=request.user,
                commentaire=f"Action en masse : {ancien} → {nouveau_statut}",
                details={'avant': ancien, 'apres': nouveau_statut},
                adresse_ip=request.META.get('REMOTE_ADDR'),
            )
        return JsonResponse({'ok': True, 'count': count, 'message': f"{count} document(s) mis en « {nouveau_statut} »."})

    elif action == 'corbeille':
        now = timezone.now()
        for doc in docs:
            doc.deleted_at = now
            doc.save()
        return JsonResponse({'ok': True, 'count': count, 'message': f"{count} document(s) envoyé(s) en corbeille."})

    return JsonResponse({'ok': False, 'error': f'Action inconnue : {action}'}, status=400)


# ==============================================================================
# DASHBOARD — données enrichies (DUA + statistiques)
# ==============================================================================

@login_required
def dashboard_stats_api(request):
    """Endpoint JSON pour les graphiques du dashboard."""
    if not (est_archiviste(request.user) or est_admin(request.user)):
        return JsonResponse({}, status=403)

    from django.db.models import Count
    from archives.models import TableauGestion

    aujourd_hui = timezone.now().date()

    # Répartition par phase
    phases = Document.objects.filter(deleted_at__isnull=True).exclude(
        statut__in=['ELIMINE', 'VERSE']
    ).values('statut').annotate(n=Count('id'))

    phase_labels = {
        'COURANT': 'Courant', 'INTERMEDIAIRE': 'Intermédiaire',
        'DEFINITIF': 'Définitif', 'EN_VERSEMENT': 'En versement',
        'EN_ELIMINATION': 'En élimination',
    }
    phases_data = {phase_labels.get(p['statut'], p['statut']): p['n'] for p in phases}

    # Dépôts des 6 derniers mois
    from datetime import timedelta
    depots_par_mois = []
    for i in range(5, -1, -1):
        mois = aujourd_hui.replace(day=1) - timedelta(days=i * 30)
        n = DepotDocument.objects.filter(
            date_depot__year=mois.year,
            date_depot__month=mois.month,
        ).count()
        depots_par_mois.append({'mois': mois.strftime('%b %Y'), 'n': n})

    # DUA à venir (30 jours)
    nb_dua_alerte = Document.objects.filter(
        date_fin_dua__lte=aujourd_hui + timedelta(days=30),
        date_fin_dua__gt=aujourd_hui,
        deleted_at__isnull=True,
    ).count()

    nb_dua_echues = Document.objects.filter(
        date_fin_dua__lte=aujourd_hui,
        deleted_at__isnull=True,
    ).exclude(statut__in=['ELIMINE', 'VERSE']).count()

    return JsonResponse({
        'phases': phases_data,
        'depots_par_mois': depots_par_mois,
        'nb_dua_alerte': nb_dua_alerte,
        'nb_dua_echues': nb_dua_echues,
        'nb_corbeille': Document.objects.filter(deleted_at__isnull=False).count(),
    })


# ==============================================================================
# MESSAGERIE INTERNE
# ==============================================================================

@login_required
def messagerie_reception(request):
    """Boîte de réception — messages reçus non mis en corbeille."""
    receptions = (
        MessageDestinataire.objects
        .filter(destinataire=request.user, en_corbeille=False)
        .select_related('message', 'message__expediteur')
        .order_by('-message__date_envoi')
    )
    nb_non_lus = receptions.filter(lu=False).count()
    ctx = {
        **_notif_ctx(request),
        'receptions': receptions,
        'nb_non_lus': nb_non_lus,
        'vue_active': 'reception',
    }
    return render(request, 'archives/messagerie/reception.html', ctx)


@login_required
def messagerie_envoyes(request):
    """Messages envoyés par l'utilisateur courant."""
    messages_envoyes = (
        Message.objects
        .filter(expediteur=request.user)
        .prefetch_related('messagedestinataire_set__destinataire')
        .order_by('-date_envoi')
    )
    ctx = {
        **_notif_ctx(request),
        'messages_envoyes': messages_envoyes,
        'vue_active': 'envoyes',
    }
    return render(request, 'archives/messagerie/envoyes.html', ctx)


@login_required
def messagerie_detail(request, pk):
    """Affiche un message et son fil de réponses. Marque comme lu."""
    # L'utilisateur doit être expéditeur ou destinataire
    msg = get_object_or_404(Message, pk=pk)
    est_expediteur = (msg.expediteur == request.user)
    try:
        reception = MessageDestinataire.objects.get(message=msg, destinataire=request.user)
        reception.marquer_lu()
    except MessageDestinataire.DoesNotExist:
        reception = None
        if not est_expediteur:
            raise PermissionDenied

    # Fil de réponses (direct seulement, pas récursif)
    reponses = msg.reponses.prefetch_related('messagedestinataire_set__destinataire').order_by('date_envoi')

    ctx = {
        **_notif_ctx(request),
        'msg': msg,
        'reponses': reponses,
        'est_expediteur': est_expediteur,
        'reception': reception,
        'vue_active': 'detail',
    }
    return render(request, 'archives/messagerie/detail.html', ctx)


@login_required
def messagerie_nouveau(request):
    """Composer et envoyer un nouveau message."""
    users_disponibles = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('last_name', 'first_name')

    if request.method == 'POST':
        objet   = request.POST.get('objet', '').strip()
        corps   = request.POST.get('corps', '').strip()
        dest_ids = request.POST.getlist('destinataires')
        doc_id  = request.POST.get('document_lie') or None
        courrier_id = request.POST.get('courrier_lie') or None

        if not objet or not corps or not dest_ids:
            messages.error(request, "L'objet, le corps et au moins un destinataire sont obligatoires.")
        else:
            destinataires = User.objects.filter(pk__in=dest_ids, is_active=True)
            if not destinataires.exists():
                messages.error(request, "Aucun destinataire valide sélectionné.")
            else:
                msg = Message(
                    expediteur=request.user,
                    objet=objet,
                    corps=corps,
                )
                if doc_id:
                    try:
                        msg.document = Document.objects.get(pk=doc_id)
                    except Document.DoesNotExist:
                        pass
                if request.FILES.get('piece_jointe'):
                    msg.piece_jointe = request.FILES['piece_jointe']
                msg.save()
                for dest in destinataires:
                    MessageDestinataire.objects.create(message=msg, destinataire=dest)
                messages.success(request, f"Message envoyé à {destinataires.count()} destinataire(s).")
                return redirect('archives:messagerie_envoyes')

    ctx = {
        **_notif_ctx(request),
        'users_disponibles': users_disponibles,
        'vue_active': 'nouveau',
        'destinataire_preselect': request.GET.get('dest'),
        'document_preselect': request.GET.get('doc'),
    }
    return render(request, 'archives/messagerie/nouveau.html', ctx)


@login_required
def messagerie_repondre(request, pk):
    """Répondre à un message existant."""
    msg_original = get_object_or_404(Message, pk=pk)
    # Seul un destinataire ou l'expéditeur peut répondre
    est_concerne = (
        msg_original.expediteur == request.user or
        MessageDestinataire.objects.filter(message=msg_original, destinataire=request.user).exists()
    )
    if not est_concerne:
        raise PermissionDenied

    if request.method == 'POST':
        corps = request.POST.get('corps', '').strip()
        if not corps:
            messages.error(request, "Le corps de la réponse est obligatoire.")
        else:
            # La réponse va à l'expéditeur du message original
            reponse = Message(
                expediteur=request.user,
                objet=f"Rép : {msg_original.objet}",
                corps=corps,
                parent=msg_original,
                document=msg_original.document,
                courrier=msg_original.courrier,
            )
            if request.FILES.get('piece_jointe'):
                reponse.piece_jointe = request.FILES['piece_jointe']
            reponse.save()
            # Destinataire = expéditeur du message original (et autres destinataires si tous)
            destinataires_reponse = {msg_original.expediteur} if msg_original.expediteur else set()
            for md in msg_original.messagedestinataire_set.exclude(destinataire=request.user):
                destinataires_reponse.add(md.destinataire)
            for dest in destinataires_reponse:
                if dest and dest != request.user:
                    MessageDestinataire.objects.get_or_create(message=reponse, destinataire=dest)
            messages.success(request, "Réponse envoyée.")
            return redirect('archives:messagerie_detail', pk=msg_original.pk)

    ctx = {
        **_notif_ctx(request),
        'msg_original': msg_original,
        'vue_active': 'detail',
    }
    return render(request, 'archives/messagerie/repondre.html', ctx)


@login_required
def messagerie_corbeille(request):
    """Messages mis en corbeille par l'utilisateur."""
    receptions = (
        MessageDestinataire.objects
        .filter(destinataire=request.user, en_corbeille=True)
        .select_related('message', 'message__expediteur')
        .order_by('-message__date_envoi')
    )
    ctx = {
        **_notif_ctx(request),
        'receptions': receptions,
        'vue_active': 'corbeille',
    }
    return render(request, 'archives/messagerie/corbeille.html', ctx)


@login_required
def messagerie_supprimer(request, pk):
    """Met un message reçu en corbeille (côté destinataire)."""
    reception = get_object_or_404(MessageDestinataire, message__pk=pk, destinataire=request.user)
    if request.method == 'POST':
        reception.en_corbeille = not reception.en_corbeille
        reception.save(update_fields=['en_corbeille'])
        if reception.en_corbeille:
            messages.info(request, "Message déplacé en corbeille.")
            return redirect('archives:messagerie_reception')
        else:
            messages.success(request, "Message restauré dans la boîte de réception.")
            return redirect('archives:messagerie_reception')
    ctx = {**_notif_ctx(request), 'reception': reception}
    return render(request, 'archives/messagerie/confirmer_suppression.html', ctx)


# ==============================================================================
# MODULE COURRIER — Secrétariat ENSMG
# Accessible : ARCHIVISTE, ADMIN + PERSONNEL (secrétariat)
# ==============================================================================

class _CourrierVide:
    """Sentinelle utilisée en mode création pour éviter les VariableDoesNotExist
    sur courrier.X quand courrier=None et que DEBUG=True répropage les exceptions
    de résolution de variables Django."""
    def __getattr__(self, name):
        return ''
    def __bool__(self):
        return False


def _peut_acceder_courriers(user):
    """Archiviste, Admin, ou Personnel (rôle secrétariat)."""
    return est_archiviste(user) or est_admin(user) or est_personnel(user)


def _peut_gerer_courriers(user):
    """Créer/modifier un courrier : Archiviste, Admin ou Personnel."""
    return _peut_acceder_courriers(user)


def _peut_gerer_bordereaux_courriers(user):
    """Bordereaux courriers : Archiviste et Admin uniquement."""
    return est_archiviste(user) or est_admin(user)


# ── Liste ──────────────────────────────────────────────────────────────────────

@login_required
def courrier_liste(request):
    """Liste de tous les courriers actifs, avec filtres."""
    if not _peut_acceder_courriers(request.user):
        raise PermissionDenied

    qs = Courrier.objects.filter(deleted_at__isnull=True).select_related('cree_par', 'en_reponse_a')

    # Filtres
    sens    = request.GET.get('sens', '')
    statut  = request.GET.get('statut', '')
    q       = request.GET.get('q', '').strip()

    if sens:
        qs = qs.filter(sens=sens)
    if statut:
        qs = qs.filter(statut=statut)
    if q:
        qs = qs.filter(
            Q(objet__icontains=q)
            | Q(expediteur__icontains=q)
            | Q(destinataire__icontains=q)
            | Q(numero_enregistrement__icontains=q)
            | Q(reference_expediteur__icontains=q)
        )

    nb_en_retard = sum(1 for c in Courrier.objects.filter(deleted_at__isnull=True) if c.est_en_retard)

    return render(request, 'archives/courriers/liste.html', {
        **_notif_ctx(request),
        'courriers':    qs.order_by('-date_enregistrement'),
        'sens_filtre':  sens,
        'statut_filtre': statut,
        'q':            q,
        'nb_en_retard': nb_en_retard,
        'STATUTS':      Courrier.Statut.choices,
        'breadcrumb':   [('Tableau de bord', 'archives:dashboard'), ('Courriers', None)],
    })


# ── Enregistrement ─────────────────────────────────────────────────────────────

@login_required
def courrier_enregistrer(request):
    """Enregistrer un nouveau courrier (arrivée ou départ)."""
    if not _peut_gerer_courriers(request.user):
        raise PermissionDenied

    import datetime
    users_actifs = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    courriers_arrivee = Courrier.objects.filter(sens='ARRIVEE', deleted_at__isnull=True).order_by('-date_courrier')
    tdgs = TableauGestion.objects.all()

    errors = {}
    data   = {}

    if request.method == 'POST':
        data = request.POST
        sens            = data.get('sens', '')
        objet           = data.get('objet', '').strip()
        expediteur      = data.get('expediteur', '').strip()
        destinataire    = data.get('destinataire', '').strip()
        service_interne = data.get('service_interne', '').strip()
        date_courrier_s = data.get('date_courrier', '')
        ref_exp         = data.get('reference_expediteur', '').strip()
        description     = data.get('description', '').strip()
        instructions    = data.get('instructions', '').strip()
        ampliation      = data.get('ampliation', '').strip()
        conf            = data.get('confidentialite', 'INTERNE')
        delai_s         = data.get('delai_reponse', '')
        en_reponse_id   = data.get('en_reponse_a', '')
        tdg_id          = data.get('tableau_gestion', '')
        mots_cles       = data.get('mots_cles', '').strip()

        # Validation minimale
        if not sens:
            errors['sens'] = 'Le sens est obligatoire.'
        if not objet:
            errors['objet'] = 'L\'objet est obligatoire.'
        if not expediteur:
            errors['expediteur'] = 'L\'expéditeur est obligatoire.'
        if not destinataire:
            errors['destinataire'] = 'Le destinataire est obligatoire.'
        if not date_courrier_s:
            errors['date_courrier'] = 'La date est obligatoire.'

        date_courrier = None
        if date_courrier_s:
            try:
                date_courrier = datetime.date.fromisoformat(date_courrier_s)
            except ValueError:
                errors['date_courrier'] = 'Format de date invalide.'

        delai = None
        if delai_s:
            try:
                delai = datetime.date.fromisoformat(delai_s)
            except ValueError:
                errors['delai_reponse'] = 'Format de date invalide.'

        if not errors:
            en_reponse = None
            if en_reponse_id:
                en_reponse = Courrier.objects.filter(pk=en_reponse_id, sens='ARRIVEE').first()

            tdg = None
            if tdg_id:
                tdg = TableauGestion.objects.filter(pk=tdg_id).first()

            courrier = Courrier(
                sens                 = sens,
                objet                = objet,
                expediteur           = expediteur,
                destinataire         = destinataire,
                service_interne      = service_interne,
                date_courrier        = date_courrier,
                reference_expediteur = ref_exp,
                description          = description,
                instructions         = instructions,
                ampliation           = ampliation,
                confidentialite      = conf,
                delai_reponse        = delai if sens == 'ARRIVEE' else None,
                en_reponse_a         = en_reponse if sens == 'DEPART' else None,
                tableau_gestion      = tdg,
                mots_cles            = mots_cles,
                statut               = 'ENREGISTRE',
                cree_par             = request.user,
            )
            # Fichier joint ?
            if 'fichier' in request.FILES:
                courrier.fichier = request.FILES['fichier']

            courrier.save()

            MouvementCourrier.objects.create(
                courrier    = courrier,
                action      = 'ENREGISTREMENT',
                utilisateur = request.user,
                commentaire = f'Enregistrement initial — {courrier.get_sens_display()}',
                adresse_ip  = request.META.get('REMOTE_ADDR'),
            )

            messages.success(request, f"Courrier {courrier.numero_enregistrement} enregistré avec succès.")
            return redirect('archives:courrier_detail', pk=courrier.pk)

    return render(request, 'archives/courriers/form.html', {
        **_notif_ctx(request),
        'mode':              'creation',
        'courrier':          _CourrierVide(),
        'errors':            errors,
        'data':              data,
        'courriers_arrivee': courriers_arrivee,
        'tdgs':              tdgs,
        'CONFIDENTIALITES':  Courrier.Confidentialite.choices,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Nouveau courrier', None)],
    })


# ── Détail ─────────────────────────────────────────────────────────────────────

@login_required
def courrier_detail(request, pk):
    """Affiche le détail complet d'un courrier avec son journal d'audit."""
    courrier = get_object_or_404(Courrier, pk=pk, deleted_at__isnull=True)
    if not _peut_acceder_courriers(request.user):
        raise PermissionDenied

    journal   = courrier.mouvements.select_related('utilisateur').order_by('date_action')
    reponses  = courrier.reponses.filter(deleted_at__isnull=True) if courrier.sens == 'ARRIVEE' else []

    MouvementCourrier.objects.create(
        courrier    = courrier,
        action      = 'CONSULTATION',
        utilisateur = request.user,
        commentaire = 'Consultation de la fiche courrier.',
        adresse_ip  = request.META.get('REMOTE_ADDR'),
    )

    return render(request, 'archives/courriers/detail.html', {
        **_notif_ctx(request),
        'courrier':  courrier,
        'journal':   journal,
        'reponses':  reponses,
        'peut_modifier': _peut_gerer_courriers(request.user),
        'peut_archiver': _peut_gerer_bordereaux_courriers(request.user),
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       (courrier.numero_enregistrement, None)],
    })


# ── Modification ────────────────────────────────────────────────────────────────

@login_required
def courrier_modifier(request, pk):
    """Modifier les métadonnées d'un courrier existant."""
    courrier = get_object_or_404(Courrier, pk=pk, deleted_at__isnull=True)
    if not _peut_gerer_courriers(request.user):
        raise PermissionDenied
    if courrier.statut in ('VERSE', 'ELIMINE'):
        messages.error(request, "Ce courrier est clôturé et ne peut plus être modifié.")
        return redirect('archives:courrier_detail', pk=pk)

    import datetime
    courriers_arrivee = Courrier.objects.filter(
        sens='ARRIVEE', deleted_at__isnull=True
    ).exclude(pk=pk)
    tdgs = TableauGestion.objects.all()
    errors = {}

    if request.method == 'POST':
        data = request.POST
        objet           = data.get('objet', '').strip()
        expediteur      = data.get('expediteur', '').strip()
        destinataire    = data.get('destinataire', '').strip()
        service_interne = data.get('service_interne', '').strip()
        date_courrier_s = data.get('date_courrier', '')
        ref_exp         = data.get('reference_expediteur', '').strip()
        description     = data.get('description', '').strip()
        instructions    = data.get('instructions', '').strip()
        ampliation      = data.get('ampliation', '').strip()
        conf            = data.get('confidentialite', courrier.confidentialite)
        delai_s         = data.get('delai_reponse', '')
        en_reponse_id   = data.get('en_reponse_a', '')
        tdg_id          = data.get('tableau_gestion', '')
        mots_cles       = data.get('mots_cles', '').strip()
        accuse          = data.get('accuse_reception') == 'on'

        if not objet:
            errors['objet'] = 'L\'objet est obligatoire.'
        if not date_courrier_s:
            errors['date_courrier'] = 'La date est obligatoire.'

        date_courrier = courrier.date_courrier
        if date_courrier_s:
            try:
                date_courrier = datetime.date.fromisoformat(date_courrier_s)
            except ValueError:
                errors['date_courrier'] = 'Format de date invalide.'

        delai = None
        if delai_s:
            try:
                delai = datetime.date.fromisoformat(delai_s)
            except ValueError:
                errors['delai_reponse'] = 'Format de date invalide.'

        if not errors:
            avant = {
                'objet': courrier.objet,
                'expediteur': courrier.expediteur,
                'statut': courrier.statut,
            }
            courrier.objet                = objet
            courrier.expediteur           = expediteur
            courrier.destinataire         = destinataire
            courrier.service_interne      = service_interne
            courrier.date_courrier        = date_courrier
            courrier.reference_expediteur = ref_exp
            courrier.description          = description
            courrier.instructions         = instructions
            courrier.ampliation           = ampliation
            courrier.confidentialite      = conf
            courrier.mots_cles            = mots_cles
            courrier.accuse_reception     = accuse
            if courrier.sens == 'ARRIVEE':
                courrier.delai_reponse = delai
            if courrier.sens == 'DEPART' and en_reponse_id:
                courrier.en_reponse_a = Courrier.objects.filter(pk=en_reponse_id, sens='ARRIVEE').first()
            if tdg_id:
                courrier.tableau_gestion = TableauGestion.objects.filter(pk=tdg_id).first()
            if 'fichier' in request.FILES:
                courrier.fichier = request.FILES['fichier']
                courrier.empreinte_sha256 = ''  # Force recalcul dans save()

            courrier.save()
            MouvementCourrier.objects.create(
                courrier    = courrier,
                action      = 'MODIFICATION',
                utilisateur = request.user,
                commentaire = 'Mise à jour des métadonnées du courrier.',
                details     = {'avant': avant, 'apres': {'objet': courrier.objet}},
                adresse_ip  = request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, "Courrier mis à jour.")
            return redirect('archives:courrier_detail', pk=pk)

    return render(request, 'archives/courriers/form.html', {
        **_notif_ctx(request),
        'mode':              'edition',
        'courrier':          courrier,
        'errors':            errors,
        'data':              request.POST if errors else {},
        'courriers_arrivee': courriers_arrivee,
        'tdgs':              tdgs,
        'CONFIDENTIALITES':  Courrier.Confidentialite.choices,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       (courrier.numero_enregistrement, 'archives:courrier_detail', pk),
                       ('Modifier', None)],
    })


# ── Actions de workflow ────────────────────────────────────────────────────────

@login_required
def courrier_action(request, pk):
    """
    Actions de workflow via POST :
      action=traiter      ENREGISTRE / EN_TRAITEMENT → TRAITE
      action=archiver     TRAITE → ARCHIVE
      action=en_traitement  ENREGISTRE → EN_TRAITEMENT
    """
    courrier = get_object_or_404(Courrier, pk=pk, deleted_at__isnull=True)
    if not _peut_gerer_courriers(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('archives:courrier_detail', pk=pk)

    action = request.POST.get('action', '')

    if action == 'en_traitement' and courrier.statut == 'ENREGISTRE':
        courrier.statut = 'EN_TRAITEMENT'
        courrier.traite_par = request.user
        courrier.date_traitement = timezone.now()
        courrier.save(update_fields=['statut', 'traite_par', 'date_traitement'])
        MouvementCourrier.objects.create(
            courrier=courrier, action='TRAITEMENT', utilisateur=request.user,
            commentaire='Prise en charge du courrier — passage en traitement.',
            adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.info(request, "Courrier pris en charge.")

    elif action == 'traiter' and courrier.statut in ('ENREGISTRE', 'EN_TRAITEMENT'):
        courrier.statut = 'TRAITE'
        courrier.traite_par = request.user
        courrier.date_traitement = timezone.now()
        courrier.save(update_fields=['statut', 'traite_par', 'date_traitement'])
        MouvementCourrier.objects.create(
            courrier=courrier, action='TRAITEMENT', utilisateur=request.user,
            commentaire=request.POST.get('commentaire', 'Traitement clôturé.'),
            adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, "Courrier marqué comme traité.")

    elif action == 'archiver' and courrier.statut == 'TRAITE' and _peut_gerer_bordereaux_courriers(request.user):
        courrier.statut = 'ARCHIVE'
        courrier.date_archivage = timezone.now()
        courrier.save(update_fields=['statut', 'date_archivage'])
        MouvementCourrier.objects.create(
            courrier=courrier, action='ARCHIVAGE', utilisateur=request.user,
            commentaire='Classement définitif dans le registre des courriers.',
            adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, "Courrier archivé.")

    else:
        messages.error(request, "Action non autorisée pour ce courrier dans son état actuel.")

    return redirect('archives:courrier_detail', pk=pk)


# ── Corbeille courrier ─────────────────────────────────────────────────────────

@login_required
def courrier_supprimer(request, pk):
    """Soft delete d'un courrier (mise en corbeille)."""
    courrier = get_object_or_404(Courrier, pk=pk, deleted_at__isnull=True)
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        courrier.deleted_at = timezone.now()
        courrier.save(update_fields=['deleted_at'])
        MouvementCourrier.objects.create(
            courrier=courrier, action='MODIFICATION', utilisateur=request.user,
            commentaire='Mis en corbeille.', adresse_ip=request.META.get('REMOTE_ADDR'),
        )
        messages.warning(request, f"Courrier {courrier.numero_enregistrement} mis en corbeille.")
        return redirect('archives:courrier_liste')
    return render(request, 'archives/courriers/confirmer_suppression.html', {
        **_notif_ctx(request), 'courrier': courrier,
    })


# ── Bordereaux de versement courriers ─────────────────────────────────────────

@login_required
def courrier_bv_liste(request):
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    qs = BordereauVersementCourrier.objects.select_related('cree_par', 'valide_par').order_by('-date_creation')
    return render(request, 'archives/courriers/bv_liste.html', {
        **_notif_ctx(request),
        'bordereaux': qs,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Versements', None)],
    })


@login_required
def courrier_bv_creer(request):
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    import datetime
    courriers_eligibles = Courrier.objects.filter(
        statut='ARCHIVE',
        sort_final='CONSERVATION',
        deleted_at__isnull=True,
    ).exclude(bordereaux_versement__isnull=False)

    if request.method == 'POST':
        ids = request.POST.getlist('courriers')
        obs = request.POST.get('observations', '')
        service = request.POST.get('service_versant', 'Secrétariat ENSMG')
        if not ids:
            messages.error(request, "Sélectionnez au moins un courrier.")
        else:
            num = f"BVC-{datetime.date.today().strftime('%Y%m%d')}-{BordereauVersementCourrier.objects.count() + 1:04d}"
            bv = BordereauVersementCourrier.objects.create(
                numero=num, service_versant=service, observations=obs, cree_par=request.user,
            )
            bv.courriers.set(Courrier.objects.filter(pk__in=ids, deleted_at__isnull=True))
            messages.success(request, f"Bordereau {num} créé.")
            return redirect('archives:courrier_bv_detail', pk=bv.pk)

    return render(request, 'archives/courriers/bv_form.html', {
        **_notif_ctx(request),
        'courriers_eligibles': courriers_eligibles,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Versements', 'archives:courrier_bv_liste'),
                       ('Nouveau', None)],
    })


@login_required
def courrier_bv_detail(request, pk):
    bv = get_object_or_404(BordereauVersementCourrier, pk=pk)
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    import datetime
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'soumettre' and bv.statut == 'BROUILLON':
            bv.statut = 'EN_VALIDATION'; bv.save()
            messages.info(request, "Bordereau soumis pour validation.")
        elif action == 'valider' and bv.statut == 'EN_VALIDATION' and est_admin(request.user):
            bv.statut = 'VALIDE'; bv.valide_par = request.user
            bv.date_validation = datetime.date.today(); bv.save()
            messages.success(request, "Bordereau validé ✓")
        elif action == 'executer' and bv.statut == 'VALIDE':
            bv.statut = 'EXECUTE'; bv.save()
            bv.courriers.all().update(statut='VERSE')
            messages.success(request, "Versement exécuté — courriers marqués VERSÉ.")
        elif action == 'rejeter' and est_admin(request.user):
            bv.statut = 'REJETE'; bv.save()
            messages.warning(request, "Bordereau rejeté.")
        return redirect('archives:courrier_bv_detail', pk=pk)
    return render(request, 'archives/courriers/bv_detail.html', {
        **_notif_ctx(request),
        'bv': bv,
        'courriers': bv.courriers.select_related('cree_par'),
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Versements', 'archives:courrier_bv_liste'),
                       (bv.numero, None)],
    })


# ── Bordereaux d'élimination courriers ────────────────────────────────────────

@login_required
def courrier_be_liste(request):
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    qs = BordereauEliminationCourrier.objects.select_related('cree_par').order_by('-date_creation')
    return render(request, 'archives/courriers/be_liste.html', {
        **_notif_ctx(request),
        'bordereaux': qs,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ("Éliminations", None)],
    })


@login_required
def courrier_be_creer(request):
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    import datetime
    courriers_eligibles = Courrier.objects.filter(
        statut='ARCHIVE',
        sort_final='ELIMINATION',
        deleted_at__isnull=True,
    ).exclude(bordereaux_elimination__isnull=False)

    if request.method == 'POST':
        ids   = request.POST.getlist('courriers')
        motif = request.POST.get('motif', '').strip()
        obs   = request.POST.get('observations', '')
        service = request.POST.get('service_producteur', 'Secrétariat ENSMG')
        if not ids:
            messages.error(request, "Sélectionnez au moins un courrier.")
        elif not motif:
            messages.error(request, "Le motif d'élimination est obligatoire.")
        else:
            num = f"BEC-{datetime.date.today().strftime('%Y%m%d')}-{BordereauEliminationCourrier.objects.count() + 1:04d}"
            be = BordereauEliminationCourrier.objects.create(
                numero=num, service_producteur=service, motif=motif, observations=obs, cree_par=request.user,
            )
            be.courriers.set(Courrier.objects.filter(pk__in=ids, deleted_at__isnull=True))
            messages.success(request, f"Bordereau {num} créé.")
            return redirect('archives:courrier_be_detail', pk=be.pk)

    return render(request, 'archives/courriers/be_form.html', {
        **_notif_ctx(request),
        'courriers_eligibles': courriers_eligibles,
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Éliminations', 'archives:courrier_be_liste'),
                       ('Nouveau', None)],
    })


@login_required
def courrier_be_detail(request, pk):
    be = get_object_or_404(BordereauEliminationCourrier, pk=pk)
    if not _peut_gerer_bordereaux_courriers(request.user):
        raise PermissionDenied
    import datetime
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'soumettre' and be.statut == 'BROUILLON':
            be.statut = 'EN_VALIDATION'; be.save()
            messages.info(request, "Bordereau soumis pour visa DAS.")
        elif action == 'visa' and be.statut == 'EN_VALIDATION' and est_admin(request.user):
            ref = request.POST.get('reference_visa', '').strip()
            be.statut = 'VISA_OBTENU'; be.visa_das = True
            be.date_visa = datetime.date.today(); be.reference_visa = ref; be.save()
            messages.success(request, "Visa DAS enregistré ✓")
        elif action == 'executer' and be.statut == 'VISA_OBTENU':
            be.statut = 'EXECUTE'; be.date_elimination = datetime.date.today(); be.save()
            be.courriers.all().update(statut='ELIMINE')
            messages.success(request, "Élimination exécutée — courriers marqués ÉLIMINÉ.")
        elif action == 'rejeter' and est_admin(request.user):
            be.statut = 'REJETE'; be.save()
            messages.warning(request, "Bordereau rejeté par la DAS.")
        return redirect('archives:courrier_be_detail', pk=pk)
    return render(request, 'archives/courriers/be_detail.html', {
        **_notif_ctx(request),
        'be': be,
        'courriers': be.courriers.select_related('cree_par'),
        'breadcrumb': [('Tableau de bord', 'archives:dashboard'),
                       ('Courriers', 'archives:courrier_liste'),
                       ('Éliminations', 'archives:courrier_be_liste'),
                       (be.numero, None)],
    })
