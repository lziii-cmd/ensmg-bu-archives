"""
Migration 0007 — Données initiales pour ProvenanceExterne.
Les provenances les plus communes citées dans le cahier des charges ENSMG.
"""
from django.db import migrations


def creer_provenances(apps, schema_editor):
    ProvenanceExterne = apps.get_model('archives', 'ProvenanceExterne')
    provenances = [
        ('RECTO',  "Rectorat de l'UCAD",                          "Rectorat de l'Université Cheikh Anta Diop de Dakar"),
        ('BU',     "Bibliothèque Universitaire (UCAD)",            "Bibliothèque Universitaire centrale de l'UCAD"),
        ('ESP',    "École Supérieure Polytechnique (ESP)",         "ESP — Université Cheikh Anta Diop"),
        ('FASEG',  "FASEG — Université Cheikh Anta Diop",          "Faculté des Sciences Économiques et de Gestion"),
        ('FSJP',   "FSJP — Université Cheikh Anta Diop",          "Faculté des Sciences Juridiques et Politiques"),
        ('ANS',    "Archives Nationales du Sénégal",               "Direction des Archives Nationales du Sénégal (DAS)"),
        ('MESRI',  "Ministère de l'Enseignement Supérieur (MESRI)","Ministère en charge de l'enseignement supérieur"),
        ('CRSS',   "CRSS — Centre de Recherches Scientifiques",    "Centre de Recherches Scientifiques et Technologiques du Sénégal"),
        ('AUTRE',  "Autre organisme externe",                      "Organisme externe non listé — préciser dans la description"),
    ]
    for code, nom, description in provenances:
        ProvenanceExterne.objects.get_or_create(
            code=code,
            defaults={'nom': nom, 'description': description, 'actif': True}
        )


def supprimer_provenances(apps, schema_editor):
    ProvenanceExterne = apps.get_model('archives', 'ProvenanceExterne')
    codes = ['RECTO', 'BU', 'ESP', 'FASEG', 'FSJP', 'ANS', 'MESRI', 'CRSS', 'AUTRE']
    ProvenanceExterne.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0006_provenanceexterne_depotdocument_provenance'),
    ]

    operations = [
        migrations.RunPython(creer_provenances, supprimer_provenances),
    ]
