"""
Migration 0006 — Ajout du modèle ProvenanceExterne et des champs provenance sur DepotDocument.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0005_demande_recherche_service_fk'),
    ]

    operations = [
        # ── 1. Créer le modèle ProvenanceExterne ─────────────────────────────
        migrations.CreateModel(
            name='ProvenanceExterne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30, unique=True, verbose_name='Code')),
                ('nom', models.CharField(max_length=200, verbose_name="Nom de l'organisme")),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('cree_le', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
            ],
            options={
                'verbose_name': 'Provenance externe',
                'verbose_name_plural': 'Provenances externes',
                'ordering': ['nom'],
            },
        ),

        # ── 2. Données initiales (provenances connues) ───────────────────────
        # (injectées via une migration de données séparée si besoin)

        # ── 3. Ajouter provenance_interne sur DepotDocument ──────────────────
        migrations.AddField(
            model_name='depotdocument',
            name='provenance_interne',
            field=models.BooleanField(
                default=True,
                verbose_name='Provenance ENSMG (interne)',
                help_text="Décochez si le document provient d'un organisme externe (Rectorat, BU, ESP…)",
            ),
        ),

        # ── 4. Ajouter provenance_externe sur DepotDocument ──────────────────
        migrations.AddField(
            model_name='depotdocument',
            name='provenance_externe',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='archives.provenanceexterne',
                verbose_name='Organisme externe',
                help_text="Sélectionnez l'organisme d'origine du document",
            ),
        ),

        # ── 5. Retirer choices= du champ code de CategorieDocument ──────────
        # (le champ devient un CharField libre pour permettre la création admin)
        migrations.AlterField(
            model_name='categoriedocument',
            name='code',
            field=models.CharField(max_length=10, unique=True, verbose_name='Code'),
        ),
    ]
