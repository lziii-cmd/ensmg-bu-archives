# Migration manuelle — 2026-03-12
# Remplace DemandeRecherche.service_producteur (CharField) par FK vers Departement

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0004_add_mots_cles_depot_demande_recherche'),
        ('users', '0002_departement_remove_customuser_service_and_more'),
    ]

    operations = [
        # Supprimer l'ancien champ texte libre
        migrations.RemoveField(
            model_name='demanderecherche',
            name='service_producteur',
        ),
        # Ajouter la FK vers Departement
        migrations.AddField(
            model_name='demanderecherche',
            name='service_producteur',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='recherches_documentaires',
                to='users.departement',
                verbose_name='Service producteur / déposant',
                help_text='Service ou département qui a produit ou déposé le document',
            ),
        ),
    ]
