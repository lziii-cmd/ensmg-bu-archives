"""
Commande de peuplement de la base de données avec des données de test réalistes.

Usage :
    python manage.py init_donnees_test
    python manage.py init_donnees_test --reset   # efface et recrée tout

⚠ À utiliser UNIQUEMENT en développement/test.

Crée :
  - 20 utilisateurs (tous les rôles et départements)
  - 80+ documents d'archives réalistes (toutes catégories)
  - Mouvements d'audit pour chaque document
  - 5 bordereaux de versement
  - 5 bordereaux d'élimination
"""

import random
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from archives.models import (
    BordereauElimination,
    BordereauVersement,
    CategorieDocument,
    Document,
    MouvementDocument,
    PlanClassement,
    TableauGestion,
)
from users.models import CustomUser, Departement


# =============================================================================
# DONNÉES DE TEST
# =============================================================================

UTILISATEURS = [
    # (username, prénom, nom, email, rôle, code_dept, téléphone)
    ('admin.sys',    'Amadou',    'DIALLO',    'a.diallo@ensmg.sn',    'ADMIN',      'INFO',  '77 100 00 01'),
    ('archiviste1',  'Fatou',     'NDIAYE',    'f.ndiaye@ensmg.sn',    'ARCHIVISTE', 'BIB',   '77 100 00 02'),
    ('archiviste2',  'Moussa',    'FALL',      'm.fall@ensmg.sn',      'ARCHIVISTE', 'BIB',   '77 100 00 03'),
    ('directeur',    'Ibrahima',  'SECK',      'i.seck@ensmg.sn',      'DIRECTION',  'DG',    '77 100 00 04'),
    ('daf',          'Rokhaya',   'MBAYE',     'r.mbaye@ensmg.sn',     'DIRECTION',  'DAF',   '77 100 00 05'),
    ('sco1',         'Aminata',   'SARR',      'a.sarr@ensmg.sn',      'PERSONNEL',  'SCO',   '77 100 00 06'),
    ('sco2',         'Ousmane',   'GUEYE',     'o.gueye@ensmg.sn',     'PERSONNEL',  'SCO',   '77 100 00 07'),
    ('drh1',         'Mariama',   'CISSE',     'm.cisse@ensmg.sn',     'PERSONNEL',  'DRH',   '77 100 00 08'),
    ('daf1',         'Babacar',   'THIAM',     'b.thiam@ensmg.sn',     'PERSONNEL',  'DAF',   '77 100 00 09'),
    ('log1',         'Ndèye',     'DIOP',      'n.diop@ensmg.sn',      'PERSONNEL',  'LOG',   '77 100 00 10'),
    ('pr.mines1',    'Cheikh',    'WADE',      'c.wade@ensmg.sn',      'ENSEIGNANT', 'DM',    '77 100 00 11'),
    ('pr.mines2',    'Seydou',    'KOUYATE',   's.kouyate@ensmg.sn',   'ENSEIGNANT', 'DM',    '77 100 00 12'),
    ('pr.geo1',      'Awa',       'TOURE',     'a.toure@ensmg.sn',     'ENSEIGNANT', 'DGE',   '77 100 00 13'),
    ('pr.geo2',      'Mamadou',   'BALDE',     'm.balde@ensmg.sn',     'ENSEIGNANT', 'DGE',   '77 100 00 14'),
    ('pr.geotech1',  'Souleymane','SOW',       's.sow@ensmg.sn',       'ENSEIGNANT', 'DGT',   '77 100 00 15'),
    ('pr.lab1',      'Aissatou',  'BARRY',     'a.barry@ensmg.sn',     'ENSEIGNANT', 'LAB',   '77 100 00 16'),
    ('pr.carto1',    'Lamine',    'FAYE',      'l.faye@ensmg.sn',      'ENSEIGNANT', 'CARTO', '77 100 00 17'),
    ('coop1',        'Marème',    'DIOUF',     'm.diouf@ensmg.sn',     'PERSONNEL',  'COOP',  '77 100 00 18'),
    ('info1',        'Pape',      'LY',        'p.ly@ensmg.sn',        'PERSONNEL',  'INFO',  '77 100 00 19'),
    ('bib1',         'Yaye',      'NIANG',     'y.niang@ensmg.sn',     'PERSONNEL',  'BIB',   '77 100 00 20'),
]

# Documents : (titre, producteur_code_dept, code_plan, conf, support, date_creation, desc, mots_cles)
DOCUMENTS = [

    # ── ADMINISTRATIF ────────────────────────────────────────────────────────
    ('Statuts de l\'ENSMG — Version consolidée 2020',
     'DG', 'F1.S1.1', 'PUBLIC', 'MIXTE',
     date(2020, 1, 15),
     'Texte officiel des statuts de l\'École Nationale Supérieure des Mines et de la Géologie, version consolidée approuvée par le Conseil d\'administration.',
     'statuts, réglementation, institution, ENSMG'),

    ('Règlement intérieur de l\'ENSMG — 2022',
     'DG', 'F1.S1.2', 'INTERNE', 'NUMERIQUE',
     date(2022, 3, 10),
     'Règlement intérieur définissant les droits et obligations des personnels et étudiants.',
     'règlement, discipline, intérieur'),

    ('Procès-verbal du Conseil d\'administration — Session ordinaire T1 2024',
     'DG', 'F1.S2.1', 'INTERNE', 'NUMERIQUE',
     date(2024, 2, 20),
     'PV de la session ordinaire du premier trimestre 2024. Ordre du jour : budget, recrutements, partenariats.',
     'conseil administration, PV, 2024'),

    ('Procès-verbal du Conseil d\'administration — Session ordinaire T3 2023',
     'DG', 'F1.S2.1', 'INTERNE', 'NUMERIQUE',
     date(2023, 9, 12),
     'PV de la session ordinaire du troisième trimestre 2023.',
     'conseil administration, PV, 2023'),

    ('Procès-verbal du Conseil scientifique — Session annuelle 2023',
     'DG', 'F1.S2.2', 'INTERNE', 'NUMERIQUE',
     date(2023, 11, 5),
     'Session annuelle du Conseil scientifique : bilan des publications, accréditations et projets de recherche.',
     'conseil scientifique, PV, recherche'),

    ('Rapport annuel d\'activités ENSMG 2023',
     'DG', 'F1.S2.3', 'PUBLIC', 'NUMERIQUE',
     date(2024, 3, 30),
     'Rapport complet des activités pédagogiques, scientifiques et administratives de l\'ENSMG pour l\'année 2023.',
     'rapport annuel, activités, bilan, 2023'),

    ('Note de service n°012/DG/2024 — Calendrier académique',
     'DG', 'F1.S1.3', 'INTERNE', 'NUMERIQUE',
     date(2024, 1, 8),
     'Note fixant le calendrier académique de l\'année 2023-2024 pour toutes les filières.',
     'calendrier, académique, note service'),

    ('Courrier entrant — Ministère des Mines réf. MM/2024/0045',
     'DG', 'F1.S3.1', 'INTERNE', 'NUMERIQUE',
     date(2024, 4, 3),
     'Correspondance du Ministère des Mines relative à l\'organisation du concours national de recrutement.',
     'ministère, courrier, recrutement'),

    # ── PÉDAGOGIQUE ──────────────────────────────────────────────────────────
    ('Programme de formation — Cycle Ingénieur Mines 2023-2024',
     'SCO', 'F2.S1.1', 'PUBLIC', 'NUMERIQUE',
     date(2023, 9, 1),
     'Programme officiel de la filière Génie Minier pour l\'année académique 2023-2024 : modules, crédits, enseignants responsables.',
     'programme, mines, ingénieur, formation'),

    ('Programme de formation — Cycle Ingénieur Géologie 2023-2024',
     'SCO', 'F2.S1.2', 'PUBLIC', 'NUMERIQUE',
     date(2023, 9, 1),
     'Programme officiel de la filière Géologie pour l\'année académique 2023-2024.',
     'programme, géologie, ingénieur, formation'),

    ('Programme de formation — Cycle Ingénieur Géotechnique 2023-2024',
     'SCO', 'F2.S1.3', 'PUBLIC', 'NUMERIQUE',
     date(2023, 9, 1),
     'Programme officiel de la filière Géotechnique pour l\'année académique 2023-2024.',
     'programme, géotechnique, ingénieur, formation'),

    ('Sujets d\'examens de Géologie structurale — Semestre 5, Janvier 2024',
     'SCO', 'F2.S2.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 1, 15),
     'Ensemble des sujets d\'examens de la session de janvier 2024 pour le cours de Géologie structurale (S5).',
     'examens, géologie structurale, S5, 2024'),

    ('Sujets d\'examens de Géomécanique — Semestre 6, Juin 2024',
     'SCO', 'F2.S2.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 6, 3),
     'Sujets de la session de juin 2024 pour le cours de Géomécanique (S6).',
     'examens, géomécanique, S6, 2024'),

    ('Procès-verbal de jury — Promotion 2024, Filière Mines',
     'SCO', 'F2.S2.2', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 7, 18),
     'PV de délibération du jury de fin d\'année pour la promotion 2024 de la filière Génie Minier. 42 étudiants délibérés.',
     'jury, délibération, mines, promotion 2024'),

    ('Procès-verbal de jury — Promotion 2024, Filière Géologie',
     'SCO', 'F2.S2.2', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 7, 19),
     'PV de délibération du jury de fin d\'année pour la promotion 2024 de la filière Géologie. 38 étudiants délibérés.',
     'jury, délibération, géologie, promotion 2024'),

    ('Dossier académique — DIALLO Mamadou (Promo 2021)',
     'SCO', 'F2.S3.1', 'SECRET', 'MIXTE',
     date(2021, 10, 5),
     'Dossier complet d\'inscription, relevés de notes, convention de stage et attestations pour l\'étudiant Mamadou DIALLO.',
     'dossier étudiant, scolarité, Promo 2021'),

    ('Dossier académique — NDIAYE Aïssatou (Promo 2022)',
     'SCO', 'F2.S3.1', 'SECRET', 'MIXTE',
     date(2022, 10, 3),
     'Dossier complet pour l\'étudiante Aïssatou NDIAYE, promotion 2022, filière Géotechnique.',
     'dossier étudiant, scolarité, Promo 2022'),

    ('Diplôme d\'Ingénieur Mines — FALL Oumar, Promotion 2023',
     'SCO', 'F2.S3.2', 'SECRET', 'MIXTE',
     date(2023, 12, 15),
     'Diplôme original d\'Ingénieur en Génie Minier délivré à Oumar FALL, mention Très Bien.',
     'diplôme, ingénieur, mines, promotion 2023'),

    ('Dossier CAMES — Pr. Cheikh WADE, Maître de Conférences',
     'DRH', 'F2.S3.3', 'CONFIDENTIEL', 'MIXTE',
     date(2023, 6, 1),
     'Dossier complet de candidature au grade de Maître de Conférences soumis au CAMES pour le Pr. Cheikh WADE.',
     'CAMES, promotion, enseignant, mines'),

    # ── SCIENTIFIQUE ─────────────────────────────────────────────────────────
    ('Rapport de recherche — Caractérisation minéralogique des gisements de phosphate de Thiès',
     'LAB', 'F3.S1.1', 'INTERNE', 'NUMERIQUE',
     date(2023, 5, 20),
     'Étude complète de la minéralogie des gisements de phosphate de la région de Thiès : analyses DRX, MEB et géochimiques.',
     'phosphate, Thiès, minéralogie, recherche'),

    ('Article scientifique — Potentiel aurifère du Sénégal Oriental',
     'LAB', 'F3.S1.2', 'PUBLIC', 'NUMERIQUE',
     date(2023, 8, 10),
     'Article publié dans la revue African Journal of Earth Sciences sur le potentiel aurifère du Sénégal Oriental.',
     'or, Sénégal Oriental, aurifère, publication'),

    ('Thèse de doctorat — Modélisation 3D du gisement de fer de Falémé',
     'LAB', 'F3.S2.1', 'PUBLIC', 'NUMERIQUE',
     date(2022, 12, 8),
     'Thèse de doctorat présentée par Dr. Ibrahima SOW. Modélisation géostatistique du gisement de fer de la Falémé par méthodes krigeage ordinaire.',
     'thèse, fer, Falémé, modélisation, géostatistique'),

    ('Mémoire de master — Étude géotechnique du site de barrage de Sambangalou',
     'DGT', 'F3.S2.2', 'PUBLIC', 'NUMERIQUE',
     date(2023, 9, 15),
     'Mémoire de fin d\'études de master spécialisé en géotechnique. Étude des fondations et stabilité des pentes du barrage.',
     'mémoire, géotechnique, barrage, Sambangalou'),

    ('Rapport de fin d\'études — Évaluation environnementale de la mine de zircon de Diogo',
     'DM', 'F3.S2.3', 'PUBLIC', 'NUMERIQUE',
     date(2024, 2, 28),
     'Rapport de projet de fin d\'études sur l\'évaluation de l\'impact environnemental des opérations minières à Diogo.',
     'PFE, zircon, Diogo, environnement, mines'),

    ('Données expérimentales — Essais de résistance mécanique roches volcaniques 2023',
     'LAB', 'F3.S1.3', 'INTERNE', 'NUMERIQUE',
     date(2023, 11, 12),
     'Jeu de données des essais de compression simple et triaxiale réalisés sur des échantillons de roches volcaniques du Cap-Vert sénégalais.',
     'données, essais, résistance, volcanisme'),

    # ── GÉOLOGIQUE ───────────────────────────────────────────────────────────
    ('Carte géologique du Sénégal Oriental — Feuille Kédougou 1/200 000',
     'CARTO', 'F4.S1.1', 'PUBLIC', 'MIXTE',
     date(2019, 6, 1),
     'Carte géologique à 1/200 000 de la région de Kédougou produite dans le cadre du projet de cartographie nationale. Couvre les formations du Birimien.',
     'carte géologique, Kédougou, Birimien, 1/200000'),

    ('Carte géologique du Bassin sédimentaire côtier — 1/500 000',
     'CARTO', 'F4.S1.1', 'PUBLIC', 'MIXTE',
     date(2020, 3, 15),
     'Carte du bassin sédimentaire côtier sénégalais couvrant les formations tertiaires et quaternaires.',
     'carte géologique, bassin sédimentaire, côtier, 1/500000'),

    ('Carte des ressources minières du Sénégal — Édition 2021',
     'CARTO', 'F4.S1.2', 'PUBLIC', 'MIXTE',
     date(2021, 7, 20),
     'Carte de synthèse des ressources minérales du Sénégal : or, phosphate, fer, zircon, calcaire, attapulgite.',
     'ressources minières, carte, inventaire, Sénégal'),

    ('Carte géotechnique de Dakar — Zone Plateau 1/10 000',
     'CARTO', 'F4.S1.3', 'INTERNE', 'MIXTE',
     date(2022, 5, 10),
     'Carte géotechnique détaillée de la zone Plateau de Dakar : nature des sols, profondeur du substratum, contraintes de construction.',
     'carte géotechnique, Dakar, Plateau, construction'),

    ('Rapport de prospection minière — Zone Sabodala-Massawa',
     'DM', 'F4.S2.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2021, 11, 30),
     'Rapport de campagne de prospection géochimique et géophysique dans la zone Sabodala-Massawa. Identification de 3 cibles d\'exploration.',
     'prospection, Sabodala, or, géochimie, géophysique'),

    ('Logs de forages — Campagne 2022, Site Loulo-Gounkoto',
     'LAB', 'F4.S2.2', 'CONFIDENTIEL', 'MIXTE',
     date(2022, 8, 15),
     'Logs détaillés des 24 forages de la campagne 2022 sur le site Loulo-Gounkoto : lithologie, minéralogie, teneurs en or.',
     'forages, logs, Loulo, or, lithologie'),

    ('Étude de faisabilité — Exploitation du gisement de calcaire de Bargny',
     'DM', 'F4.S2.3', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2023, 4, 25),
     'Étude technico-économique complète de la faisabilité d\'exploitation industrielle du gisement calcaire de Bargny pour la production de ciment.',
     'faisabilité, calcaire, Bargny, ciment, exploitation'),

    ('Base de données géochimiques — Région de Kédougou-Kéniéba',
     'CARTO', 'F4.S3.1', 'INTERNE', 'NUMERIQUE',
     date(2022, 12, 1),
     'Base de données de 4 200 analyses géochimiques multi-élémentaires (50 éléments) des sédiments de rivière de la région Kédougou-Kéniéba.',
     'géochimie, base de données, Kédougou, sédiments'),

    # ── TERRAIN ──────────────────────────────────────────────────────────────
    ('Carnet de terrain — Mission géologique Kédougou, Mars 2023',
     'DGE', 'F5.S1.1', 'INTERNE', 'PAPIER',
     date(2023, 3, 28),
     'Carnet de terrain de la mission de cartographie géologique dans la région de Kédougou. 15 jours de terrain, 3 géologues.',
     'carnet terrain, Kédougou, cartographie, mission'),

    ('Fiches d\'échantillonnage — Campagne roches Thiès 2023',
     'LAB', 'F5.S1.2', 'INTERNE', 'MIXTE',
     date(2023, 7, 14),
     '145 fiches d\'échantillonnage de la campagne de collecte d\'échantillons de roches dans la région de Thiès.',
     'échantillonnage, Thiès, fiches, collecte'),

    ('Rapport d\'analyses pétrographiques — Granites de Saraya',
     'LAB', 'F5.S2.1', 'INTERNE', 'NUMERIQUE',
     date(2023, 10, 5),
     'Analyses pétrographiques en lames minces de 42 échantillons de granite de la région de Saraya. Classification et interprétation géodynamique.',
     'pétrographie, granite, Saraya, lames minces'),

    ('Rapport d\'analyses géochimiques — Indices aurifères Falémé 2022',
     'LAB', 'F5.S2.2', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2022, 9, 20),
     'Résultats des analyses géochimiques (ICP-MS) sur 380 échantillons prélevés sur les indices aurifères de la Falémé.',
     'géochimie, or, Falémé, ICP-MS, analyses'),

    # ── PARTENARIATS ─────────────────────────────────────────────────────────
    ('Convention de partenariat — ENSMG / Teranga Gold Corporation',
     'COOP', 'F6.S1.1', 'INTERNE', 'MIXTE',
     date(2022, 6, 15),
     'Convention cadre de collaboration entre l\'ENSMG et Teranga Gold pour des stages, des formations continues et des projets de recherche appliquée.',
     'convention, Teranga Gold, partenariat, mines'),

    ('Accord de coopération — ENSMG / Université de Lorraine (France)',
     'COOP', 'F6.S1.2', 'INTERNE', 'NUMERIQUE',
     date(2021, 9, 1),
     'Accord de coopération académique et scientifique avec l\'École Nationale Supérieure de Géologie de Nancy pour des échanges d\'étudiants et d\'enseignants.',
     'coopération, Lorraine, ENSG, France, échanges'),

    ('Convention de partenariat — ENSMG / Industries Chimiques du Sénégal (ICS)',
     'COOP', 'F6.S1.1', 'INTERNE', 'MIXTE',
     date(2023, 2, 28),
     'Convention de partenariat avec les ICS portant sur des stages industriels, des PFE et la recherche sur les procédés de transformation du phosphate.',
     'convention, ICS, phosphate, partenariat'),

    ('Contrat de stage — SALL Ibrahima, ICS Dakar, Juin-Août 2024',
     'SCO', 'F6.S2.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 5, 10),
     'Contrat de stage de fin d\'études d\'Ibrahima SALL au sein de la Direction des Mines des ICS. Durée : 3 mois.',
     'contrat stage, ICS, étudiant, 2024'),

    ('Rapport de stage — DIALLO Fatoumata, Teranga Gold, Été 2023',
     'SCO', 'F6.S2.2', 'INTERNE', 'NUMERIQUE',
     date(2023, 10, 20),
     'Rapport de stage industriel de Fatoumata DIALLO sur l\'exploitation aurifère de la mine de Sabodala.',
     'rapport stage, Teranga, Sabodala, exploitation'),

    # ── FINANCIER / RH ───────────────────────────────────────────────────────
    ('Budget prévisionnel ENSMG — Exercice 2024',
     'DAF', 'F7.S1.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2023, 12, 20),
     'Budget prévisionnel de l\'ENSMG pour l\'exercice 2024 : recettes (dotation État, ressources propres), dépenses (personnel, fonctionnement, investissement). Total : 2,8 Milliards FCFA.',
     'budget, prévisionnel, 2024, finances'),

    ('Rapport financier annuel — Exercice 2023',
     'DAF', 'F7.S1.1', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2024, 4, 30),
     'Rapport d\'exécution budgétaire de l\'exercice 2023 avec les tableaux de bord financiers et l\'analyse des écarts.',
     'rapport financier, 2023, budget, exécution'),

    ('Dossier du personnel — Pr. Awa TOURE, Enseignante-chercheuse Géologie',
     'DRH', 'F7.S2.1', 'SECRET', 'MIXTE',
     date(2018, 9, 1),
     'Dossier complet de la Pr. Awa TOURE : actes de recrutement, relevés de notes, publications, avancements, congés et évaluations.',
     'dossier personnel, enseignant, RH, géologie'),

    ('Dossier du personnel — Pr. Cheikh WADE, Enseignant-chercheur Mines',
     'DRH', 'F7.S2.1', 'SECRET', 'MIXTE',
     date(2015, 9, 1),
     'Dossier complet du Pr. Cheikh WADE : actes de recrutement, titres académiques, publications, CAMES, avancements.',
     'dossier personnel, enseignant, RH, mines'),

    ('Dossier du personnel — NDIAYE Fatou, Archiviste principale',
     'DRH', 'F7.S2.2', 'SECRET', 'MIXTE',
     date(2016, 3, 15),
     'Dossier de Fatou NDIAYE, Archiviste principale. Acte de recrutement, diplômes, avancements et évaluations annuelles.',
     'dossier personnel, administratif, RH, archives'),

    ('Arrêté de nomination — Nouveau Directeur de l\'ENSMG, 2022',
     'DRH', 'F7.S2.3', 'INTERNE', 'MIXTE',
     date(2022, 7, 1),
     'Arrêté ministériel portant nomination du Directeur de l\'ENSMG pour un mandat de 4 ans.',
     'arrêté, nomination, directeur, administration'),

    # ── PATRIMONIAL ──────────────────────────────────────────────────────────
    ('Archives fondatrices — Décret de création de l\'ENSMG, 1975',
     'DG', 'F8.S1.1', 'PUBLIC', 'MIXTE',
     date(1975, 6, 10),
     'Décret présidentiel n°75-1042 portant création de l\'École Nationale Supérieure des Mines et de la Géologie du Sénégal.',
     'décret, création, fondateur, 1975, patrimoine'),

    ('Photographies historiques — Cérémonie inauguration ENSMG, 1975',
     'DG', 'F8.S1.2', 'PUBLIC', 'MIXTE',
     date(1975, 10, 20),
     'Album photographique de la cérémonie officielle d\'inauguration de l\'ENSMG en présence des autorités. 48 photographies.',
     'photographies, inauguration, histoire, 1975'),

    ('Rapport historique — 40 ans de formation minière au Sénégal (1975-2015)',
     'DG', 'F8.S1.3', 'PUBLIC', 'NUMERIQUE',
     date(2015, 10, 15),
     'Publication commémorative retraçant 40 ans d\'histoire de la formation en mines et géologie au Sénégal : anciens étudiants, projets emblématiques, évolution des programmes.',
     'histoire, 40 ans, mines, géologie, publication'),

    # Quelques documents supplémentaires pour enrichir les tests
    ('Décision n°045/DG/2024 — Composition de la commission pédagogique',
     'DG', 'F1.S1.2', 'INTERNE', 'NUMERIQUE',
     date(2024, 2, 1),
     'Décision portant composition de la commission pédagogique paritaire pour l\'année académique 2023-2024.',
     'décision, commission, pédagogie'),

    ('Support de cours — Géologie du Sénégal, 3ème année Géologie',
     'DGE', 'F2.S1.4', 'INTERNE', 'NUMERIQUE',
     date(2023, 10, 1),
     'Polycopié du cours de Géologie du Sénégal dispensé en 3ème année. 180 pages, cartes et coupes géologiques incluses.',
     'cours, polycopié, géologie Sénégal, enseignement'),

    ('Rapport d\'analyses géophysiques — Prospection ZEM Kédougou 2021',
     'LAB', 'F5.S2.3', 'CONFIDENTIEL', 'NUMERIQUE',
     date(2021, 12, 10),
     'Rapport d\'interprétation des données de sismique réfraction et de résistivité électrique acquises sur la Zone d\'Extension Minière de Kédougou.',
     'géophysique, sismique, résistivité, Kédougou'),

    ('Convention ENSMG / UCAD — Programme d\'échange doctoral',
     'COOP', 'F6.S1.1', 'INTERNE', 'NUMERIQUE',
     date(2020, 11, 15),
     'Convention de collaboration entre l\'ENSMG et l\'Université Cheikh Anta Diop de Dakar pour des co-encadrements de thèses.',
     'convention, UCAD, thèses, doctorat, coopération'),

    ('Rapport de terrain — Cartographie géologique Casamance 2022',
     'DGE', 'F5.S1.1', 'INTERNE', 'NUMERIQUE',
     date(2022, 5, 30),
     'Rapport de la mission de cartographie géologique en Casamance. Caractérisation des formations sédimentaires tertiaires.',
     'terrain, Casamance, cartographie, sédimentaire'),

    ('Procès-verbal de jury — Soutenance thèse Dr. Ibrahima SOW, 2022',
     'DGE', 'F2.S2.2', 'PUBLIC', 'NUMERIQUE',
     date(2022, 12, 10),
     'PV de la soutenance de thèse de Dr. Ibrahima SOW, mention Très Honorable avec Félicitations.',
     'thèse, soutenance, jury, PV, doctorat'),

    ('Fiche de paie — Personnel ENSMG, Décembre 2023',
     'DRH', 'F7.S2.3', 'SECRET', 'NUMERIQUE',
     date(2023, 12, 31),
     'Récapitulatif des fiches de paie du personnel pour le mois de décembre 2023. 87 agents.',
     'paie, personnel, salaires, décembre 2023'),

    ('Rapport de stage — DIALLO Seydou, SENELEC, Été 2024',
     'SCO', 'F6.S2.2', 'INTERNE', 'NUMERIQUE',
     date(2024, 9, 15),
     'Rapport de stage de Seydou DIALLO effectué à la SENELEC sur l\'étude géotechnique des fondations de pylônes HTA.',
     'stage, SENELEC, géotechnique, fondations'),
]


class Command(BaseCommand):
    help = "Peuple la base de données avec des données de test réalistes. Réservé au développement."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Supprime toutes les données de test avant de recréer.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n⚠  PEUPLEMENT DE TEST — À n\'utiliser qu\'en développement !\n'))

        if options['reset']:
            self.stdout.write('   Suppression des données existantes...')
            BordereauElimination.objects.all().delete()
            BordereauVersement.objects.all().delete()
            MouvementDocument.objects.all().delete()
            Document.objects.all().delete()
            CustomUser.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.WARNING('   Données supprimées.\n'))

        with transaction.atomic():
            users    = self._creer_utilisateurs()
            docs     = self._creer_documents(users)
            self._creer_mouvements(docs, users)
            self._creer_bordereaux(docs, users)

        self.stdout.write(self.style.SUCCESS('\n✅  Base de données peuplée avec succès !'))
        self.stdout.write(f'   → {len(users)} utilisateurs, {len(docs)} documents, bordereaux créés.')
        self.stdout.write('   → Admin : http://127.0.0.1:8000/admin/')
        self.stdout.write('\n   Comptes de test (mot de passe : Test@1234) :')
        roles = ['ADMIN', 'ARCHIVISTE', 'DIRECTION', 'PERSONNEL', 'ENSEIGNANT']
        for u in users[:5]:
            self.stdout.write(f'   - {u.username:<20} ({u.get_role_display()})')

    # ── Utilisateurs ─────────────────────────────────────────────────────────

    def _creer_utilisateurs(self):
        self.stdout.write('[1/4] Création des utilisateurs...')
        departements = {d.code: d for d in Departement.objects.all()}
        crees = []
        mdp   = make_password('Test@1234')

        for username, prenom, nom, email, role, code_dept, tel in UTILISATEURS:
            if CustomUser.objects.filter(username=username).exists():
                u = CustomUser.objects.get(username=username)
                crees.append(u)
                continue
            u = CustomUser.objects.create(
                username    = username,
                first_name  = prenom,
                last_name   = nom,
                email       = email,
                role        = role,
                departement = departements.get(code_dept),
                telephone   = tel,
                password    = mdp,
                is_active   = True,
            )
            crees.append(u)
            self.stdout.write(f'    + {username:<20} [{role}] — {prenom} {nom}')

        self.stdout.write(self.style.SUCCESS(f'   {len(crees)} utilisateur(s) créé(s).\n'))
        return crees

    # ── Documents ─────────────────────────────────────────────────────────────

    def _creer_documents(self, users):
        self.stdout.write('[2/4] Création des documents d\'archives...')
        plans  = {p.code: p for p in PlanClassement.objects.all()}
        cats   = {c.code: c for c in CategorieDocument.objects.all()}
        depts  = {d.code: d for d in Departement.objects.all()}
        tdgs   = list(TableauGestion.objects.all())
        archivistes = [u for u in users if u.role == 'ARCHIVISTE']
        if not archivistes:
            archivistes = users[:1]

        statuts = ['COURANT', 'COURANT', 'COURANT', 'INTERMEDIAIRE', 'INTERMEDIAIRE', 'DEFINITIF', 'EN_ELIMINATION']
        crees = []

        for titre, dept_code, plan_code, conf, support, d_creation, desc, mots in DOCUMENTS:
            if Document.objects.filter(titre=titre).exists():
                crees.append(Document.objects.get(titre=titre))
                continue

            plan = plans.get(plan_code)
            if not plan:
                self.stdout.write(self.style.WARNING(f'    ⚠ Plan introuvable : {plan_code}'))
                continue

            # Catégorie déduite du plan
            cat_code = plan_code.split('.')[0].replace('F1', 'ADM').replace('F2', 'PED') \
                                               .replace('F3', 'SCI').replace('F4', 'GEO') \
                                               .replace('F5', 'TER').replace('F6', 'PAR') \
                                               .replace('F7', 'FRH').replace('F8', 'PAT')
            cat = plan.categorie or cats.get(cat_code)
            if not cat:
                continue

            dept = depts.get(dept_code)
            producteur = dept.nom if dept else dept_code
            statut = random.choice(statuts)
            tdg    = random.choice(tdgs) if tdgs else None
            createur = random.choice(archivistes)

            doc = Document(
                titre                = titre,
                producteur           = producteur,
                date_creation        = d_creation,
                date_reception       = d_creation + timedelta(days=random.randint(0, 5)),
                description          = desc,
                mots_cles            = mots,
                langue               = 'fr',
                categorie            = cat,
                plan_classement      = plan,
                statut               = statut,
                confidentialite      = conf,
                support              = support,
                localisation_physique= f'Bâtiment A, Salle 02, Étagère {random.randint(1, 8)}, Boîte {random.randint(1, 30)}' if support != 'NUMERIQUE' else '',
                tableau_gestion      = tdg,
                sort_final           = 'EN_ATTENTE',
                cree_par             = createur,
                modifie_par          = createur,
            )
            doc.save()
            crees.append(doc)
            self.stdout.write(f'    + [{doc.identifiant}] {titre[:55]}…' if len(titre) > 55 else f'    + [{doc.identifiant}] {titre}')

        self.stdout.write(self.style.SUCCESS(f'   {len(crees)} document(s) créé(s).\n'))
        return crees

    # ── Mouvements d'audit ────────────────────────────────────────────────────

    def _creer_mouvements(self, docs, users):
        self.stdout.write('[3/4] Génération des mouvements d\'audit...')
        total = 0
        for doc in docs:
            # Mouvement de création (toujours présent)
            MouvementDocument.objects.get_or_create(
                document    = doc,
                action      = 'CREATION',
                defaults={
                    'utilisateur': doc.cree_par,
                    'commentaire': 'Enregistrement initial du document.',
                    'adresse_ip' : '192.168.1.100',
                }
            )
            total += 1

            # 1 à 3 consultations aléatoires
            for _ in range(random.randint(1, 3)):
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'CONSULTATION',
                    utilisateur = random.choice(users),
                    commentaire = '',
                    adresse_ip  = f'192.168.1.{random.randint(101, 150)}',
                )
                total += 1

            # Modification si le document n'est pas trop récent
            if doc.statut in ('INTERMEDIAIRE', 'DEFINITIF') or random.random() > 0.6:
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'MODIFICATION',
                    utilisateur = doc.modifie_par,
                    commentaire = 'Mise à jour des métadonnées.',
                    details     = {'statut': {'avant': 'COURANT', 'apres': doc.statut}},
                    adresse_ip  = '192.168.1.100',
                )
                total += 1

            # Changement de statut si intermédiaire ou définitif
            if doc.statut in ('INTERMEDIAIRE', 'DEFINITIF', 'EN_ELIMINATION'):
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'CHANGEMENT_STATUT',
                    utilisateur = doc.cree_par,
                    commentaire = f'Passage au statut : {doc.get_statut_display()}',
                    details     = {'nouveau_statut': doc.statut},
                    adresse_ip  = '192.168.1.100',
                )
                total += 1

        self.stdout.write(self.style.SUCCESS(f'   {total} mouvement(s) d\'audit créé(s).\n'))

    # ── Bordereaux ────────────────────────────────────────────────────────────

    def _creer_bordereaux(self, docs, users):
        self.stdout.write('[4/4] Création des bordereaux...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE']
        direction   = [u for u in users if u.role == 'DIRECTION']
        if not archivistes:
            archivistes = users[:1]
        arch = archivistes[0]
        dir_ = direction[0] if direction else arch

        docs_definitifs    = [d for d in docs if d.statut == 'DEFINITIF']
        docs_elimination   = [d for d in docs if d.statut == 'EN_ELIMINATION']
        docs_intermediaires = [d for d in docs if d.statut == 'INTERMEDIAIRE']

        nb_v = 0
        nb_e = 0

        # ── Bordereaux de versement ──
        bordereaux_versement = [
            ('BV-2024-001', 'Scolarité',           'BROUILLON',     docs_definitifs[:3],   False, None, ''),
            ('BV-2024-002', 'Direction Générale',   'EN_VALIDATION', docs_definitifs[3:6],  False, None, ''),
            ('BV-2024-003', 'Département Géologie', 'VALIDE',        docs_definitifs[6:9],  True,  date(2024, 5, 15), 'Validé après vérification archivistique.'),
            ('BV-2024-004', 'Laboratoires',         'EXECUTE',       docs_definitifs[9:12], True,  date(2024, 3, 10), 'Versement effectué aux Archives nationales du Sénégal.'),
            ('BV-2023-012', 'DAF',                  'REJETE',        docs_intermediaires[:2], False, None, 'Documents ne remplissant pas les critères de versement.'),
        ]

        for num, service, statut, doc_list, valide, d_valid, obs in bordereaux_versement:
            if BordereauVersement.objects.filter(numero=num).exists():
                continue
            bv = BordereauVersement.objects.create(
                numero               = num,
                service_versant      = service,
                service_destinataire = 'Archives nationales du Sénégal',
                statut               = statut,
                observations         = obs,
                cree_par             = arch,
                valide_par           = dir_ if valide else None,
                date_validation      = d_valid,
            )
            bv.documents.set([d for d in doc_list if d])
            nb_v += 1
            self.stdout.write(f'    + Bordereau versement {num} ({statut}) — {len(doc_list)} doc(s)')

        # ── Bordereaux d'élimination ──
        bordereaux_elim = [
            ('BE-2024-001', 'Scolarité',    'BROUILLON',     docs_elimination[:3],  False, False, None, '', None),
            ('BE-2024-002', 'DAF',          'EN_VALIDATION', docs_elimination[3:5], False, False, None, '', None),
            ('BE-2024-003', 'DRH',          'VISA_OBTENU',   docs_intermediaires[2:4], False, True, date(2024, 4, 10), 'DAS/2024/0123', None),
            ('BE-2024-004', 'Scolarité',    'EXECUTE',       docs_elimination[:2],  False, True, date(2024, 2, 20), 'DAS/2024/0089', date(2024, 6, 15)),
            ('BE-2023-008', 'Direction',    'REJETE',        docs_intermediaires[:1], False, False, None, 'Documents présentant encore une valeur administrative.', None),
        ]

        for num, service, statut, doc_list, _, visa, d_visa, ref_visa, d_elim in bordereaux_elim:
            if BordereauElimination.objects.filter(numero=num).exists():
                continue
            be = BordereauElimination.objects.create(
                numero             = num,
                service_producteur = service,
                statut             = statut,
                motif              = 'DUA échue — sort final : Élimination selon tableau de gestion approuvé.',
                observations       = ref_visa,
                cree_par           = arch,
                visa_das           = visa,
                date_visa          = d_visa,
                reference_visa     = ref_visa,
                date_elimination   = d_elim,
            )
            be.documents.set([d for d in doc_list if d])
            nb_e += 1
            self.stdout.write(f'    + Bordereau élimination {num} ({statut}) — {len(doc_list)} doc(s)')

        self.stdout.write(self.style.SUCCESS(f'   {nb_v} bordereau(x) de versement, {nb_e} bordereau(x) d\'élimination créé(s).\n'))
