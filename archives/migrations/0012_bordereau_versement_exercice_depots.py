"""
Migration 0012 — Bordereau de versement : ajout exercice + M2M depots
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0011_alter_courrier_en_reponse_a_and_more'),
    ]

    operations = [
        # Exercice budgétaire (année) auto-détecté depuis les dépôts
        migrations.AddField(
            model_name='bordereauversement',
            name='exercice',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Exercice (année)',
                db_index=True,
                help_text='Année budgétaire du bordereau — auto-détecté depuis les dates de dépôts.',
            ),
        ),
        # Lien direct vers les DepotDocument inclus dans ce bordereau
        migrations.AddField(
            model_name='bordereauversement',
            name='depots',
            field=models.ManyToManyField(
                to='archives.depotdocument',
                related_name='bordereaux_versement',
                verbose_name='Dépôts inclus',
                blank=True,
            ),
        ),
        # Service destinataire par défaut : Archives ENSMG (interne) plutôt qu'ANS
        migrations.AlterField(
            model_name='bordereauversement',
            name='service_destinataire',
            field=models.CharField(
                max_length=200,
                default='Service des Archives — ENSMG',
                verbose_name='Service destinataire',
            ),
        ),
        # documents M2M — ajout de blank=True (validation formulaire uniquement)
        migrations.AlterField(
            model_name='bordereauversement',
            name='documents',
            field=models.ManyToManyField(
                blank=True,
                related_name='bordereaux_versement',
                to='archives.document',
                verbose_name='Documents versés',
            ),
        ),
    ]
