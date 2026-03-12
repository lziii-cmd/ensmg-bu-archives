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
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from archives.forms import (
    DepotAgentForm, TraiterDepotForm,
    DemandePretForm, TraiterDemandePretForm,
    RetourPretForm, AccesDocumentForm, RechercheDocumentForm,
    DemandeRechercheForm, TraiterRechercheForm,
)
from archives.models import (
    Document, DepotDocument, DemandePret, PretDocument,
    AccesDocument, Notification, MouvementDocument,
    RetentionJuridique, PlanClassement, CategorieDocument, DemandeRecherche,
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
        ctx['nb_notifications'] = notifs_non_lues.count()
        ctx['notifs_recentes']  = notifs_non_lues.select_related(
            'depot', 'document'
        ).order_by('-date_creation')[:6]
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
            ctx['nb_documents']         = Document.objects.exclude(statut='ELIMINE').count()
            ctx['derniers_depots']      = DepotDocument.objects.select_related('agent', 'categorie').order_by('-date_depot')[:10]
            ctx['prets_en_cours']       = PretDocument.objects.select_related(
                'emprunteur', 'document'
            ).filter(statut='EN_COURS').order_by('date_retour_prevue')[:10]
        else:
            # Dashboard agent : documents publics + ses dépôts/prêts
            ctx['docs_publics'] = Document.objects.filter(
                confidentialite='PUBLIC'
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
            confidentialite__in=niveaux
        ).exclude(statut='ELIMINE').select_related('categorie', 'plan_classement')

        # Accès ABAC individuels
        acces_ids = AccesDocument.objects.filter(
            utilisateur=user, actif=True
        ).filter(
            Q(date_fin__isnull=True) | Q(date_fin__gt=timezone.now())
        ).values_list('document_id', flat=True)
        qs = (qs | Document.objects.filter(pk__in=acces_ids)).distinct()

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
        'document': doc, 'fichier_url': doc.fichier.url,
        **_notif_ctx(request),
    })


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

        depot = DepotDocument.objects.create(
            agent=request.user,
            titre=form.cleaned_data['titre'],
            fichier=request.FILES['fichier'],
            date_reception=form.cleaned_data['date_reception'],
            categorie=categorie,
            description=form.cleaned_data.get('description', ''),
            mots_cles=form.cleaned_data.get('mots_cles', ''),
            statut='EN_ATTENTE',
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
