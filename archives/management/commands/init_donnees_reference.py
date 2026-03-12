"""
Commande de gestion Django : initialisation des données de référence ENSMG.

Usage :
    python manage.py init_donnees_reference
    python manage.py init_donnees_reference --reset   # efface et recharge tout

Charge :
  1. Les départements et services de l'ENSMG
  2. Les 8 catégories documentaires (CDC § 4)
  3. Le plan de classement hiérarchique ENSMG (Fonds → Séries → Sous-séries)
  4. Le tableau de gestion des DUA (Loi 2006-19 + ISO 15489)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from archives.models import CategorieDocument, PlanClassement, TableauGestion
from users.models import Departement


# =============================================================================
# DONNÉES DE RÉFÉRENCE
# =============================================================================

# Départements : (code, nom, type, description)
DEPARTEMENTS = [
    ('DG',    'Direction Générale',                        'DIRECTION',     'Directeur et cabinet de direction.'),
    ('DAF',   'Direction Administrative et Financière',    'ADMINISTRATIF', 'Gestion financière, comptabilité et budget.'),
    ('DRH',   'Direction des Ressources Humaines',         'ADMINISTRATIF', 'Recrutement, carrières et paie du personnel.'),
    ('SCO',   'Scolarité',                                 'ADMINISTRATIF', 'Gestion des inscriptions, dossiers étudiants, diplômes et examens.'),
    ('DM',    'Département Mines',                         'PEDAGOGIQUE',   'Formation et recherche en génie minier et extraction minière.'),
    ('DGE',   'Département Géologie',                      'PEDAGOGIQUE',   'Formation et recherche en géologie générale et structurale.'),
    ('DGT',   'Département Géotechnique',                  'PEDAGOGIQUE',   'Formation et recherche en géotechnique et mécanique des sols.'),
    ('LAB',   'Laboratoires',                              'SCIENTIFIQUE',  'Laboratoires de recherche : pétrographie, géochimie, géophysique.'),
    ('CARTO', 'Cartographie et SIG',                       'SCIENTIFIQUE',  'Production et gestion des cartes géologiques et systèmes d\'information géographique.'),
    ('BIB',   'Bibliothèque et Documentation',             'SUPPORT',       'Gestion du fonds documentaire, revues et thèses.'),
    ('COOP',  'Coopération et Relations Extérieures',      'DIRECTION',     'Partenariats, conventions et coopération internationale.'),
    ('INFO',  'Service Informatique',                      'SUPPORT',       'Infrastructure informatique, systèmes d\'information et sécurité.'),
    ('LOG',   'Logistique et Patrimoine',                  'SUPPORT',       'Gestion du patrimoine immobilier et des équipements.'),
]

CATEGORIES = [
    {'code': 'ADM', 'nom': 'Administratif et institutionnel',       'description': 'Textes réglementaires, décisions, courriers, rapports d\'activités.'},
    {'code': 'PED', 'nom': 'Gestion académique et pédagogique',     'description': 'Programmes, diplômes, dossiers étudiants, jurys, dossiers CAMES.'},
    {'code': 'SCI', 'nom': 'Scientifique et de recherche',          'description': 'Projets de recherche, publications, thèses et mémoires, données expérimentales.'},
    {'code': 'GEO', 'nom': 'Géologique et minier',                  'description': 'Cartes géologiques, logs de forages, rapports de prospection, bases de données minières.'},
    {'code': 'TER', 'nom': 'Terrain et technique',                  'description': 'Carnets de terrain, fiches d\'échantillonnage, analyses pétrographiques et géophysiques.'},
    {'code': 'PAR', 'nom': 'Partenariats et industrie',             'description': 'Conventions, contrats de stage, rapports d\'immersion industrielle.'},
    {'code': 'FRH', 'nom': 'Financier et ressources humaines',      'description': 'Budgets, dossiers du personnel, fiches de paie, contrats.'},
    {'code': 'PAT', 'nom': 'Patrimonial et historique',             'description': 'Archives historiques, photographies anciennes, documents fondateurs.'},
]

# Plan de classement : (code, intitulé, code_parent, niveau, code_categorie)
PLAN_CLASSEMENT = [
    # ── FONDS 1 : DIRECTION ET GOUVERNANCE ──────────────────────────────────
    ('F1',       'Direction et gouvernance',                        None,   1, 'ADM'),
    ('F1.S1',    'Textes réglementaires et institutionnels',        'F1',   2, 'ADM'),
    ('F1.S1.1',  'Statuts et décrets de création',                  'F1.S1', 3, 'ADM'),
    ('F1.S1.2',  'Règlements intérieurs',                           'F1.S1', 3, 'ADM'),
    ('F1.S1.3',  'Notes de service et circulaires',                 'F1.S1', 3, 'ADM'),
    ('F1.S2',    'Conseil d\'administration et conseil scientifique','F1',   2, 'ADM'),
    ('F1.S2.1',  'Procès-verbaux du Conseil d\'administration',     'F1.S2', 3, 'ADM'),
    ('F1.S2.2',  'Procès-verbaux du Conseil scientifique',          'F1.S2', 3, 'ADM'),
    ('F1.S2.3',  'Rapports annuels d\'activités',                   'F1.S2', 3, 'ADM'),
    ('F1.S3',    'Correspondances de la Direction',                 'F1',   2, 'ADM'),
    ('F1.S3.1',  'Courriers entrants',                              'F1.S3', 3, 'ADM'),
    ('F1.S3.2',  'Courriers sortants',                              'F1.S3', 3, 'ADM'),

    # ── FONDS 2 : GESTION ACADÉMIQUE ET PÉDAGOGIQUE ──────────────────────────
    ('F2',       'Gestion académique et pédagogique',               None,   1, 'PED'),
    ('F2.S1',    'Programmes et formations',                        'F2',   2, 'PED'),
    ('F2.S1.1',  'Programmes de formation — Mines',                 'F2.S1', 3, 'PED'),
    ('F2.S1.2',  'Programmes de formation — Géologie',              'F2.S1', 3, 'PED'),
    ('F2.S1.3',  'Programmes de formation — Géotechnique',          'F2.S1', 3, 'PED'),
    ('F2.S1.4',  'Plans de cours et supports pédagogiques',         'F2.S1', 3, 'PED'),
    ('F2.S2',    'Examens et jurys',                                'F2',   2, 'PED'),
    ('F2.S2.1',  'Sujets d\'examens et corrigés',                   'F2.S2', 3, 'PED'),
    ('F2.S2.2',  'Procès-verbaux de jurys et délibérations',        'F2.S2', 3, 'PED'),
    ('F2.S2.3',  'Relevés de notes',                                'F2.S2', 3, 'PED'),
    ('F2.S3',    'Dossiers étudiants',                              'F2',   2, 'PED'),
    ('F2.S3.1',  'Dossiers d\'inscription et académiques',          'F2.S3', 3, 'PED'),
    ('F2.S3.2',  'Diplômes et attestations de réussite',            'F2.S3', 3, 'PED'),
    ('F2.S3.3',  'Dossiers CAMES',                                  'F2.S3', 3, 'PED'),

    # ── FONDS 3 : RECHERCHE SCIENTIFIQUE ─────────────────────────────────────
    ('F3',       'Recherche scientifique',                          None,   1, 'SCI'),
    ('F3.S1',    'Projets et programmes de recherche',              'F3',   2, 'SCI'),
    ('F3.S1.1',  'Protocoles et rapports de recherche',             'F3.S1', 3, 'SCI'),
    ('F3.S1.2',  'Publications scientifiques et articles',          'F3.S1', 3, 'SCI'),
    ('F3.S1.3',  'Données expérimentales et résultats d\'analyses', 'F3.S1', 3, 'SCI'),
    ('F3.S2',    'Thèses, mémoires et rapports de fin d\'études',   'F3',   2, 'SCI'),
    ('F3.S2.1',  'Thèses de doctorat',                              'F3.S2', 3, 'SCI'),
    ('F3.S2.2',  'Mémoires de master',                              'F3.S2', 3, 'SCI'),
    ('F3.S2.3',  'Rapports de projets de fin d\'études (PFE)',      'F3.S2', 3, 'SCI'),

    # ── FONDS 4 : ARCHIVES GÉOLOGIQUES ET MINIÈRES ───────────────────────────
    ('F4',       'Archives géologiques et minières',                None,   1, 'GEO'),
    ('F4.S1',    'Cartographie géologique',                         'F4',   2, 'GEO'),
    ('F4.S1.1',  'Cartes géologiques',                              'F4.S1', 3, 'GEO'),
    ('F4.S1.2',  'Cartes minières et métallogéniques',              'F4.S1', 3, 'GEO'),
    ('F4.S1.3',  'Cartes géotechniques',                            'F4.S1', 3, 'GEO'),
    ('F4.S2',    'Rapports de terrain et de forage',                'F4',   2, 'GEO'),
    ('F4.S2.1',  'Rapports de prospection et d\'exploration',       'F4.S2', 3, 'GEO'),
    ('F4.S2.2',  'Logs de forages et données de sondage',           'F4.S2', 3, 'GEO'),
    ('F4.S2.3',  'Études de faisabilité et d\'exploitation',        'F4.S2', 3, 'GEO'),
    ('F4.S3',    'Bases de données géologiques',                    'F4',   2, 'GEO'),
    ('F4.S3.1',  'Bases de données minières',                       'F4.S3', 3, 'GEO'),
    ('F4.S3.2',  'Données géophysiques et géochimiques',            'F4.S3', 3, 'GEO'),

    # ── FONDS 5 : ARCHIVES DE TERRAIN ET TECHNIQUES ──────────────────────────
    ('F5',       'Archives de terrain et techniques',               None,   1, 'TER'),
    ('F5.S1',    'Carnets et rapports de terrain',                  'F5',   2, 'TER'),
    ('F5.S1.1',  'Carnets de terrain',                              'F5.S1', 3, 'TER'),
    ('F5.S1.2',  'Fiches d\'échantillonnage',                       'F5.S1', 3, 'TER'),
    ('F5.S2',    'Analyses de laboratoire',                         'F5',   2, 'TER'),
    ('F5.S2.1',  'Analyses pétrographiques',                        'F5.S2', 3, 'TER'),
    ('F5.S2.2',  'Analyses géochimiques',                           'F5.S2', 3, 'TER'),
    ('F5.S2.3',  'Analyses géophysiques',                           'F5.S2', 3, 'TER'),
    ('F5.S3',    'Photographies et iconographie scientifique',       'F5',   2, 'TER'),

    # ── FONDS 6 : PARTENARIATS ET RELATIONS EXTÉRIEURES ──────────────────────
    ('F6',       'Partenariats et relations extérieures',           None,   1, 'PAR'),
    ('F6.S1',    'Conventions et accords',                          'F6',   2, 'PAR'),
    ('F6.S1.1',  'Conventions de partenariat national',             'F6.S1', 3, 'PAR'),
    ('F6.S1.2',  'Accords de coopération internationale',           'F6.S1', 3, 'PAR'),
    ('F6.S2',    'Stages et insertion professionnelle',             'F6',   2, 'PAR'),
    ('F6.S2.1',  'Contrats de stage',                               'F6.S2', 3, 'PAR'),
    ('F6.S2.2',  'Rapports de stages et d\'immersion industrielle', 'F6.S2', 3, 'PAR'),

    # ── FONDS 7 : FINANCES ET RESSOURCES HUMAINES ────────────────────────────
    ('F7',       'Finances et ressources humaines',                 None,   1, 'FRH'),
    ('F7.S1',    'Gestion financière et comptable',                 'F7',   2, 'FRH'),
    ('F7.S1.1',  'Budgets et rapports financiers annuels',          'F7.S1', 3, 'FRH'),
    ('F7.S1.2',  'Pièces comptables et justificatifs',              'F7.S1', 3, 'FRH'),
    ('F7.S2',    'Ressources humaines',                             'F7',   2, 'FRH'),
    ('F7.S2.1',  'Dossiers du personnel enseignant',                'F7.S2', 3, 'FRH'),
    ('F7.S2.2',  'Dossiers du personnel administratif et technique','F7.S2', 3, 'FRH'),
    ('F7.S2.3',  'Fiches de paie, contrats et arrêtés',            'F7.S2', 3, 'FRH'),

    # ── FONDS 8 : PATRIMOINE ET MÉMOIRE INSTITUTIONNELLE ─────────────────────
    ('F8',       'Patrimoine et mémoire institutionnelle',          None,   1, 'PAT'),
    ('F8.S1',    'Archives historiques',                            'F8',   2, 'PAT'),
    ('F8.S1.1',  'Documents fondateurs de l\'ENSMG',               'F8.S1', 3, 'PAT'),
    ('F8.S1.2',  'Photographies et iconographie historique',        'F8.S1', 3, 'PAT'),
    ('F8.S1.3',  'Témoignages et publications historiques',         'F8.S1', 3, 'PAT'),
]

# Tableau de gestion DUA : (intitulé, code_catégorie, DUA courante, DUA intermédiaire, sort final, observations)
TABLEAU_GESTION = [
    # ADMINISTRATIF
    ('Statuts et textes réglementaires de l\'école',    'ADM', 0, 0, 'CONSERVATION', 'Conservation définitive — documents constitutifs. Loi 2006-19 art. 8.'),
    ('Décisions et arrêtés de direction',              'ADM', 5, 10, 'CONSERVATION', 'Conservation définitive après 15 ans. Valeur probatoire.'),
    ('Notes de service et circulaires',                'ADM', 3, 2,  'ELIMINATION',  'Élimination après 5 ans. Pas de valeur historique durable.'),
    ('Procès-verbaux du Conseil d\'administration',    'ADM', 5, 10, 'CONSERVATION', 'Conservation définitive. Valeur juridique et historique.'),
    ('Procès-verbaux du Conseil scientifique',         'ADM', 5, 10, 'CONSERVATION', 'Conservation définitive. Valeur scientifique et institutionnelle.'),
    ('Rapports annuels d\'activités',                  'ADM', 5, 5,  'CONSERVATION', 'Conservation définitive après 10 ans. Mémoire institutionnelle.'),
    ('Courriers entrants et sortants',                 'ADM', 3, 2,  'TRI',          'Tri : conserver les courriers à valeur décisionnelle, éliminer les accusés de réception.'),

    # PÉDAGOGIQUE
    ('Programmes de formation',                        'PED', 5, 5,  'CONSERVATION', 'Conservation définitive. Base de l\'accréditation et du suivi pédagogique.'),
    ('Sujets d\'examens et corrigés',                  'PED', 5, 0,  'ELIMINATION',  'Élimination après 5 ans sauf sujets particulièrement innovants (tri).'),
    ('Procès-verbaux de jurys et délibérations',       'PED', 10, 10, 'CONSERVATION', 'Conservation définitive. Valeur juridique et probatoire pour les diplômés.'),
    ('Dossiers académiques des étudiants',             'PED', 5, 20, 'CONSERVATION', 'Conservation 25 ans minimum. Preuve de diplomation.'),
    ('Diplômes et attestations de réussite',           'PED', 0, 0,  'CONSERVATION', 'Conservation définitive. Valeur juridique absolue.'),
    ('Dossiers CAMES',                                 'PED', 10, 10, 'CONSERVATION', 'Conservation définitive. Valeur probatoire pour l\'avancement des enseignants.'),
    ('Plans de cours et supports pédagogiques',        'PED', 3, 2,  'TRI',          'Tri : conserver les supports innovants ou primés, éliminer les autres.'),

    # SCIENTIFIQUE
    ('Thèses de doctorat',                             'SCI', 0, 0,  'CONSERVATION', 'Conservation définitive. Production scientifique de référence.'),
    ('Mémoires de master et PFE',                      'SCI', 10, 10, 'TRI',          'Tri : conservation des travaux primés ou exploités ; élimination après 20 ans.'),
    ('Rapports de recherche',                          'SCI', 10, 5,  'CONSERVATION', 'Conservation définitive après 15 ans si publication associée.'),
    ('Publications scientifiques',                     'SCI', 0, 0,  'CONSERVATION', 'Conservation définitive. Production intellectuelle de l\'établissement.'),
    ('Données expérimentales et résultats d\'analyses','SCI', 10, 5,  'TRI',          'Tri : conserver données publiées ou citées ; éliminer données brutes non exploitées.'),

    # GÉOLOGIQUE
    ('Cartes géologiques et minières',                 'GEO', 0, 0,  'CONSERVATION', 'Conservation définitive. Valeur scientifique, patrimoniale et stratégique nationale.'),
    ('Logs de forages et données de sondage',          'GEO', 0, 0,  'CONSERVATION', 'Conservation définitive. Données irremplaçables.'),
    ('Rapports de prospection et d\'exploration',      'GEO', 20, 10, 'CONSERVATION', 'Conservation définitive. Valeur scientifique et économique nationale.'),
    ('Études de faisabilité minière',                  'GEO', 20, 10, 'CONSERVATION', 'Conservation définitive. Valeur stratégique nationale.'),
    ('Bases de données géologiques',                   'GEO', 0, 0,  'CONSERVATION', 'Conservation définitive. Ressource scientifique nationale unique.'),

    # TERRAIN
    ('Carnets de terrain',                             'TER', 10, 10, 'CONSERVATION', 'Conservation définitive si données non publiées ailleurs. Sinon tri après 20 ans.'),
    ('Fiches d\'échantillonnage',                      'TER', 10, 5,  'TRI',          'Tri : conserver fiches liées à publications ; éliminer les autres après 15 ans.'),
    ('Rapports d\'analyses pétrographiques',           'TER', 15, 5,  'TRI',          'Tri : conserver si résultats publiés ou base de thèse.'),

    # PARTENARIAT
    ('Conventions de partenariat',                     'PAR', 5, 5,  'CONSERVATION', 'Conservation définitive. Valeur juridique et institutionnelle.'),
    ('Contrats de stage',                              'PAR', 5, 5,  'ELIMINATION',  'Élimination après 10 ans. Délai de prescription commerciale.'),
    ('Rapports de stages',                             'PAR', 5, 5,  'TRI',          'Tri : conserver les rapports primés ou cités ; éliminer les autres.'),
    ('Accords de coopération internationale',          'PAR', 5, 10, 'CONSERVATION', 'Conservation définitive. Valeur diplomatique et institutionnelle.'),

    # FINANCIER / RH
    ('Budgets et rapports financiers annuels',         'FRH', 10, 5,  'CONSERVATION', 'Conservation définitive. Valeur probatoire et historique. Obligations comptables.'),
    ('Pièces comptables et justificatifs de dépenses', 'FRH', 10, 0,  'ELIMINATION',  'Élimination après 10 ans. Délai légal de prescription en droit sénégalais.'),
    ('Dossiers du personnel enseignant',               'FRH', 0, 0,  'CONSERVATION', 'Conservation définitive (50 ans après départ). Droits à la retraite et CAMES.'),
    ('Dossiers du personnel administratif et technique','FRH', 0, 0, 'CONSERVATION', 'Conservation définitive (50 ans après départ). Droits à la retraite.'),
    ('Fiches de paie',                                 'FRH', 10, 0,  'ELIMINATION',  'Élimination après 10 ans. Délai de prescription sociale.'),

    # PATRIMONIAL
    ('Archives historiques fondatrices',               'PAT', 0, 0,  'CONSERVATION', 'Conservation définitive absolue. Mémoire de l\'institution.'),
    ('Photographies historiques',                      'PAT', 0, 0,  'CONSERVATION', 'Conservation définitive. Patrimoine iconographique.'),
]


class Command(BaseCommand):
    help = "Charge les données de référence ENSMG : catégories, plan de classement et tableau de gestion DUA."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Efface toutes les données de référence avant de recharger.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('⚠  Suppression des données de référence existantes...'))
            TableauGestion.objects.all().delete()
            PlanClassement.objects.all().delete()
            CategorieDocument.objects.all().delete()
            Departement.objects.all().delete()
            self.stdout.write(self.style.WARNING('   Données supprimées.\n'))

        with transaction.atomic():
            self._charger_departements()
            self._charger_categories()
            self._charger_plan_classement()
            self._charger_tableau_gestion()

        self.stdout.write(self.style.SUCCESS('\n✅  Données de référence chargées avec succès !'))
        self.stdout.write('   → Accédez à l\'admin pour consulter les données : http://127.0.0.1:8000/admin/')

    # ── Étape 1 : Départements ───────────────────────────────────────────────

    def _charger_departements(self):
        self.stdout.write('\n[1/4] Chargement des départements et services...')
        crees = 0
        for code, nom, type_, description in DEPARTEMENTS:
            _, created = Departement.objects.get_or_create(
                code=code,
                defaults={'nom': nom, 'type': type_, 'description': description, 'actif': True},
            )
            if created:
                crees += 1
                self.stdout.write(f'    + [{code}] {nom}')
        self.stdout.write(self.style.SUCCESS(f'   {crees} département(s) créé(s), {len(DEPARTEMENTS) - crees} déjà existant(s).'))

    # ── Étape 2 : Catégories ─────────────────────────────────────────────────

    def _charger_categories(self):
        self.stdout.write('\n[2/4] Chargement des catégories documentaires...')
        crees = 0
        for data in CATEGORIES:
            _, created = CategorieDocument.objects.get_or_create(
                code=data['code'],
                defaults={'nom': data['nom'], 'description': data['description']},
            )
            if created:
                crees += 1
                self.stdout.write(f'    + [{data["code"]}] {data["nom"]}')
        self.stdout.write(self.style.SUCCESS(f'   {crees} catégorie(s) créée(s), {len(CATEGORIES) - crees} déjà existante(s).'))

    # ── Étape 2 : Plan de classement ─────────────────────────────────────────

    def _charger_plan_classement(self):
        self.stdout.write('\n[3/4] Chargement du plan de classement...')
        crees = 0
        # Index des catégories pour éviter des requêtes répétées
        categories = {c.code: c for c in CategorieDocument.objects.all()}

        for code, intitule, code_parent, niveau, code_cat in PLAN_CLASSEMENT:
            parent = None
            if code_parent:
                try:
                    parent = PlanClassement.objects.get(code=code_parent)
                except PlanClassement.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'    ⚠ Parent introuvable pour {code} (parent={code_parent})'))

            _, created = PlanClassement.objects.get_or_create(
                code=code,
                defaults={
                    'intitule':  intitule,
                    'parent':    parent,
                    'niveau':    niveau,
                    'categorie': categories.get(code_cat),
                    'actif':     True,
                },
            )
            if created:
                crees += 1
                indent = '  ' * (niveau - 1)
                self.stdout.write(f'    {indent}+ {code} — {intitule}')

        self.stdout.write(self.style.SUCCESS(f'   {crees} entrée(s) créée(s), {len(PLAN_CLASSEMENT) - crees} déjà existante(s).'))

    # ── Étape 3 : Tableau de gestion DUA ─────────────────────────────────────

    def _charger_tableau_gestion(self):
        self.stdout.write('\n[4/4] Chargement du tableau de gestion (DUA)...')
        crees = 0
        categories = {c.code: c for c in CategorieDocument.objects.all()}

        for intitule, code_cat, dua_c, dua_i, sort, obs in TABLEAU_GESTION:
            cat = categories.get(code_cat)
            if not cat:
                self.stdout.write(self.style.WARNING(f'    ⚠ Catégorie {code_cat} introuvable pour : {intitule}'))
                continue

            _, created = TableauGestion.objects.get_or_create(
                intitule=intitule,
                type_document=cat,
                defaults={
                    'duree_courante':      dua_c,
                    'duree_intermediaire': dua_i,
                    'sort_final':          sort,
                    'observations':        obs,
                },
            )
            if created:
                crees += 1
                self.stdout.write(f'    + {intitule} ({dua_c}+{dua_i} ans → {sort})')

        self.stdout.write(self.style.SUCCESS(f'   {crees} règle(s) DUA créée(s), {len(TABLEAU_GESTION) - crees} déjà existante(s).'))
