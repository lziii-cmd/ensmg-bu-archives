"""
Migration 0008 — Trois nouvelles fonctionnalités :

1. Document.deleted_at   → Corbeille (soft delete)
2. Document.texte_extrait → Indexation plein texte / OCR
3. AuditToken            → Accès temporaire sécurisé pour auditeurs externes

Conformité : ISO 15489 (traçabilité), Loi 2006-19 (cycle de vie),
             CDC ENSMG § 5.8 (audit externe), § 5.10 (OCR).
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0007_provenance_initiale'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ────────────────────────────────────────────────
        # 1. Corbeille — soft delete sur Document
        # ────────────────────────────────────────────────
        migrations.AddField(
            model_name='document',
            name='deleted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Mis en corbeille le',
                help_text='NULL = document actif. Non-NULL = document en corbeille (soft delete).',
            ),
        ),

        # ────────────────────────────────────────────────
        # 2. Texte extrait pour l'indexation / OCR futur
        # ────────────────────────────────────────────────
        migrations.AddField(
            model_name='document',
            name='texte_extrait',
            field=models.TextField(
                blank=True,
                verbose_name='Texte extrait (OCR / indexation plein texte)',
                help_text='Alimenté par Tesseract / PaddleOCR. Utilisé pour la recherche plein texte.',
            ),
        ),

        # ────────────────────────────────────────────────
        # 3. Modèle AuditToken
        # ────────────────────────────────────────────────
        migrations.CreateModel(
            name='AuditToken',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('token', models.CharField(
                    editable=False, max_length=64, unique=True,
                    verbose_name="Token d'accès",
                )),
                ('description', models.CharField(
                    max_length=300,
                    verbose_name="Objet / Mission d'audit",
                )),
                ('auditeur_nom', models.CharField(
                    max_length=200,
                    verbose_name="Nom de l'auditeur / organisme",
                )),
                ('auditeur_email', models.EmailField(
                    blank=True,
                    verbose_name="Email de l'auditeur",
                )),
                # Périmètre d'accès
                ('perimetre', models.CharField(
                    choices=[
                        ('TOUS',      'Tous les documents autorisés'),
                        ('CATEGORIE', 'Par catégorie documentaire'),
                        ('PLAN',      'Par plan de classement'),
                        ('SELECTION', 'Sélection manuelle'),
                    ],
                    default='TOUS',
                    max_length=20,
                    verbose_name="Périmètre d'accès",
                )),
                # Confidentialité maximale accessible
                ('confidentialite_max', models.CharField(
                    choices=[
                        ('INTERNE',      'Interne'),
                        ('CONFIDENTIEL', 'Confidentiel'),
                        ('SECRET',       'Secret'),
                    ],
                    default='INTERNE',
                    max_length=20,
                    verbose_name='Confidentialité maximale accessible',
                )),
                # Durée de validité
                ('date_creation', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Créé le',
                )),
                ('date_debut', models.DateTimeField(
                    verbose_name='Valide à partir du',
                )),
                ('date_expiration', models.DateTimeField(
                    verbose_name='Expire le',
                )),
                ('actif', models.BooleanField(
                    default=True,
                    verbose_name='Actif',
                )),
                # Traçabilité
                ('nb_consultations', models.PositiveIntegerField(
                    default=0,
                    verbose_name='Nombre de consultations',
                )),
                ('derniere_consultation', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Dernière consultation',
                )),
                # FK
                ('cree_par', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_tokens_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
                # M2M
                ('categories', models.ManyToManyField(
                    blank=True,
                    to='archives.categoriedocument',
                    verbose_name='Catégories autorisées',
                )),
                ('plans', models.ManyToManyField(
                    blank=True,
                    to='archives.planclassement',
                    verbose_name='Plans de classement autorisés',
                )),
                ('documents', models.ManyToManyField(
                    blank=True,
                    related_name='audit_tokens',
                    to='archives.document',
                    verbose_name='Documents autorisés (sélection)',
                )),
            ],
            options={
                'verbose_name':        "Token d'audit",
                'verbose_name_plural': "Tokens d'audit",
                'ordering':            ['-date_creation'],
            },
        ),
    ]
