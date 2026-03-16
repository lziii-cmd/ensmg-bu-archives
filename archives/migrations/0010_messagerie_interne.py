"""
Migration 0010 — Messagerie interne
Ajoute les 2 modèles du système de messagerie inter-agents :
  - Message      (message avec objet, corps, pièce jointe, fil de réponses)
  - MessageDestinataire  (statut lu/non-lu et corbeille par destinataire)
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0009_module_courrier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. Message ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('objet', models.CharField(max_length=300, verbose_name='Objet')),
                ('corps', models.TextField(verbose_name='Corps du message')),
                ('date_envoi', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Date d'envoi")),
                ('piece_jointe', models.FileField(blank=True, null=True, upload_to='messagerie/%Y/%m/', verbose_name='Pièce jointe')),
                ('nom_piece_jointe', models.CharField(blank=True, max_length=255, verbose_name='Nom du fichier joint')),
                ('expediteur', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='messages_envoyes',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Expéditeur',
                )),
                ('parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reponses',
                    to='archives.message',
                    verbose_name='En réponse à',
                )),
                ('document', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='messages_lies',
                    to='archives.document',
                    verbose_name='Document lié',
                )),
                ('courrier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='messages_lies',
                    to='archives.courrier',
                    verbose_name='Courrier lié',
                )),
            ],
            options={
                'verbose_name': 'Message interne',
                'verbose_name_plural': 'Messages internes',
                'ordering': ['-date_envoi'],
                'default_permissions': ('add', 'view'),
            },
        ),

        # ── 2. MessageDestinataire ─────────────────────────────────────────────
        migrations.CreateModel(
            name='MessageDestinataire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lu', models.BooleanField(db_index=True, default=False, verbose_name='Lu')),
                ('date_lecture', models.DateTimeField(blank=True, null=True, verbose_name='Date de lecture')),
                ('en_corbeille', models.BooleanField(db_index=True, default=False, verbose_name='En corbeille')),
                ('message', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='archives.message',
                    verbose_name='Message',
                )),
                ('destinataire', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Destinataire',
                )),
            ],
            options={
                'verbose_name': 'Destinataire du message',
                'verbose_name_plural': 'Destinataires des messages',
                'ordering': ['-message__date_envoi'],
                'unique_together': {('message', 'destinataire')},
            },
        ),

        # ── 3. ManyToMany via through ──────────────────────────────────────────
        migrations.AddField(
            model_name='message',
            name='destinataires',
            field=models.ManyToManyField(
                through='archives.MessageDestinataire',
                related_name='messages_recus',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Destinataires',
            ),
        ),
    ]
