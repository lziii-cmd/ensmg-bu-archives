"""
Migration 0009 — Module Courrier
Ajoute les 4 modèles du module courrier :
  - Courrier (entité principale arrivée/départ)
  - MouvementCourrier (journal d'audit immuable)
  - BordereauVersementCourrier (versement aux Archives nationales)
  - BordereauEliminationCourrier (élimination avec visa DAS obligatoire)
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archives', '0008_document_corbeille_texte_audit_token'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. Courrier ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Courrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_enregistrement', models.CharField(
                    db_index=True, editable=False, max_length=40, unique=True,
                    help_text='Format : ENSMG-ARR-AAAA-XXXXX ou ENSMG-DEP-AAAA-XXXXX',
                    verbose_name="Numéro d'enregistrement",
                )),
                ('sens', models.CharField(
                    choices=[('ARRIVEE', 'Arrivée'), ('DEPART', 'Départ')],
                    db_index=True, max_length=10, verbose_name='Sens',
                )),
                ('objet', models.CharField(max_length=500, verbose_name='Objet')),
                ('date_courrier', models.DateField(verbose_name='Date du courrier')),
                ('date_enregistrement', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Date d'enregistrement")),
                ('reference_expediteur', models.CharField(
                    blank=True, max_length=100,
                    help_text='Référence figurant sur le document original',
                    verbose_name='Référence expéditeur',
                )),
                ('expediteur', models.CharField(max_length=300, verbose_name='Expéditeur')),
                ('destinataire', models.CharField(max_length=300, verbose_name='Destinataire')),
                ('service_interne', models.CharField(
                    blank=True, max_length=200,
                    help_text='Service ENSMG destinataire (arrivée) ou expéditeur (départ)',
                    verbose_name='Service interne concerné',
                )),
                ('ampliation', models.TextField(
                    blank=True,
                    help_text='Services mis en copie, séparés par des virgules',
                    verbose_name='Ampliation',
                )),
                ('instructions', models.TextField(blank=True, verbose_name='Instructions de traitement')),
                ('description', models.TextField(blank=True, verbose_name='Description / Résumé')),
                ('mots_cles', models.TextField(
                    blank=True,
                    help_text='Séparés par des virgules',
                    verbose_name='Mots-clés',
                )),
                ('delai_reponse', models.DateField(
                    blank=True, null=True,
                    help_text='Date limite de réponse attendue (courrier arrivée uniquement)',
                    verbose_name='Délai de réponse',
                )),
                ('accuse_reception', models.BooleanField(default=False, verbose_name='Accusé de réception envoyé')),
                ('fichier', models.FileField(
                    blank=True, null=True,
                    upload_to='courriers/%Y/%m/',
                    verbose_name='Fichier numérique (scan)',
                )),
                ('nom_fichier_original', models.CharField(blank=True, max_length=255, verbose_name='Nom du fichier original')),
                ('taille_fichier', models.BigIntegerField(blank=True, null=True, verbose_name='Taille (octets)')),
                ('empreinte_sha256', models.CharField(blank=True, max_length=64, verbose_name='Empreinte SHA-256')),
                ('localisation_physique', models.CharField(
                    blank=True, max_length=300,
                    help_text='Ex : Classeur n°3, Registre 2026, Intercalaire Mai',
                    verbose_name='Localisation physique',
                )),
                ('statut', models.CharField(
                    choices=[
                        ('ENREGISTRE', 'Enregistré'),
                        ('EN_TRAITEMENT', 'En traitement'),
                        ('TRAITE', 'Traité'),
                        ('ARCHIVE', 'Archivé'),
                        ('VERSE', 'Versé aux Archives nationales'),
                        ('ELIMINE', 'Éliminé'),
                    ],
                    db_index=True, default='ENREGISTRE', max_length=20, verbose_name='Statut',
                )),
                ('confidentialite', models.CharField(
                    choices=[
                        ('PUBLIC', 'Public'),
                        ('INTERNE', 'Usage interne'),
                        ('CONFIDENTIEL', 'Confidentiel'),
                    ],
                    default='INTERNE', max_length=20, verbose_name='Confidentialité',
                )),
                ('date_fin_dua', models.DateField(blank=True, null=True, verbose_name='Date de fin de DUA')),
                ('sort_final', models.CharField(
                    choices=[
                        ('CONSERVATION', 'Conservation définitive'),
                        ('ELIMINATION', 'Élimination'),
                        ('TRI', 'Tri'),
                        ('EN_ATTENTE', 'En attente de décision'),
                    ],
                    default='EN_ATTENTE', max_length=20, verbose_name='Sort final',
                )),
                ('date_traitement', models.DateTimeField(blank=True, null=True, verbose_name='Date de traitement')),
                ('date_archivage', models.DateTimeField(blank=True, null=True, verbose_name="Date d'archivage")),
                ('deleted_at', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Suppression logique — purge automatique après 30 jours.',
                    verbose_name='Mis en corbeille le',
                )),
                ('en_reponse_a', models.ForeignKey(
                    blank=True, null=True,
                    limit_choices_to={'sens': 'ARRIVEE'},
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reponses',
                    to='archives.courrier',
                    verbose_name='En réponse au courrier arrivée',
                )),
                ('tableau_gestion', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='archives.tableaugestion',
                    verbose_name='Tableau de gestion (DUA)',
                )),
                ('cree_par', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='courriers_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Enregistré par',
                )),
                ('traite_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='courriers_traites',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Traité par',
                )),
            ],
            options={
                'verbose_name': 'Courrier',
                'verbose_name_plural': 'Courriers',
                'ordering': ['-date_enregistrement'],
                'permissions': [
                    ('can_enregistrer_courrier', 'Peut enregistrer un courrier'),
                    ('can_traiter_courrier', 'Peut traiter un courrier'),
                    ('can_archiver_courrier', 'Peut archiver un courrier'),
                    ('can_verse_courrier', 'Peut verser des courriers'),
                    ('can_eliminer_courrier', 'Peut éliminer des courriers'),
                ],
            },
        ),

        # ── 2. MouvementCourrier ───────────────────────────────────────────────
        migrations.CreateModel(
            name='MouvementCourrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('ENREGISTREMENT', 'Enregistrement'),
                        ('MODIFICATION', 'Modification'),
                        ('CONSULTATION', 'Consultation'),
                        ('TRAITEMENT', 'Traitement'),
                        ('ARCHIVAGE', 'Archivage'),
                        ('VERSEMENT', 'Versement'),
                        ('ELIMINATION', 'Élimination'),
                        ('RESTAURATION', 'Restauration depuis la corbeille'),
                        ('TELECHARGEMENT', 'Téléchargement'),
                    ],
                    max_length=30, verbose_name='Action',
                )),
                ('date_action', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Date et heure')),
                ('commentaire', models.TextField(blank=True, verbose_name='Commentaire')),
                ('details', models.JSONField(default=dict, verbose_name='Détails (avant/après)')),
                ('adresse_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='Adresse IP')),
                ('courrier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mouvements',
                    to='archives.courrier',
                    verbose_name='Courrier',
                )),
                ('utilisateur', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': "Journal d'audit — Courrier",
                'verbose_name_plural': "Journal d'audit — Courriers",
                'ordering': ['-date_action'],
                'default_permissions': ('add', 'view'),
            },
        ),

        # ── 3. BordereauVersementCourrier ──────────────────────────────────────
        migrations.CreateModel(
            name='BordereauVersementCourrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')),
                ('date_creation', models.DateField(auto_now_add=True, verbose_name='Date de création')),
                ('service_versant', models.CharField(default='Secrétariat ENSMG', max_length=200, verbose_name='Service versant')),
                ('service_destinataire', models.CharField(default='Archives nationales du Sénégal', max_length=200, verbose_name='Service destinataire')),
                ('statut', models.CharField(
                    choices=[
                        ('BROUILLON', 'Brouillon'),
                        ('EN_VALIDATION', 'En attente de validation'),
                        ('VALIDE', 'Validé'),
                        ('EXECUTE', 'Exécuté'),
                        ('REJETE', 'Rejeté'),
                    ],
                    default='BROUILLON', max_length=20, verbose_name='Statut',
                )),
                ('observations', models.TextField(blank=True, verbose_name='Observations')),
                ('date_validation', models.DateField(blank=True, null=True, verbose_name='Date de validation')),
                ('courriers', models.ManyToManyField(
                    related_name='bordereaux_versement',
                    to='archives.courrier',
                    verbose_name='Courriers versés',
                )),
                ('cree_par', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='bv_courriers_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
                ('valide_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='bv_courriers_valides',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Validé par',
                )),
            ],
            options={
                'verbose_name': 'Bordereau de versement (Courriers)',
                'verbose_name_plural': 'Bordereaux de versement (Courriers)',
                'ordering': ['-date_creation'],
            },
        ),

        # ── 4. BordereauEliminationCourrier ────────────────────────────────────
        migrations.CreateModel(
            name='BordereauEliminationCourrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=30, unique=True, verbose_name='Numéro de bordereau')),
                ('date_creation', models.DateField(auto_now_add=True, verbose_name='Date de création')),
                ('service_producteur', models.CharField(default='Secrétariat ENSMG', max_length=200, verbose_name='Service producteur')),
                ('statut', models.CharField(
                    choices=[
                        ('BROUILLON', 'Brouillon'),
                        ('EN_VALIDATION', "En attente de visa archivistique (DAS)"),
                        ('VISA_OBTENU', "Visa obtenu — Élimination autorisée"),
                        ('EXECUTE', 'Élimination exécutée'),
                        ('REJETE', 'Rejeté par la DAS'),
                    ],
                    default='BROUILLON', max_length=20, verbose_name='Statut',
                )),
                ('motif', models.TextField(verbose_name="Motif d'élimination")),
                ('observations', models.TextField(blank=True, verbose_name='Observations')),
                ('visa_das', models.BooleanField(default=False, verbose_name='Visa DAS obtenu')),
                ('date_visa', models.DateField(blank=True, null=True, verbose_name='Date du visa')),
                ('reference_visa', models.CharField(blank=True, max_length=100, verbose_name='Référence du visa')),
                ('date_elimination', models.DateField(blank=True, null=True, verbose_name="Date d'élimination effective")),
                ('courriers', models.ManyToManyField(
                    related_name='bordereaux_elimination',
                    to='archives.courrier',
                    verbose_name='Courriers à éliminer',
                )),
                ('cree_par', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='be_courriers_crees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Créé par',
                )),
            ],
            options={
                'verbose_name': "Bordereau d'élimination (Courriers)",
                'verbose_name_plural': "Bordereaux d'élimination (Courriers)",
                'ordering': ['-date_creation'],
            },
        ),
    ]
