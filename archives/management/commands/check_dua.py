"""
archives/management/commands/check_dua.py
Commande de gestion Django pour surveiller les DUA et la corbeille.

Usage :
    python manage.py check_dua              # Alertes DUA + purge corbeille
    python manage.py check_dua --dry-run    # Simulation sans écriture

Planification recommandée (crontab Windows Task Scheduler, chaque matin à 7h) :
    python manage.py check_dua
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from archives.models import Document, AuditToken, Notification


class Command(BaseCommand):
    help = "Vérifie les DUA arrivant à échéance, expire les tokens d'audit et purge la corbeille."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simule les actions sans rien modifier en base.',
        )
        parser.add_argument(
            '--corbeille-jours',
            type=int,
            default=30,
            help='Nombre de jours avant purge définitive de la corbeille (défaut : 30).',
        )
        parser.add_argument(
            '--alerte-jours',
            type=int,
            default=30,
            help='Nombre de jours avant échéance pour déclencher une alerte DUA (défaut : 30).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        corbeille_jours = options['corbeille_jours']
        alerte_jours = options['alerte_jours']

        now = timezone.now()
        aujourd_hui = now.date()

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'[DRY-RUN] ' if dry_run else ''}Démarrage check_dua — {now.strftime('%d/%m/%Y %H:%M')}"
        ))
        self.stdout.write("─" * 60)

        # ─────────────────────────────────────────────────────────────
        # 1. Documents dont la DUA est échue (sans alerte existante)
        # ─────────────────────────────────────────────────────────────
        docs_dua_echue = Document.objects.filter(
            date_fin_dua__lte=aujourd_hui,
            deleted_at__isnull=True,
        ).exclude(statut__in=['ELIMINE', 'VERSE'])

        self.stdout.write(f"\n[DUA ÉCHUES] {docs_dua_echue.count()} document(s) trouvé(s)")

        from django.contrib.auth import get_user_model
        User = get_user_model()
        archivistes = User.objects.filter(role__in=['ADMIN', 'ARCHIVISTE'])

        for doc in docs_dua_echue:
            msg = (
                f"Le document « {doc.titre[:60]} » (réf. {doc.identifiant}) "
                f"a atteint sa durée d'utilité administrative. "
                f"Sort final prévu : {doc.get_sort_final_display()}. "
                f"Action requise par l'archiviste."
            )
            self.stdout.write(f"  → {doc.identifiant} — DUA échue le {doc.date_fin_dua}")
            if not dry_run:
                for arch in archivistes:
                    # Éviter les doublons : une alerte par document par mois
                    dejà_alerté = Notification.objects.filter(
                        document=doc,
                        type='DUA_ECHUE',
                        date_creation__date__gte=aujourd_hui.replace(day=1),
                    ).exists()
                    if not dejà_alerté:
                        Notification.envoyer(
                            destinataire=arch,
                            type_='DUA_ECHUE',
                            titre=f"DUA échue — {doc.identifiant}",
                            message=msg,
                            document=doc,
                        )

        # ─────────────────────────────────────────────────────────────
        # 2. Documents dont la DUA arrive dans N jours
        # ─────────────────────────────────────────────────────────────
        seuil = aujourd_hui + timedelta(days=alerte_jours)
        docs_alerte = Document.objects.filter(
            date_fin_dua__gt=aujourd_hui,
            date_fin_dua__lte=seuil,
            deleted_at__isnull=True,
        ).exclude(statut__in=['ELIMINE', 'VERSE'])

        self.stdout.write(f"\n[DUA PROCHAINES] {docs_alerte.count()} document(s) dans les {alerte_jours} prochains jours")

        for doc in docs_alerte:
            jours = (doc.date_fin_dua - aujourd_hui).days
            self.stdout.write(f"  → {doc.identifiant} — DUA dans {jours} jours ({doc.date_fin_dua})")
            if not dry_run:
                for arch in archivistes:
                    dejà_alerté = Notification.objects.filter(
                        document=doc,
                        type='ALERTE_DUA',
                        date_creation__date__gte=aujourd_hui.replace(day=1),
                    ).exists()
                    if not dejà_alerté:
                        Notification.envoyer(
                            destinataire=arch,
                            type_='ALERTE_DUA',
                            titre=f"DUA dans {jours} j — {doc.identifiant}",
                            message=(
                                f"La DUA du document « {doc.titre[:60]} » "
                                f"(réf. {doc.identifiant}) arrive à échéance le {doc.date_fin_dua}. "
                                f"Sort final prévu : {doc.get_sort_final_display()}."
                            ),
                            document=doc,
                        )

        # ─────────────────────────────────────────────────────────────
        # 3. Purge automatique de la corbeille (> 30 jours)
        # ─────────────────────────────────────────────────────────────
        seuil_purge = now - timedelta(days=corbeille_jours)
        docs_a_purger = Document.objects.filter(
            deleted_at__lte=seuil_purge,
        )
        nb_purges = docs_a_purger.count()
        self.stdout.write(f"\n[CORBEILLE] {nb_purges} document(s) à purger (plus de {corbeille_jours} jours)")

        if not dry_run and nb_purges > 0:
            for doc in docs_a_purger:
                self.stdout.write(f"  ✗ Suppression définitive : {doc.identifiant}")
                # Suppression physique du fichier si présent
                if doc.fichier:
                    try:
                        doc.fichier.delete(save=False)
                    except Exception:
                        pass
                doc.delete()

        # ─────────────────────────────────────────────────────────────
        # 4. Expiration des tokens d'audit
        # ─────────────────────────────────────────────────────────────
        tokens_expires = AuditToken.objects.filter(
            actif=True,
            date_expiration__lt=now,
        )
        nb_tokens = tokens_expires.count()
        self.stdout.write(f"\n[AUDIT TOKENS] {nb_tokens} token(s) à expirer")
        if not dry_run and nb_tokens > 0:
            tokens_expires.update(actif=False)

        # ─────────────────────────────────────────────────────────────
        # Résumé
        # ─────────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"check_dua terminé {'(DRY-RUN)' if dry_run else '✓'}\n"
            f"  DUA échues      : {docs_dua_echue.count()}\n"
            f"  DUA prochaines  : {docs_alerte.count()}\n"
            f"  Corbeille purgée: {nb_purges}\n"
            f"  Tokens expirés  : {nb_tokens}\n"
        ))
