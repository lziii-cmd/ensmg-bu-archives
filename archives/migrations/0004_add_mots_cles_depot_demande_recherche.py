# Generated manually — 2026-03-12
# Adds: DepotDocument.mots_cles + DemandeRecherche model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0003_phase5_workflow_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Ajouter mots_cles à DepotDocument
        migrations.AddField(
            model_name='depotdocument',
            name='mots_cles',
            field=models.TextField(
                blank=True,
                help_text="Séparés par des virgules — optionnel, peut être renseigné par l'archiviste",
                verbose_name='Mots-clés',
            ),
        ),

        # 2. Créer DemandeRecherche
        migrations.CreateModel(
            name='DemandeRecherche',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_producteur', models.CharField(
                    blank=True, max_length=200,
                    help_text='Service ou département qui a produit ou déposé le document',
                    verbose_name='Service producteur / déposant',
                )),
                ('motif', models.TextField(verbose_name='Motif de la demande')),
                ('description', models.TextField(
                    help_text='Titre approximatif, période, contenu, contexte…',
                    verbose_name='Description du document recherché',
                )),
                ('statut', models.CharField(
                    choices=[
                        ('EN_ATTENTE', 'En attente de traitement'),
                        ('ACCORDEE',   'Document trouvé — prêt accordé'),
                        ('REFUSEE',    'Document non trouvé / refusée'),
                    ],
                    db_index=True, default='EN_ATTENTE', max_length=20,
                    verbose_name='Statut',
                )),
                ('date_demande', models.DateTimeField(auto_now_add=True, verbose_name='Date de la demande')),
                ('date_traitement', models.DateTimeField(blank=True, null=True, verbose_name='Date de traitement')),
                ('motif_refus', models.TextField(blank=True, verbose_name='Motif du refus / document non trouvé')),
                # FKs
                ('agent', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='demandes_recherche',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Agent demandeur',
                )),
                ('categorie', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='archives.categoriedocument',
                    verbose_name='Catégorie documentaire',
                )),
                ('traite_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recherches_traitees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Traitée par',
                )),
                ('document_fourni', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recherches',
                    to='archives.document',
                    verbose_name='Document trouvé',
                )),
                ('pret_cree', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recherche_source',
                    to='archives.demandepret',
                    verbose_name='Demande de prêt créée',
                )),
            ],
            options={
                'verbose_name': 'Demande de recherche documentaire',
                'verbose_name_plural': 'Demandes de recherche documentaire',
                'ordering': ['-date_demande'],
            },
        ),
    ]
