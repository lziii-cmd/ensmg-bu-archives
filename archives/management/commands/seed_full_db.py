"""
seed_full_db.py — Jeu de données de test COMPLET pour le système ENSMG Archives.

Couvre les 16 modèles applicatifs avec des scénarios réalistes et des cas limites :
  • DUA échues nécessitant une décision
  • Prêts en retard (date_retour_prevue dépassée)
  • Documents bloqués par rétention juridique (Legal Hold)
  • Documents en corbeille (soft-delete)
  • Tokens d'audit (valide, expiré, futur)
  • Dépôts en attente pour l'archiviste
  • Bordereaux dans tous les états du workflow
  • Vérifications d'intégrité SHA-256 (OK et échec simulé)
  • Notifications pour chaque rôle
  • Accès ABAC individuels

Usage :
    python manage.py seed_full_db             # peuplement sans écraser
    python manage.py seed_full_db --reset     # remet à zéro puis repeuple
    python manage.py seed_full_db --reset --quiet
"""

import hashlib
import random
import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from archives.models import (
    AccesDocument,
    AuditToken,
    BordereauElimination,
    BordereauVersement,
    BordereauEliminationCourrier,
    BordereauVersementCourrier,
    CategorieDocument,
    Courrier,
    DemandePret,
    DemandeRecherche,
    Document,
    DepotDocument,
    Message,
    MessageDestinataire,
    MouvementCourrier,
    MouvementDocument,
    Notification,
    PlanClassement,
    PretDocument,
    ProvenanceExterne,
    RetentionJuridique,
    TableauGestion,
    VerificationIntegrite,
)
from users.models import CustomUser, Departement

# ═══════════════════════════════════════════════════════════════════════════════
# RÉFÉRENTIEL UTILISATEURS
# ═══════════════════════════════════════════════════════════════════════════════

UTILISATEURS = [
    # (username,       prénom,          nom,          email,                         rôle,         dept,  tél)

    # ── Système ────────────────────────────────────────────────────────────────
    ('admin.sys',    'Amadou',        'DIALLO',     'a.diallo@ensmg.sn',          'ADMIN',      'INFO', '77 100 00 01'),

    # ── Direction ──────────────────────────────────────────────────────────────
    ('directeur',    'Ibrahima',      'SECK',       'i.seck@ensmg.sn',            'DIRECTION',  'DG',   '77 100 00 02'),
    ('csa',          'Rokhaya',       'MBAYE',      'r.mbaye@ensmg.sn',           'DIRECTION',  'DG',   '77 100 00 03'),

    # ── Service des Archives (2 agents seulement) ──────────────────────────────
    ('archiviste1',  'Fatou',         'NDIAYE',     'f.ndiaye@ensmg.sn',          'ARCHIVISTE', 'ARC',  '77 100 00 04'),
    ('archiviste2',  'Moussa',        'FALL',       'm.fall@ensmg.sn',            'ARCHIVISTE', 'ARC',  '77 100 00 05'),

    # ── Comptabilité Financière (4 agents) ────────────────────────────────────
    ('cf1',          'Babacar',       'THIAM',      'b.thiam@ensmg.sn',           'PERSONNEL',  'CF',   '77 100 00 06'),
    ('cf2',          'Ndèye',         'DIOP',       'n.diop@ensmg.sn',            'PERSONNEL',  'CF',   '77 100 00 07'),
    ('cf3',          'Coumba',        'NIANG',      'c.niang@ensmg.sn',           'PERSONNEL',  'CF',   '77 100 00 08'),
    ('cf4',          'Lamine',        'FAYE',       'l.faye@ensmg.sn',            'PERSONNEL',  'CF',   '77 100 00 09'),

    # ── Comptabilité des Matières (3 agents) ──────────────────────────────────
    ('cm1',          'Mariama',       'CISSE',      'm.cisse@ensmg.sn',           'PERSONNEL',  'CM',   '77 100 00 10'),
    ('cm2',          'Pape',          'LY',         'p.ly@ensmg.sn',              'PERSONNEL',  'CM',   '77 100 00 11'),
    ('cm3',          'Ibou',          'NDIAYE',     'ib.ndiaye@ensmg.sn',         'PERSONNEL',  'CM',   '77 100 00 12'),

    # ── Ressources Humaines (3 agents) ────────────────────────────────────────
    ('rh1',          'Marème',        'DIOUF',      'm.diouf@ensmg.sn',           'PERSONNEL',  'DRH',  '77 100 00 13'),
    ('rh2',          'Ndeye Khady',   'SOW',        'nk.sow@ensmg.sn',            'PERSONNEL',  'DRH',  '77 100 00 14'),
    ('rh3',          'Yaye',          'NIANG',      'y.niang@ensmg.sn',           'PERSONNEL',  'DRH',  '77 100 00 15'),

    # ── Scolarité (4 agents) ───────────────────────────────────────────────────
    ('sco1',         'Aminata',       'SARR',       'a.sarr@ensmg.sn',            'PERSONNEL',  'SCO',  '77 100 00 16'),
    ('sco2',         'Ousmane',       'GUEYE',      'o.gueye@ensmg.sn',           'PERSONNEL',  'SCO',  '77 100 00 17'),
    ('sco3',         'Abdoulaye',     'DIALLO',     'ab.diallo@ensmg.sn',         'PERSONNEL',  'SCO',  '77 100 00 18'),
    ('sco4',         'Khadim',        'BA',         'k.ba@ensmg.sn',              'PERSONNEL',  'SCO',  '77 100 00 19'),

    # ── Secrétariat (3 agents) ────────────────────────────────────────────────
    ('sec1',         'Aissatou',      'BARRY',      'a.barry@ensmg.sn',           'PERSONNEL',  'SEC',  '77 100 00 20'),
    ('sec2',         'Mamadou',       'BALDE',      'm.balde@ensmg.sn',           'PERSONNEL',  'SEC',  '77 100 00 21'),
    ('sec3',         'Souleymane',    'SOW',        's.sow@ensmg.sn',             'PERSONNEL',  'SEC',  '77 100 00 22'),
]

# ═══════════════════════════════════════════════════════════════════════════════
# RÉFÉRENTIEL DOCUMENTS
# (titre, dept_code, plan_code, confidentialite, support, date_creation,
#  description, mots_cles, statut, sort_final, dua_echue?)
# ═══════════════════════════════════════════════════════════════════════════════

DOCUMENTS = [

    # ── ADMINISTRATIF ─────────────────────────────────────────────────────────
    ('Statuts de l\'ENSMG — Version consolidée 2020',
     'DG','F1.S1.1','PUBLIC','MIXTE', date(2020,1,15),
     'Texte officiel des statuts de l\'École Nationale Supérieure des Mines et de la Géologie, version consolidée approuvée par le Conseil d\'administration.',
     'statuts, réglementation, institution, ENSMG',
     'DEFINITIF','CONSERVATION', False),

    ('Règlement intérieur de l\'ENSMG — 2022',
     'DG','F1.S1.2','INTERNE','NUMERIQUE', date(2022,3,10),
     'Règlement intérieur définissant les droits et obligations des personnels et étudiants.',
     'règlement, discipline, intérieur',
     'COURANT','EN_ATTENTE', False),

    ('Procès-verbal du Conseil d\'administration — T1 2024',
     'DG','F1.S2.1','INTERNE','NUMERIQUE', date(2024,2,20),
     'PV de la session ordinaire du premier trimestre 2024. Ordre du jour : budget, recrutements, partenariats.',
     'conseil administration, PV, 2024',
     'COURANT','EN_ATTENTE', False),

    ('Procès-verbal du Conseil d\'administration — T3 2023',
     'DG','F1.S2.1','INTERNE','NUMERIQUE', date(2023,9,12),
     'PV de la session ordinaire du troisième trimestre 2023.',
     'conseil administration, PV, 2023',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Procès-verbal du Conseil scientifique — Session annuelle 2023',
     'DG','F1.S2.2','INTERNE','NUMERIQUE', date(2023,11,5),
     'Session annuelle du Conseil scientifique : bilan des publications, accréditations et projets de recherche.',
     'conseil scientifique, PV, recherche',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Rapport annuel d\'activités ENSMG 2023',
     'DG','F1.S2.3','PUBLIC','NUMERIQUE', date(2024,3,30),
     'Rapport complet des activités pédagogiques, scientifiques et administratives de l\'ENSMG pour l\'année 2023.',
     'rapport annuel, activités, bilan, 2023',
     'COURANT','EN_ATTENTE', False),

    ('Note de service n°012/DG/2024 — Calendrier académique',
     'DG','F1.S1.3','INTERNE','NUMERIQUE', date(2024,1,8),
     'Note fixant le calendrier académique de l\'année 2023-2024 pour toutes les filières.',
     'calendrier, académique, note service',
     'COURANT','EN_ATTENTE', False),

    ('Courrier entrant — Ministère des Mines réf. MM/2024/0045',
     'DG','F1.S3.1','INTERNE','NUMERIQUE', date(2024,4,3),
     'Correspondance du Ministère des Mines relative à l\'organisation du concours national de recrutement.',
     'ministère, courrier, recrutement',
     'COURANT','EN_ATTENTE', False),

    # ── PÉDAGOGIQUE ───────────────────────────────────────────────────────────
    ('Programme de formation — Cycle Ingénieur Mines 2023-2024',
     'SCO','F2.S1.1','PUBLIC','NUMERIQUE', date(2023,9,1),
     'Programme officiel de la filière Génie Minier pour l\'année académique 2023-2024 : modules, crédits, enseignants responsables.',
     'programme, mines, ingénieur, formation',
     'COURANT','EN_ATTENTE', False),

    ('Programme de formation — Cycle Ingénieur Géologie 2023-2024',
     'SCO','F2.S1.2','PUBLIC','NUMERIQUE', date(2023,9,1),
     'Programme officiel de la filière Géologie pour l\'année académique 2023-2024.',
     'programme, géologie, ingénieur, formation',
     'COURANT','EN_ATTENTE', False),

    ('Programme de formation — Cycle Ingénieur Géotechnique 2023-2024',
     'SCO','F2.S1.3','PUBLIC','NUMERIQUE', date(2023,9,1),
     'Programme officiel de la filière Géotechnique pour l\'année académique 2023-2024.',
     'programme, géotechnique, ingénieur, formation',
     'COURANT','EN_ATTENTE', False),

    ('Sujets d\'examens de Géologie structurale — S5, Janvier 2024',
     'SCO','F2.S2.1','CONFIDENTIEL','NUMERIQUE', date(2024,1,15),
     'Ensemble des sujets d\'examens de la session de janvier 2024 pour le cours de Géologie structurale (S5).',
     'examens, géologie structurale, S5, 2024',
     'COURANT','ELIMINATION', False),

    ('Sujets d\'examens de Géomécanique — S6, Juin 2024',
     'SCO','F2.S2.1','CONFIDENTIEL','NUMERIQUE', date(2024,6,3),
     'Sujets de la session de juin 2024 pour le cours de Géomécanique (S6).',
     'examens, géomécanique, S6, 2024',
     'COURANT','ELIMINATION', False),

    ('Procès-verbal de jury — Promotion 2024, Filière Mines',
     'SCO','F2.S2.2','CONFIDENTIEL','NUMERIQUE', date(2024,7,18),
     'PV de délibération du jury de fin d\'année pour la promotion 2024 de la filière Génie Minier. 42 étudiants délibérés.',
     'jury, délibération, mines, promotion 2024',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Procès-verbal de jury — Promotion 2024, Filière Géologie',
     'SCO','F2.S2.2','CONFIDENTIEL','NUMERIQUE', date(2024,7,19),
     'PV de délibération du jury de fin d\'année pour la promotion 2024 de la filière Géologie. 38 étudiants délibérés.',
     'jury, délibération, géologie, promotion 2024',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Dossier académique — DIALLO Mamadou (Promo 2021)',
     'SCO','F2.S3.1','SECRET','MIXTE', date(2021,10,5),
     'Dossier complet d\'inscription, relevés de notes, convention de stage et attestations pour l\'étudiant Mamadou DIALLO.',
     'dossier étudiant, scolarité, Promo 2021',
     'DEFINITIF','CONSERVATION', False),

    ('Dossier académique — NDIAYE Aïssatou (Promo 2022)',
     'SCO','F2.S3.1','SECRET','MIXTE', date(2022,10,3),
     'Dossier complet pour l\'étudiante Aïssatou NDIAYE, promotion 2022, filière Géotechnique.',
     'dossier étudiant, scolarité, Promo 2022',
     'DEFINITIF','CONSERVATION', False),

    ('Diplôme d\'Ingénieur Mines — FALL Oumar, Promotion 2023',
     'SCO','F2.S3.2','SECRET','MIXTE', date(2023,12,15),
     'Diplôme original d\'Ingénieur en Génie Minier délivré à Oumar FALL, mention Très Bien.',
     'diplôme, ingénieur, mines, promotion 2023',
     'DEFINITIF','CONSERVATION', False),

    ('Dossier CAMES — Pr. Cheikh WADE, Maître de Conférences',
     'DRH','F2.S3.3','CONFIDENTIEL','MIXTE', date(2023,6,1),
     'Dossier complet de candidature au grade de Maître de Conférences soumis au CAMES pour le Pr. Cheikh WADE.',
     'CAMES, promotion, enseignant, mines',
     'COURANT','CONSERVATION', False),

    # ── SCIENTIFIQUE ──────────────────────────────────────────────────────────
    ('Rapport de recherche — Caractérisation minéralogique des gisements de phosphate de Thiès',
     'LAB','F3.S1.1','INTERNE','NUMERIQUE', date(2023,5,20),
     'Étude complète de la minéralogie des gisements de phosphate de la région de Thiès : analyses DRX, MEB et géochimiques.',
     'phosphate, Thiès, minéralogie, recherche',
     'COURANT','CONSERVATION', False),

    ('Article scientifique — Potentiel aurifère du Sénégal Oriental',
     'LAB','F3.S1.2','PUBLIC','NUMERIQUE', date(2023,8,10),
     'Article publié dans la revue African Journal of Earth Sciences sur le potentiel aurifère du Sénégal Oriental.',
     'or, Sénégal Oriental, aurifère, publication',
     'DEFINITIF','CONSERVATION', False),

    ('Thèse de doctorat — Modélisation 3D du gisement de fer de Falémé',
     'LAB','F3.S2.1','PUBLIC','NUMERIQUE', date(2022,12,8),
     'Thèse de doctorat présentée par Dr. Ibrahima SOW. Modélisation géostatistique du gisement de fer de la Falémé.',
     'thèse, fer, Falémé, modélisation, géostatistique',
     'DEFINITIF','CONSERVATION', False),

    ('Mémoire de master — Étude géotechnique du site de barrage de Sambangalou',
     'DGT','F3.S2.2','PUBLIC','NUMERIQUE', date(2023,9,15),
     'Mémoire de fin d\'études de master spécialisé en géotechnique. Étude des fondations et stabilité des pentes du barrage.',
     'mémoire, géotechnique, barrage, Sambangalou',
     'DEFINITIF','CONSERVATION', False),

    ('Rapport de fin d\'études — Évaluation environnementale mine de zircon de Diogo',
     'DM','F3.S2.3','PUBLIC','NUMERIQUE', date(2024,2,28),
     'Rapport de projet de fin d\'études sur l\'évaluation de l\'impact environnemental des opérations minières à Diogo.',
     'PFE, zircon, Diogo, environnement, mines',
     'COURANT','EN_ATTENTE', False),

    ('Données expérimentales — Essais résistance mécanique roches volcaniques 2023',
     'LAB','F3.S1.3','INTERNE','NUMERIQUE', date(2023,11,12),
     'Jeu de données des essais de compression simple et triaxiale réalisés sur des échantillons de roches volcaniques.',
     'données, essais, résistance, volcanisme',
     'INTERMEDIAIRE','ELIMINATION', True),  # DUA échue !

    # ── GÉOLOGIQUE ────────────────────────────────────────────────────────────
    ('Carte géologique du Sénégal Oriental — Kédougou 1/200 000',
     'CARTO','F4.S1.1','PUBLIC','MIXTE', date(2019,6,1),
     'Carte géologique à 1/200 000 de la région de Kédougou produite dans le cadre du projet de cartographie nationale.',
     'carte géologique, Kédougou, Birimien, 1/200000',
     'DEFINITIF','CONSERVATION', False),

    ('Carte géologique du Bassin sédimentaire côtier — 1/500 000',
     'CARTO','F4.S1.1','PUBLIC','MIXTE', date(2020,3,15),
     'Carte du bassin sédimentaire côtier sénégalais couvrant les formations tertiaires et quaternaires.',
     'carte géologique, bassin sédimentaire, côtier, 1/500000',
     'DEFINITIF','CONSERVATION', False),

    ('Carte des ressources minières du Sénégal — Édition 2021',
     'CARTO','F4.S1.2','PUBLIC','MIXTE', date(2021,7,20),
     'Carte de synthèse des ressources minérales du Sénégal : or, phosphate, fer, zircon, calcaire, attapulgite.',
     'ressources minières, carte, inventaire, Sénégal',
     'DEFINITIF','CONSERVATION', False),

    ('Carte géotechnique de Dakar — Zone Plateau 1/10 000',
     'CARTO','F4.S1.3','INTERNE','MIXTE', date(2022,5,10),
     'Carte géotechnique détaillée de la zone Plateau de Dakar : nature des sols, profondeur du substratum.',
     'carte géotechnique, Dakar, Plateau, construction',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Rapport de prospection minière — Zone Sabodala-Massawa',
     'DM','F4.S2.1','CONFIDENTIEL','NUMERIQUE', date(2021,11,30),
     'Rapport de campagne de prospection géochimique et géophysique dans la zone Sabodala-Massawa.',
     'prospection, Sabodala, or, géochimie, géophysique',
     'INTERMEDIAIRE','CONSERVATION', True),  # DUA échue !

    ('Logs de forages — Campagne 2022, Site Loulo-Gounkoto',
     'LAB','F4.S2.2','CONFIDENTIEL','MIXTE', date(2022,8,15),
     'Logs détaillés des 24 forages de la campagne 2022 sur le site Loulo-Gounkoto : lithologie, minéralogie, teneurs en or.',
     'forages, logs, Loulo, or, lithologie',
     'INTERMEDIAIRE','ELIMINATION', True),  # DUA échue — blocage légal !

    ('Étude de faisabilité — Exploitation gisement de calcaire de Bargny',
     'DM','F4.S2.3','CONFIDENTIEL','NUMERIQUE', date(2023,4,25),
     'Étude technico-économique complète de la faisabilité d\'exploitation industrielle du gisement calcaire de Bargny.',
     'faisabilité, calcaire, Bargny, ciment, exploitation',
     'COURANT','EN_ATTENTE', False),

    ('Base de données géochimiques — Région Kédougou-Kéniéba',
     'CARTO','F4.S3.1','INTERNE','NUMERIQUE', date(2022,12,1),
     'Base de données de 4 200 analyses géochimiques multi-élémentaires (50 éléments) des sédiments de rivière.',
     'géochimie, base de données, Kédougou, sédiments',
     'INTERMEDIAIRE','CONSERVATION', False),

    # ── TERRAIN ───────────────────────────────────────────────────────────────
    ('Carnet de terrain — Mission géologique Kédougou, Mars 2023',
     'DGE','F5.S1.1','INTERNE','PAPIER', date(2023,3,28),
     'Carnet de terrain de la mission de cartographie géologique dans la région de Kédougou. 15 jours de terrain, 3 géologues.',
     'carnet terrain, Kédougou, cartographie, mission',
     'COURANT','EN_ATTENTE', False),

    ('Fiches d\'échantillonnage — Campagne roches Thiès 2023',
     'LAB','F5.S1.2','INTERNE','MIXTE', date(2023,7,14),
     '145 fiches d\'échantillonnage de la campagne de collecte d\'échantillons de roches dans la région de Thiès.',
     'échantillonnage, Thiès, fiches, collecte',
     'COURANT','ELIMINATION', False),

    ('Rapport d\'analyses pétrographiques — Granites de Saraya',
     'LAB','F5.S2.1','INTERNE','NUMERIQUE', date(2023,10,5),
     'Analyses pétrographiques en lames minces de 42 échantillons de granite de la région de Saraya.',
     'pétrographie, granite, Saraya, lames minces',
     'COURANT','CONSERVATION', False),

    ('Rapport d\'analyses géochimiques — Indices aurifères Falémé 2022',
     'LAB','F5.S2.2','CONFIDENTIEL','NUMERIQUE', date(2022,9,20),
     'Résultats des analyses géochimiques (ICP-MS) sur 380 échantillons prélevés sur les indices aurifères de la Falémé.',
     'géochimie, or, Falémé, ICP-MS, analyses',
     'INTERMEDIAIRE','CONSERVATION', True),  # DUA échue !

    ('Rapport analyses géophysiques — Prospection ZEM Kédougou 2021',
     'LAB','F5.S2.3','CONFIDENTIEL','NUMERIQUE', date(2021,12,10),
     'Rapport d\'interprétation des données de sismique réfraction et de résistivité électrique acquises sur la ZEM de Kédougou.',
     'géophysique, sismique, résistivité, Kédougou',
     'INTERMEDIAIRE','ELIMINATION', True),  # DUA échue !

    # ── PARTENARIATS ──────────────────────────────────────────────────────────
    ('Convention de partenariat — ENSMG / Teranga Gold Corporation',
     'COOP','F6.S1.1','INTERNE','MIXTE', date(2022,6,15),
     'Convention cadre de collaboration entre l\'ENSMG et Teranga Gold pour des stages, des formations continues et des projets de recherche appliquée.',
     'convention, Teranga Gold, partenariat, mines',
     'COURANT','CONSERVATION', False),

    ('Accord de coopération — ENSMG / Université de Lorraine',
     'COOP','F6.S1.2','INTERNE','NUMERIQUE', date(2021,9,1),
     'Accord de coopération académique et scientifique avec l\'ENSG Nancy pour des échanges d\'étudiants et d\'enseignants.',
     'coopération, Lorraine, ENSG, France, échanges',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Convention de partenariat — ENSMG / ICS',
     'COOP','F6.S1.1','INTERNE','MIXTE', date(2023,2,28),
     'Convention de partenariat avec les ICS portant sur des stages industriels, des PFE et la recherche sur les procédés de transformation du phosphate.',
     'convention, ICS, phosphate, partenariat',
     'COURANT','CONSERVATION', False),

    ('Contrat de stage — SALL Ibrahima, ICS Dakar, Juin-Août 2024',
     'SCO','F6.S2.1','CONFIDENTIEL','NUMERIQUE', date(2024,5,10),
     'Contrat de stage de fin d\'études d\'Ibrahima SALL au sein de la Direction des Mines des ICS. Durée : 3 mois.',
     'contrat stage, ICS, étudiant, 2024',
     'COURANT','EN_ATTENTE', False),

    ('Rapport de stage — DIALLO Fatoumata, Teranga Gold, Été 2023',
     'SCO','F6.S2.2','INTERNE','NUMERIQUE', date(2023,10,20),
     'Rapport de stage industriel de Fatoumata DIALLO sur l\'exploitation aurifère de la mine de Sabodala.',
     'rapport stage, Teranga, Sabodala, exploitation',
     'COURANT','EN_ATTENTE', False),

    ('Convention ENSMG / UCAD — Programme d\'échange doctoral',
     'COOP','F6.S1.1','INTERNE','NUMERIQUE', date(2020,11,15),
     'Convention de collaboration entre l\'ENSMG et l\'Université Cheikh Anta Diop de Dakar pour des co-encadrements de thèses.',
     'convention, UCAD, thèses, doctorat, coopération',
     'INTERMEDIAIRE','CONSERVATION', False),

    # ── FINANCIER / RH ────────────────────────────────────────────────────────
    ('Budget prévisionnel ENSMG — Exercice 2024',
     'DAF','F7.S1.1','CONFIDENTIEL','NUMERIQUE', date(2023,12,20),
     'Budget prévisionnel de l\'ENSMG pour l\'exercice 2024. Total : 2,8 Milliards FCFA.',
     'budget, prévisionnel, 2024, finances',
     'COURANT','EN_ATTENTE', False),

    ('Rapport financier annuel — Exercice 2023',
     'DAF','F7.S1.1','CONFIDENTIEL','NUMERIQUE', date(2024,4,30),
     'Rapport d\'exécution budgétaire de l\'exercice 2023 avec les tableaux de bord financiers et l\'analyse des écarts.',
     'rapport financier, 2023, budget, exécution',
     'COURANT','EN_ATTENTE', False),

    ('Rapport financier annuel — Exercice 2020',
     'DAF','F7.S1.1','CONFIDENTIEL','NUMERIQUE', date(2021,4,30),
     'Rapport d\'exécution budgétaire de l\'exercice 2020.',
     'rapport financier, 2020, budget, exécution',
     'DEFINITIF','ELIMINATION', True),  # DUA échue !

    ('Dossier du personnel — Pr. Awa TOURE, Enseignante-chercheuse Géologie',
     'DRH','F7.S2.1','SECRET','MIXTE', date(2018,9,1),
     'Dossier complet de la Pr. Awa TOURE : actes de recrutement, relevés de notes, publications, avancements, congés.',
     'dossier personnel, enseignant, RH, géologie',
     'COURANT','CONSERVATION', False),

    ('Dossier du personnel — Pr. Cheikh WADE, Enseignant-chercheur Mines',
     'DRH','F7.S2.1','SECRET','MIXTE', date(2015,9,1),
     'Dossier complet du Pr. Cheikh WADE : actes de recrutement, titres académiques, publications, CAMES, avancements.',
     'dossier personnel, enseignant, RH, mines',
     'COURANT','CONSERVATION', False),

    ('Dossier du personnel — NDIAYE Fatou, Archiviste principale',
     'DRH','F7.S2.2','SECRET','MIXTE', date(2016,3,15),
     'Dossier de Fatou NDIAYE, Archiviste principale. Acte de recrutement, diplômes, avancements et évaluations annuelles.',
     'dossier personnel, administratif, RH, archives',
     'COURANT','CONSERVATION', False),

    ('Arrêté de nomination — Nouveau Directeur de l\'ENSMG, 2022',
     'DRH','F7.S2.3','INTERNE','MIXTE', date(2022,7,1),
     'Arrêté ministériel portant nomination du Directeur de l\'ENSMG pour un mandat de 4 ans.',
     'arrêté, nomination, directeur, administration',
     'COURANT','CONSERVATION', False),

    ('Fiche de paie — Personnel ENSMG, Décembre 2023',
     'DRH','F7.S2.3','SECRET','NUMERIQUE', date(2023,12,31),
     'Récapitulatif des fiches de paie du personnel pour le mois de décembre 2023. 87 agents.',
     'paie, personnel, salaires, décembre 2023',
     'COURANT','ELIMINATION', False),

    # ── PATRIMONIAL ───────────────────────────────────────────────────────────
    ('Archives fondatrices — Décret de création de l\'ENSMG, 1975',
     'DG','F8.S1.1','PUBLIC','MIXTE', date(1975,6,10),
     'Décret présidentiel n°75-1042 portant création de l\'École Nationale Supérieure des Mines et de la Géologie.',
     'décret, création, fondateur, 1975, patrimoine',
     'DEFINITIF','CONSERVATION', False),

    ('Photographies historiques — Cérémonie inauguration ENSMG, 1975',
     'DG','F8.S1.2','PUBLIC','MIXTE', date(1975,10,20),
     'Album photographique de la cérémonie officielle d\'inauguration de l\'ENSMG. 48 photographies.',
     'photographies, inauguration, histoire, 1975',
     'DEFINITIF','CONSERVATION', False),

    ('Rapport historique — 40 ans de formation minière au Sénégal (1975-2015)',
     'DG','F8.S1.3','PUBLIC','NUMERIQUE', date(2015,10,15),
     'Publication commémorative retraçant 40 ans d\'histoire de la formation en mines et géologie au Sénégal.',
     'histoire, 40 ans, mines, géologie, publication',
     'DEFINITIF','CONSERVATION', False),

    # ── Documents variés pour enrichir les scenarios ──────────────────────────
    ('Support de cours — Géologie du Sénégal, 3ème année',
     'DGE','F2.S1.4','INTERNE','NUMERIQUE', date(2023,10,1),
     'Polycopié du cours de Géologie du Sénégal dispensé en 3ème année. 180 pages, cartes et coupes incluses.',
     'cours, polycopié, géologie Sénégal, enseignement',
     'COURANT','EN_ATTENTE', False),

    ('Rapport de terrain — Cartographie géologique Casamance 2022',
     'DGE','F5.S1.1','INTERNE','NUMERIQUE', date(2022,5,30),
     'Rapport de la mission de cartographie géologique en Casamance. Caractérisation des formations sédimentaires tertiaires.',
     'terrain, Casamance, cartographie, sédimentaire',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('PV de jury — Soutenance thèse Dr. Ibrahima SOW, 2022',
     'DGE','F2.S2.2','PUBLIC','NUMERIQUE', date(2022,12,10),
     'PV de la soutenance de thèse de Dr. Ibrahima SOW, mention Très Honorable avec Félicitations.',
     'thèse, soutenance, jury, PV, doctorat',
     'DEFINITIF','CONSERVATION', False),

    ('Rapport de stage — DIALLO Seydou, SENELEC, Été 2024',
     'SCO','F6.S2.2','INTERNE','NUMERIQUE', date(2024,9,15),
     'Rapport de stage de Seydou DIALLO effectué à la SENELEC sur l\'étude géotechnique des fondations de pylônes HTA.',
     'stage, SENELEC, géotechnique, fondations',
     'COURANT','EN_ATTENTE', False),

    ('Décision n°045/DG/2024 — Commission pédagogique',
     'DG','F1.S1.2','INTERNE','NUMERIQUE', date(2024,2,1),
     'Décision portant composition de la commission pédagogique paritaire pour l\'année académique 2023-2024.',
     'décision, commission, pédagogie',
     'COURANT','EN_ATTENTE', False),

    ('Procès-verbal CA — Session extraordinaire Budget 2022',
     'DG','F1.S2.1','INTERNE','NUMERIQUE', date(2022,11,10),
     'Session extraordinaire du Conseil d\'Administration convoquée pour rectification budgétaire urgente.',
     'conseil administration, PV, budget rectificatif, 2022',
     'INTERMEDIAIRE','CONSERVATION', False),

    ('Rapport annuel activités ENSMG 2021',
     'DG','F1.S2.3','PUBLIC','NUMERIQUE', date(2022,3,1),
     'Rapport annuel des activités de l\'ENSMG pour l\'exercice 2021.',
     'rapport annuel, 2021, bilan',
     'DEFINITIF','CONSERVATION', False),

    # Docs à mettre en corbeille
    ('Brouillon — Note interne communication 2023 (CORBEILLE)',
     'DG','F1.S1.3','INTERNE','NUMERIQUE', date(2023,5,1),
     'Brouillon non finalisé d\'une note de communication interne. À supprimer.',
     'brouillon, note, communication',
     'COURANT','EN_ATTENTE', False),

    ('Fichier de test — Import CSV catalogage 2024 (CORBEILLE)',
     'BIB','F2.S1.1','INTERNE','NUMERIQUE', date(2024,1,15),
     'Fichier de test utilisé lors de l\'import CSV du catalogage. Données factices.',
     'test, import, CSV, catalogage',
     'COURANT','EN_ATTENTE', False),
]

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = "Peuple INTÉGRALEMENT la base de données avec des données de test réalistes — tous les 16 modèles couverts."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Efface toutes les données (hors superuser) avant de recréer.')
        parser.add_argument('--quiet', action='store_true',
                            help='Supprime les logs détaillés.')

    def log(self, msg, style=None):
        if not self.quiet:
            if style:
                self.stdout.write(style(msg))
            else:
                self.stdout.write(msg)

    def handle(self, *args, **options):
        self.quiet = options['quiet']
        self.stdout.write(self.style.WARNING(
            '\n╔══════════════════════════════════════════════╗\n'
            '║  SEED FULL DB — ENSMG Archives System        ║\n'
            '║  ⚠  DÉVELOPPEMENT / TEST UNIQUEMENT          ║\n'
            '╚══════════════════════════════════════════════╝\n'
        ))

        if options['reset']:
            self._reset_db()

        with transaction.atomic():
            users   = self._creer_utilisateurs()
            docs    = self._creer_documents(users)
            self._creer_depots(users, docs)
            self._creer_demandes_prets(users, docs)
            self._creer_prêts(users, docs)
            self._creer_recherches(users, docs)
            self._creer_bordereaux(users, docs)
            self._creer_retentions(users, docs)
            self._creer_acces_abac(users, docs)
            self._creer_audit_tokens(users, docs)
            self._creer_verifications_integrite(users, docs)
            self._creer_mouvements(users, docs)
            self._creer_notifications(users, docs)
            self._mettre_en_corbeille(docs, users)
            courriers = self._creer_courriers(users)
            self._creer_bordereaux_courriers(courriers, users)
            self._creer_messages(users, docs)

        self._afficher_recap(users, docs)

    # ── 0. RESET ──────────────────────────────────────────────────────────────

    def _reset_db(self):
        self.stdout.write('   Remise à zéro de la base...')
        models_order = [
            VerificationIntegrite, RetentionJuridique, AuditToken,
            AccesDocument, PretDocument, DemandePret, DemandeRecherche,
            Notification, DepotDocument, MouvementDocument,
            BordereauElimination, BordereauVersement,
            MessageDestinataire, Message,
            MouvementCourrier,
            BordereauEliminationCourrier, BordereauVersementCourrier,
            Courrier,
            Document, CustomUser,
        ]
        for m in models_order:
            if m == CustomUser:
                m.objects.filter(is_superuser=False).delete()
            else:
                m.objects.all().delete()
        self.stdout.write(self.style.WARNING('   ✓ Base réinitialisée.\n'))

    # ── 1. UTILISATEURS ───────────────────────────────────────────────────────

    def _creer_utilisateurs(self):
        self.stdout.write('[1/13] Utilisateurs...')
        departements = {d.code: d for d in Departement.objects.all()}
        mdp  = make_password('passer01')
        crees = []
        for username, prenom, nom, email, role, dept_code, tel in UTILISATEURS:
            u, created = CustomUser.objects.get_or_create(
                username=username,
                defaults=dict(
                    first_name  = prenom,
                    last_name   = nom,
                    email       = email,
                    role        = role,
                    departement = departements.get(dept_code),
                    telephone   = tel,
                    password    = mdp,
                    is_active   = True,
                )
            )
            crees.append(u)
            if created:
                self.log(f'    + {username:<22} [{role}]')
        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(crees)} utilisateur(s).\n'))
        return crees

    # ── 2. DOCUMENTS ──────────────────────────────────────────────────────────

    def _creer_documents(self, users):
        self.stdout.write('[2/13] Documents d\'archives...')
        plans       = {p.code: p for p in PlanClassement.objects.select_related('categorie').all()}
        tdgs        = list(TableauGestion.objects.all())
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        depts       = {d.code: d for d in Departement.objects.all()}
        crees       = []

        cat_map = {
            'F1': 'ADM', 'F2': 'PED', 'F3': 'SCI', 'F4': 'GEO',
            'F5': 'TER', 'F6': 'PAR', 'F7': 'FRH', 'F8': 'PAT',
        }
        cats = {c.code: c for c in CategorieDocument.objects.all()}

        for titre, dept_code, plan_code, conf, support, d_creation, desc, mots, statut, sort_final, dua_echue in DOCUMENTS:
            if Document.objects.filter(titre=titre).exists():
                crees.append(Document.objects.get(titre=titre))
                continue

            plan = plans.get(plan_code)
            if not plan:
                self.log(self.style.WARNING(f'    ⚠ Plan introuvable : {plan_code} — ignoré'))
                continue

            pref = plan_code.split('.')[0]
            cat  = plan.categorie or cats.get(cat_map.get(pref, ''))
            if not cat:
                continue

            dept      = depts.get(dept_code)
            producteur = dept.nom if dept else dept_code
            arch       = random.choice(archivistes)
            tdg        = random.choice(tdgs) if tdgs else None

            date_fin_dua = None
            if dua_echue:
                date_fin_dua = d_creation + timedelta(days=random.randint(365*2, 365*3))
                # S'assurer qu'elle est bien dans le passé
                if date_fin_dua > date.today():
                    date_fin_dua = date.today() - timedelta(days=random.randint(30, 365))
            elif tdg and tdg.duree_totale and d_creation:
                fin = d_creation + timedelta(days=tdg.duree_totale * 365)
                if fin > date.today():
                    date_fin_dua = fin

            doc = Document(
                titre                 = titre,
                producteur            = producteur,
                date_creation         = d_creation,
                date_reception        = d_creation + timedelta(days=random.randint(0, 5)),
                description           = desc,
                mots_cles             = mots,
                langue                = 'fr',
                categorie             = cat,
                plan_classement       = plan,
                statut                = statut,
                confidentialite       = conf,
                support               = support,
                localisation_physique = (
                    f'Bâtiment A, Salle 02, Étagère {random.randint(1,8)}, Boîte {random.randint(1,30)}'
                    if support != 'NUMERIQUE' else ''
                ),
                tableau_gestion  = tdg,
                sort_final       = sort_final,
                date_fin_dua     = date_fin_dua,
                cree_par         = arch,
                modifie_par      = arch,
            )
            doc.save()
            crees.append(doc)
            self.log(f'    + [{doc.identifiant}] {titre[:60]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(crees)} document(s).\n'))
        return crees

    # ── 3. DÉPÔTS ─────────────────────────────────────────────────────────────

    def _creer_depots(self, users, docs):
        """
        Crée des dépôts de documents représentatifs de l'activité ENSMG.
        Les dépôts ARCHIVE sont liés à un Document existant via document_archive
        et leur date_depot est mise à jour pour simuler plusieurs exercices
        (2023, 2024, 2025) — nécessaire pour tester le générateur de BV.
        """
        self.stdout.write('[3/13] Dépôts de documents (workflow agent → archiviste)...')
        archivistes  = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        agents       = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT')]
        cats         = list(CategorieDocument.objects.all())
        arch         = archivistes[0]
        arch2        = archivistes[1] if len(archivistes) > 1 else arch
        provenances  = list(ProvenanceExterne.objects.filter(actif=True)[:5])

        # Pool de docs disponibles pour être liés comme document_archive
        docs_libres = [d for d in docs if d.deleted_at is None and not hasattr(d, '_depot_pris')]
        doc_pool    = list(docs_libres)
        # Marquer les docs déjà liés à un dépôt existant
        deja_lies   = set(
            DepotDocument.objects.filter(document_archive__isnull=False)
            .values_list('document_archive_id', flat=True)
        )

        def _next_doc():
            """Retourne le prochain document libre du pool."""
            while doc_pool:
                d = doc_pool.pop(0)
                if d.pk not in deja_lies:
                    deja_lies.add(d.pk)
                    return d
            return None

        # (agent_idx, titre, cat_idx, statut, ext, motif_rejet, jours_depuis_aujourd_hui)
        # jours_depuis_aujourd_hui : décalage en jours pour simuler la date_depot passée
        DEPOTS = [
            # ── EN ATTENTE (travaux en cours de l'archiviste) ──────────────────
            (0,  'Rapport de mission terrain Kédougou — Mars 2025',             0, 'EN_ATTENTE', False, '',  3),
            (1,  'Convention de stage DIALLO Samba — ICS, 2025',                1, 'EN_ATTENTE', False, '',  5),
            (2,  'PV de réunion département Mines — Janvier 2025',              2, 'EN_ATTENTE', True,  '',  7),
            (3,  'Résultats examens partiels Géologie S5 — Nov 2024',           3, 'EN_ATTENTE', False, '', 15),
            (4,  'Budget prévisionnel DAF — Exercice 2026',                     4, 'EN_ATTENTE', False, '',  2),
            (5,  'Rapport de travaux — Extension laboratoire géochimie 2025',   1, 'EN_ATTENTE', False, '', 10),
            (6,  'Procès-verbal de remise de matériel — PETROSEN/ENSMG',        2, 'EN_ATTENTE', True,  '', 12),
            (7,  'Acte de recrutement — Vacataire Pr. SOW Alioune 2025',        3, 'EN_ATTENTE', False, '',  8),
            (8,  'Rapport de prospection — Région de Tambacounda 2025',         0, 'EN_ATTENTE', False, '',  4),

            # ── ARCHIVE exercice 2025 (janvier → mars = date_depot récente) ───
            (0,  'Carnet de terrain — Mission Casamance Janv. 2025',            0, 'ARCHIVE', False, '', 45),
            (1,  "Note d'information — Recrutement vacataires Fév. 2025",       1, 'ARCHIVE', False, '', 38),
            (2,  'Rapport de stage — BARRY Aissatou, PETROSEN, Janv. 2025',     2, 'ARCHIVE', True,  '', 50),
            (3,  'Accord de stage — FALL Ousmane, DGM, Mars 2025',              3, 'ARCHIVE', False, '', 20),
            (4,  "Fiches d'évaluation enseignants S1 2025",                     4, 'ARCHIVE', False, '', 30),
            (5,  'Planning des soutenances de PFE — Fév. 2025',                 0, 'ARCHIVE', False, '', 35),
            (6,  'Rapport annuel Laboratoire Géochimie — 2024',                 1, 'ARCHIVE', False, '', 28),
            (7,  'Convention ENSMG / OMVS — Avenant n°2, Janv. 2025',          2, 'ARCHIVE', True,  '', 42),
            (8,  'Bilan financier trimestriel DAF — T1 2025',                   3, 'ARCHIVE', False, '', 25),
            (9,  'Procès-verbal Conseil de direction — Fév. 2025',              4, 'ARCHIVE', False, '', 22),
            (0,  'Rapport de stage — LY Pape, SENHUILE, Janv. 2025',           0, 'ARCHIVE', False, '', 55),
            (1,  'Contrat de prestations informatiques — Mars 2025',            1, 'ARCHIVE', False, '', 18),
            (2,  'Fiche de poste — Ingénieur géologue, Mars 2025',              2, 'ARCHIVE', False, '', 15),

            # ── ARCHIVE exercice 2024 (date simulée à ~300-400 jours passés) ──
            (3,  'Rapport de mission — Étude gisement phosphate Thiès 2024',    3, 'ARCHIVE', False, '', 310),
            (4,  'PV jury de soutenance — Promotion 2024',                      4, 'ARCHIVE', False, '', 285),
            (5,  'Rapport annuel SCO — Exercice 2024',                          0, 'ARCHIVE', False, '', 260),
            (6,  'Contrat partenariat UCAD-ENSMG — 2024',                      1, 'ARCHIVE', True,  '', 330),
            (7,  'Bilan inventaire laboratoire — Oct. 2024',                    2, 'ARCHIVE', False, '', 155),
            (8,  'Rapport de stage collectif Géologie — Août 2024',             3, 'ARCHIVE', False, '', 195),
            (9,  "Note de service — Calendrier académique 2024/2025",           4, 'ARCHIVE', False, '', 220),
            (0,  'Étude cartographique — Bassin sédimentaire Casamance 2024',   0, 'ARCHIVE', True,  '', 240),
            (1,  'Rapport de prospection géophysique — Région Matam 2024',      1, 'ARCHIVE', False, '', 170),
            (2,  'Convention de coopération ENSMG/BRGM — 2024',                2, 'ARCHIVE', True,  '', 300),
            (3,  'Budget exécuté DAF — Exercice 2024',                         3, 'ARCHIVE', False, '', 350),
            (4,  'Catalogue des thèses et mémoires ENSMG — 2024',              4, 'ARCHIVE', False, '', 200),

            # ── ARCHIVE exercice 2023 (date simulée à ~500-700 jours passés) ──
            (5,  'Rapport annuel direction — Exercice 2023',                    0, 'ARCHIVE', False, '', 550),
            (6,  'Convention ENSMG/DGM — Cartographie minière 2023',           1, 'ARCHIVE', True,  '', 520),
            (7,  'PV Conseil scientifique — Session ordinaire Déc. 2023',       2, 'ARCHIVE', False, '', 490),
            (8,  'Rapport géologique — Zone aurifère Kédougou 2023',            3, 'ARCHIVE', False, '', 600),
            (9,  'Bilan RH — Exercice 2023',                                    4, 'ARCHIVE', False, '', 650),
            (0,  'Budget initial DAF — Exercice 2023',                         0, 'ARCHIVE', False, '', 680),

            # ── REJETÉS (cas d'erreur réels) ──────────────────────────────────
            (0, 'Note de service — Fermeture 24/12/2024 (scan illisible)',       3, 'REJETE',
             False, 'Document illisible — numériser en 300 DPI minimum.', 90),
            (1, 'Brouillon PFE étudiant DIALLO — non finalisé',                 4, 'REJETE',
             False, 'Document non finalisé. Déposer la version signée après soutenance.', 75),
            (2, 'Contrat prestataire 2023 — version incomplète',                0, 'REJETE',
             False, 'Pages 3 et 4 manquantes. Joindre le document complet.', 60),
        ]

        nb = 0
        for i, (ag_idx, titre, cat_idx, statut, ext, motif_rejet, jours) in enumerate(DEPOTS):
            if DepotDocument.objects.filter(titre=titre).exists():
                nb += 1
                continue
            agent = agents[ag_idx % len(agents)]
            cat   = cats[cat_idx % len(cats)] if cats else None

            # Contenu minimal simulé
            contenu     = f"[FICHIER TEST — SEED] {titre}\n\nDépartement : {agent.departement}\nDate : {date.today() - timedelta(days=jours)}\n".encode('utf-8')
            nom_fichier = f"depot_{i+1:03d}_{statut.lower()}.pdf"

            depot = DepotDocument(
                agent              = agent,
                titre              = titre,
                date_reception     = date.today() - timedelta(days=jours + 2),
                categorie          = cat,
                description        = f"Document de test — {titre}",
                mots_cles          = "seed, test, archives, ensmg",
                statut             = statut,
                provenance_interne = not ext,
                provenance_externe = random.choice(provenances) if ext and provenances else None,
                motif_rejet        = motif_rejet,
            )
            depot.fichier.save(nom_fichier, ContentFile(contenu), save=False)

            if statut == 'ARCHIVE':
                depot.traite_par      = arch
                depot.date_traitement = timezone.now() - timedelta(days=max(1, jours - 5))
                # Lier à un document existant libre
                doc_lié = _next_doc()
                if doc_lié:
                    depot.document_archive = doc_lié
            elif statut == 'REJETE':
                depot.traite_par      = arch2
                depot.date_traitement = timezone.now() - timedelta(days=max(1, jours - 3))

            depot.save()

            # Corriger la date_depot (auto_now_add=True → update() direct SQL)
            date_depot_cible = timezone.now() - timedelta(days=jours)
            DepotDocument.objects.filter(pk=depot.pk).update(date_depot=date_depot_cible)

            nb += 1
            dept_nom = agent.departement.nom if agent.departement else '?'
            self.log(f'    + [{statut}] [{dept_nom[:20]}] {titre[:55]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} dépôt(s).\n'))

    # ── 4. DEMANDES DE PRÊT ───────────────────────────────────────────────────

    def _creer_demandes_prets(self, users, docs):
        self.stdout.write('[4/13] Demandes de prêt / accès numérique...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        demandeurs  = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT', 'DIRECTION')]
        docs_phys   = [d for d in docs if d.support in ('PAPIER','MIXTE') and d.deleted_at is None]
        docs_num    = [d for d in docs if d.support in ('NUMERIQUE','MIXTE') and d.deleted_at is None]
        arch        = archivistes[0]

        DEMANDES = [
            # (demandeur_idx, doc_idx, type, motif, statut, motif_refus)
            (0, 0,  'PHYSIQUE',  'Besoin pour rédiger le rapport annuel du service.',              'EN_ATTENTE', ''),
            (1, 1,  'NUMERIQUE', 'Consultation dans le cadre d\'une formation continue.',          'EN_ATTENTE', ''),
            (2, 2,  'PHYSIQUE',  'Vérification de signature pour dossier administratif.',         'EN_ATTENTE', ''),
            (3, 3,  'NUMERIQUE', 'Référence pour préparation d\'un cours sur les statuts.',       'EN_ATTENTE', ''),
            (4, 4,  'PHYSIQUE',  'Consultation PV CA pour compte-rendu à la direction.',          'ACCORDEE',   ''),
            (5, 5,  'NUMERIQUE', 'Recherche documentaire pour projet de fin d\'études.',          'ACCORDEE',   ''),
            (6, 6,  'PHYSIQUE',  'Besoin de la note de service pour dossier RH.',                 'ACCORDEE',   ''),
            (0, 7,  'NUMERIQUE', 'Consultation de la carte géologique pour travaux pratiques.',   'ACCORDEE',   ''),
            (1, 8,  'PHYSIQUE',  'Archivage complémentaire d\'un dossier de recherche.',          'REFUSEE',    'Document en cours de traitement — disponible dans 5 jours ouvrables.'),
            (2, 9,  'NUMERIQUE', 'Copie pour diffusion au comité pédagogique.',                   'REFUSEE',    'Niveau de confidentialité incompatible avec le profil demandeur.'),
            (3, 10, 'PHYSIQUE',  'Consultation pour mise à jour du programme de formation.',      'CLOTUREE',   ''),
            (4, 11, 'NUMERIQUE', 'Accès pour projet de recherche collaborative.',                 'CLOTUREE',   ''),
            (5, 12, 'PHYSIQUE',  'Consultation pour préparer la session de soutenances.',         'EN_ATTENTE', ''),
            (6, 13, 'NUMERIQUE', 'Analyse comparative avec un autre rapport de recherche.',       'EN_ATTENTE', ''),
            (0, 14, 'PHYSIQUE',  'Consultation de la carte pour cartographie régionale.',         'ACCORDEE',   ''),
        ]

        nb = 0
        for dem_idx, doc_idx, type_dem, motif, statut, motif_refus in DEMANDES:
            demandeur = demandeurs[dem_idx % len(demandeurs)]
            pool      = docs_phys if type_dem == 'PHYSIQUE' else docs_num
            if not pool:
                continue
            doc = pool[doc_idx % len(pool)]

            if DemandePret.objects.filter(demandeur=demandeur, document=doc, type_demande=type_dem).exists():
                nb += 1
                continue

            dp = DemandePret(
                demandeur    = demandeur,
                document     = doc,
                type_demande = type_dem,
                motif        = motif,
                statut       = statut,
                motif_refus  = motif_refus,
                duree_acces_heures = 24,
            )
            if statut in ('ACCORDEE', 'REFUSEE', 'CLOTUREE'):
                dp.traite_par      = arch
                dp.date_traitement = timezone.now() - timedelta(days=random.randint(1, 15))
            dp.save()
            nb += 1
            self.log(f'    + [{statut}] {demandeur.username} → {doc.identifiant[:20]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} demande(s) de prêt.\n'))

    # ── 5. PRÊTS PHYSIQUES ────────────────────────────────────────────────────

    def _creer_prêts(self, users, docs):
        self.stdout.write('[5/13] Prêts de documents physiques...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        emprunteurs = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT', 'DIRECTION')]
        docs_phys   = [d for d in docs if d.support in ('PAPIER','MIXTE') and d.deleted_at is None]
        arch        = archivistes[0]
        nb          = 0

        PRETS = [
            # (emprunteur_idx, doc_idx, delta_debut, duree_j, statut)
            (0, 0, -5,  14, 'EN_COURS'),   # Prêt en cours normal
            (1, 1, -20, 14, 'EN_RETARD'),  # Prêt en retard !
            (2, 2, -35, 14, 'EN_RETARD'),  # Prêt très en retard !
            (3, 3, -10, 30, 'EN_COURS'),   # Prêt en cours longue durée
            (4, 4, -60, 14, 'RETOURNE'),   # Prêt retourné
            (5, 5, -45, 14, 'RETOURNE'),   # Prêt retourné
            (0, 6, -90, 14, 'RETOURNE'),   # Prêt retourné ancien
            (1, 7, -200,14, 'PERDU'),      # Prêt perdu !
            (2, 8, -3,  7,  'EN_COURS'),   # Prêt court en cours
        ]

        for emp_idx, doc_idx, delta_debut, duree, statut in PRETS:
            if not docs_phys:
                break
            emprunteur = emprunteurs[emp_idx % len(emprunteurs)]
            doc        = docs_phys[doc_idx % len(docs_phys)]
            date_pret  = date.today() + timedelta(days=delta_debut)
            date_retour_prevue = date_pret + timedelta(days=duree)

            if PretDocument.objects.filter(document=doc, emprunteur=emprunteur, statut__in=['EN_COURS','EN_RETARD']).exists():
                nb += 1
                continue

            pret = PretDocument(
                document           = doc,
                emprunteur         = emprunteur,
                accorde_par        = arch,
                date_retour_prevue = date_retour_prevue,
                statut             = statut,
                observations       = 'Prêt créé par seed_full_db.',
            )
            if statut == 'RETOURNE':
                pret.date_retour_effective = date_pret + timedelta(days=random.randint(3, duree))
            elif statut == 'PERDU':
                pret.observations = 'Document signalé non retourné après relances multiples. Procédure de constat lancée.'
            elif statut == 'EN_RETARD':
                pret.statut = 'EN_COURS'  # Django déterminera le retard via la property
            pret.save()
            nb += 1
            emoji = '🔴' if statut == 'EN_RETARD' else ('☠️' if statut == 'PERDU' else '✓')
            self.log(f'    {emoji} [{statut}] {emprunteur.username} → {doc.identifiant[:20]} (retour prévu: {date_retour_prevue})')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} prêt(s).\n'))

    # ── 6. DEMANDES DE RECHERCHE ──────────────────────────────────────────────

    def _creer_recherches(self, users, docs):
        self.stdout.write('[6/13] Demandes de recherche documentaire...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        agents      = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT')]
        cats        = list(CategorieDocument.objects.all())
        arch        = archivistes[0]
        nb          = 0

        RECHERCHES = [
            (0, 0, 'Besoin pour rapport semestriel', 'Recherche du rapport de mission terrain Kédougou de mars 2023 ou similaire.', 'EN_ATTENTE', '', None),
            (1, 1, 'Consultation courrier entrant 2022', 'Courrier du Ministère des Mines reçu en 2022 concernant les examens professionnels.', 'EN_ATTENTE', '', None),
            (2, 2, 'Préparation soutenance thèse', 'PV de jury de soutenance de thèse du département Géologie entre 2018 et 2022.', 'ACCORDEE',   '', 0),
            (3, 3, 'Recherche convention partenariale', 'Convention de coopération ENSMG / université française (2019-2023).', 'ACCORDEE',   '', 1),
            (4, 4, 'Audit interne comptabilité', 'Rapport financier annuel exercice 2020 ou 2021.', 'REFUSEE', 'Document classifié CONFIDENTIEL — accès non autorisé pour ce profil.', None),
            (5, 0, 'Mise à jour programme formation', 'Programme de formation cycle ingénieur géologie antérieur à 2020.', 'REFUSEE', 'Aucun programme antérieur à 2020 retrouvé dans les fonds.', None),
            (6, 1, 'Recherche acte administratif', 'Arrêté de nomination d\'un directeur ENSMG antérieur à 2022.', 'EN_ATTENTE', '', None),
            (0, 2, 'Vérification diplôme étudiant', 'Diplôme d\'ingénieur promotion 2021 ou 2022 délivré par l\'ENSMG.', 'ACCORDEE',   '', 2),
        ]

        docs_non_deleted = [d for d in docs if d.deleted_at is None]

        for ag_idx, cat_idx, motif, description, statut, motif_refus, doc_idx in RECHERCHES:
            agent = agents[ag_idx % len(agents)]
            cat   = cats[cat_idx % len(cats)]

            if DemandeRecherche.objects.filter(agent=agent, description=description).exists():
                nb += 1
                continue

            dr = DemandeRecherche(
                agent       = agent,
                categorie   = cat,
                motif       = motif,
                description = description,
                statut      = statut,
                motif_refus = motif_refus,
            )
            if statut in ('ACCORDEE', 'REFUSEE'):
                dr.traite_par      = arch
                dr.date_traitement = timezone.now() - timedelta(days=random.randint(1, 10))
            if statut == 'ACCORDEE' and doc_idx is not None and doc_idx < len(docs_non_deleted):
                dr.document_fourni = docs_non_deleted[doc_idx]
            dr.save()
            nb += 1
            self.log(f'    + [{statut}] {agent.username}: {description[:50]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} demande(s) de recherche.\n'))

    # ── 7. BORDEREAUX ─────────────────────────────────────────────────────────

    def _creer_bordereaux(self, users, docs):
        self.stdout.write('[7/13] Bordereaux de versement et d\'élimination...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        direction   = [u for u in users if u.role == 'DIRECTION'] or users[:1]
        arch = archivistes[0]
        dir_ = direction[0] if direction else arch

        docs_def    = [d for d in docs if d.statut == 'DEFINITIF' and d.deleted_at is None]
        docs_inter  = [d for d in docs if d.statut == 'INTERMEDIAIRE' and d.deleted_at is None]
        docs_elim   = [d for d in docs if d.sort_final == 'ELIMINATION' and d.deleted_at is None]

        # (num, service, statut, docs, valide, d_val, obs, exercice)
        BV = [
            ('BV-2025-001', 'Scolarité',                         'BROUILLON',     docs_def[:3],  False, None,            '',                                                                         2025),
            ('BV-2025-002', 'Direction Générale',                 'EN_VALIDATION', docs_def[3:6], False, None,            'En attente validation Directeur Général.',                                 2025),
            ('BV-2024-003', 'Département Géologie',               'VALIDE',        docs_def[6:9], True,  date(2024,5,15), 'Validé après vérification archivistique complète.',                        2024),
            ('BV-2024-004', 'Laboratoires',                       'EXECUTE',       docs_def[9:12],True,  date(2024,3,10), 'Versé aux Archives nationales du Sénégal le 15/03/2024.',                  2024),
            ('BV-2024-005', 'Direction des Ressources Humaines',  'EXECUTE',       docs_def[:2],  True,  date(2024,6,20), 'Versé le 20 juin 2024. Récépissé ANS/2024/VER-0045.',                     2024),
            ('BV-2023-012', 'Direction Administrative et Financière','REJETE',     docs_inter[:2],False, None,            'Documents ne remplissant pas encore les critères — DUA non échue.',        2023),
            ('BV-2023-007', 'Cartographie et SIG',                'EXECUTE',       docs_def[2:5], True,  date(2023,11,8), 'Versé aux Archives nationales en nov. 2023.',                              2023),
        ]

        # (num, service, statut, docs, _, visa, d_visa, ref_visa, d_elim, motif)
        BE = [
            ('BE-2025-001', 'Scolarité',
             'BROUILLON',     docs_elim[:3],  False, False, None,            '',              None,
             'DUA échue (10 ans) — Correspondances de routine sans valeur historique. Sort final : Élimination selon tableau de gestion révision 2022.'),

            ('BE-2025-002', 'Direction Administrative et Financière',
             'EN_VALIDATION', docs_elim[3:5], False, False, None,            '',              None,
             'DUA échue — Factures et bons de commande antérieurs à 2014. Soumis à la DAS pour visa préalable.'),

            ('BE-2024-003', 'Direction des Ressources Humaines',
             'VISA_OBTENU',   docs_inter[2:4],False, True,  date(2024,4,10), 'DAS/2024/0123', None,
             'DUA échue (5 ans) — Feuilles de présence 2019. Visa DAS obtenu. Destruction programmée.'),

            ('BE-2024-004', 'Scolarité',
             'EXECUTE',       docs_elim[:2],  False, True,  date(2024,2,20), 'DAS/2024/0089', date(2024,6,15),
             'DUA échue — Bordereaux de notes antérieurs à 2011. Destruction physique par déchiquetage le 15 juin 2024.'),

            ('BE-2023-008', 'Direction Générale',
             'REJETE',        docs_inter[:1], False, False, None,            '',              None,
             'DUA non encore échue pour certains documents — Demande rejetée par la DAS. Révision du tableau de gestion requise.'),
        ]

        nb_v = nb_e = 0
        for num, service, statut, doc_list, valide, d_val, obs, exercice in BV:
            if BordereauVersement.objects.filter(numero=num).exists():
                nb_v += 1; continue
            bv = BordereauVersement.objects.create(
                numero               = num,
                service_versant      = service,
                service_destinataire = 'Service des Archives — ENSMG',
                exercice             = exercice,
                statut               = statut,
                observations         = obs or f'Bordereau de versement — {service} — Exercice {exercice}',
                cree_par             = arch,
                valide_par           = dir_ if valide else None,
                date_validation      = d_val,
            )
            bv.documents.set([d for d in doc_list if d])
            # Lier les dépôts ARCHIVE du service pour cet exercice (s'ils existent)
            depots_service = DepotDocument.objects.filter(
                statut='ARCHIVE',
                date_depot__year=exercice,
                agent__departement__nom=service,
            )
            if depots_service.exists():
                bv.depots.set(depots_service)
            nb_v += 1
            self.log(f'    + BV {num} ({statut}) exercice={exercice} — {len([d for d in doc_list if d])} doc(s)')

        for num, service, statut, doc_list, _, visa, d_visa, ref_visa, d_elim, motif in BE:
            if BordereauElimination.objects.filter(numero=num).exists():
                nb_e += 1; continue
            be = BordereauElimination.objects.create(
                numero             = num,
                service_producteur = service,
                statut             = statut,
                motif              = motif,
                observations       = f'Ref. visa : {ref_visa}' if ref_visa else '',
                cree_par           = arch,
                visa_das           = visa,
                date_visa          = d_visa,
                reference_visa     = ref_visa or '',
                date_elimination   = d_elim,
            )
            be.documents.set([d for d in doc_list if d])
            nb_e += 1
            self.log(f'    + BE {num} ({statut}) — {len([d for d in doc_list if d])} doc(s)')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb_v} bordereau(x) de versement, {nb_e} bordereau(x) d\'élimination.\n'))

    # ── 8. RÉTENTIONS JURIDIQUES ──────────────────────────────────────────────

    def _creer_retentions(self, users, docs):
        self.stdout.write('[8/13] Rétentions juridiques (Legal Hold)...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        arch        = archivistes[0]
        # On bloque des docs qui ont sort_final ELIMINATION pour tester le conflit
        cibles = [d for d in docs if d.sort_final == 'ELIMINATION' and d.deleted_at is None][:3]

        RETENTIONS = [
            ('Procédure judiciaire devant le Tribunal Régional de Dakar — Affaire ENSMG/NDIAGNE.',
             'Tribunal Régional de Dakar Hors Classe',
             'TRD/2023/CV-4892',
             date(2023, 3, 10), None, True),
            ('Audit de la Cour des Comptes du Sénégal — Exercice 2021-2022.',
             'Cour des Comptes du Sénégal',
             'CCS/AUDIT/2024/007',
             date(2024, 1, 15), date(2025, 6, 30), True),
            ('Contentieux administratif avec prestataire BATITECH — Résolu.',
             'Tribunal Administratif de Dakar',
             'TAD/2022/ADM-1123',
             date(2022, 8, 1), date(2023, 12, 31), False),  # Levée
        ]

        nb = 0
        for i, (motif, autorite, reference, debut, fin, active) in enumerate(RETENTIONS):
            if i >= len(cibles):
                break
            doc = cibles[i]
            if RetentionJuridique.objects.filter(document=doc, reference=reference).exists():
                nb += 1; continue
            RetentionJuridique.objects.create(
                document   = doc,
                motif      = motif,
                autorite   = autorite,
                reference  = reference,
                date_debut = debut,
                date_fin   = fin,
                active     = active,
                cree_par   = arch,
            )
            nb += 1
            etat = '🔒 ACTIVE' if active else '🔓 Levée'
            self.log(f'    + {etat} — {doc.identifiant[:20]} — {autorite[:40]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} rétention(s) juridique(s).\n'))

    # ── 9. ACCÈS ABAC ─────────────────────────────────────────────────────────

    def _creer_acces_abac(self, users, docs):
        self.stdout.write('[9/13] Accès ABAC individuels (AccesDocument)...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        cibles_user = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT')]
        docs_conf   = [d for d in docs if d.confidentialite in ('CONFIDENTIEL','SECRET') and d.deleted_at is None]
        arch        = archivistes[0]
        nb          = 0

        ACCES = [
            (0, 0, 'TELECHARGEMENT', 48,  'Audit interne comptabilité — accès temporaire accordé.'),
            (1, 1, 'LECTURE',        24,  'Consultation pour rapport de recherche.'),
            (2, 2, 'LECTURE',        None,'Accès permanent — membre commission pédagogique.'),
            (3, 3, 'TELECHARGEMENT', 72,  'Préparation dossier CAMES — 72h.'),
            (4, 4, 'LECTURE',        24,  'Vérification ponctuelle dossier personnel.'),
        ]

        for usr_idx, doc_idx, type_acces, duree_h, motif in ACCES:
            if usr_idx >= len(cibles_user) or doc_idx >= len(docs_conf):
                continue
            user = cibles_user[usr_idx]
            doc  = docs_conf[doc_idx]

            if AccesDocument.objects.filter(document=doc, utilisateur=user).exists():
                nb += 1; continue

            date_fin = timezone.now() + timedelta(hours=duree_h) if duree_h else None
            AccesDocument.objects.create(
                document    = doc,
                utilisateur = user,
                accorde_par = arch,
                date_fin    = date_fin,
                type_acces  = type_acces,
                actif       = True,
                motif       = motif,
            )
            nb += 1
            exp = f"{duree_h}h" if duree_h else 'permanent'
            self.log(f'    + {user.username} → {doc.identifiant[:20]} [{type_acces}, {exp}]')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} accès ABAC.\n'))

    # ── 10. AUDIT TOKENS ──────────────────────────────────────────────────────

    def _creer_audit_tokens(self, users, docs):
        self.stdout.write('[10/13] Tokens d\'audit externe...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        arch        = archivistes[0]
        cats        = list(CategorieDocument.objects.all())
        plans       = list(PlanClassement.objects.filter(niveau=1)[:4])
        nb          = 0

        maintenant = timezone.now()

        TOKENS = [
            # (description, auditeur, email, perimetre, conf_max, delta_debut, delta_exp, nb_consult, actif)
            (
                'Mission d\'audit IGEF — Inspection générale finances 2024',
                'Inspecteur Général Moussa DIOUF — IGEF',
                'inspection@igef.gouv.sn',
                'CATEGORIE', 'CONFIDENTIEL',
                -5, +25, 12, True,   # Actif, en cours
            ),
            (
                'Évaluation CAMES — Dossiers accréditation filières Mines & Géologie',
                'Commission CAMES — Pr. Adama KONATÉ (Burkina Faso)',
                'a.konate@cames.bf',
                'SELECTION', 'INTERNE',
                -30, -5, 8, True,    # Expiré !
            ),
            (
                'Audit comptable — Cabinet DELOITTE Sénégal, Exercice 2024',
                'Cabinet DELOITTE Sénégal — M. Alioune BADIANE',
                'a.badiane@deloitte.com',
                'PLAN', 'CONFIDENTIEL',
                +10, +40, 0, True,   # Futur — pas encore valide
            ),
        ]

        for desc, auditeur, email, perimetre, conf_max, d_debut, d_exp, nb_consult, actif in TOKENS:
            if AuditToken.objects.filter(description=desc).exists():
                nb += 1; continue

            token = AuditToken(
                description         = desc,
                auditeur_nom        = auditeur,
                auditeur_email      = email,
                perimetre           = perimetre,
                confidentialite_max = conf_max,
                date_debut          = maintenant + timedelta(days=d_debut),
                date_expiration     = maintenant + timedelta(days=d_exp),
                actif               = actif,
                cree_par            = arch,
                nb_consultations    = nb_consult,
                derniere_consultation = (maintenant - timedelta(hours=3)) if nb_consult > 0 else None,
            )
            token.save()

            if perimetre == 'CATEGORIE' and cats:
                token.categories.set(cats[:3])
            elif perimetre == 'PLAN' and plans:
                token.plans.set(plans[:2])
            elif perimetre == 'SELECTION':
                docs_sel = [d for d in docs if d.confidentialite == 'INTERNE' and d.deleted_at is None][:5]
                token.documents.set(docs_sel)

            nb += 1
            etat = '✅ VALIDE' if token.est_valide else ('⏳ FUTUR' if d_debut > 0 else '❌ EXPIRÉ')
            self.log(f'    + {etat} — {auditeur[:50]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} token(s) d\'audit.\n'))

    # ── 11. VÉRIFICATIONS D'INTÉGRITÉ ─────────────────────────────────────────

    def _creer_verifications_integrite(self, users, docs):
        self.stdout.write('[11/13] Vérifications d\'intégrité SHA-256...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        arch        = archivistes[0]
        docs_num    = [d for d in docs if d.support == 'NUMERIQUE' and d.deleted_at is None][:10]
        nb          = 0

        for i, doc in enumerate(docs_num):
            if VerificationIntegrite.objects.filter(document=doc).exists():
                nb += 1; continue

            # Simuler le hash (pas de vrai fichier)
            contenu_simule = f"{doc.identifiant}-{doc.titre}".encode()
            sha = hashlib.sha256(contenu_simule).hexdigest()

            # Le 8ème doc simulera une altération détectée
            resultat = 'ECHOUE' if i == 7 else 'OK'
            message  = (
                'ALERTE : empreinte SHA-256 différente de celle enregistrée à l\'archivage. '
                'Fichier potentiellement altéré — quarantaine en attente d\'investigation.'
                if resultat == 'ECHOUE' else
                'Intégrité vérifiée — empreinte SHA-256 conforme.'
            )

            VerificationIntegrite.objects.create(
                document            = doc,
                empreinte_calculee  = sha if resultat == 'OK' else sha[:-6] + 'TAMPER',
                empreinte_reference = sha,
                resultat            = resultat,
                message             = message,
                verifie_par         = arch,
            )
            nb += 1
            emoji = '✅' if resultat == 'OK' else '🔴'
            self.log(f'    {emoji} [{resultat}] {doc.identifiant[:20]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} vérification(s) d\'intégrité.\n'))

    # ── 12. MOUVEMENTS D'AUDIT ────────────────────────────────────────────────

    def _creer_mouvements(self, users, docs):
        self.stdout.write('[12/13] Journal d\'audit (MouvementDocument)...')
        total = 0
        for doc in docs:
            if MouvementDocument.objects.filter(document=doc, action='CREATION').exists():
                total += 1
                continue

            # Création
            MouvementDocument.objects.create(
                document    = doc,
                action      = 'CREATION',
                utilisateur = doc.cree_par,
                commentaire = 'Enregistrement initial du document dans le système.',
                adresse_ip  = '192.168.1.10',
            )
            total += 1

            # 1 à 4 consultations
            for _ in range(random.randint(1, 4)):
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'CONSULTATION',
                    utilisateur = random.choice(users),
                    adresse_ip  = f'192.168.1.{random.randint(10, 250)}',
                )
                total += 1

            # Modification éventuelle
            if doc.statut in ('INTERMEDIAIRE','DEFINITIF') or random.random() > 0.5:
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'MODIFICATION',
                    utilisateur = doc.modifie_par,
                    commentaire = 'Mise à jour des métadonnées descriptives.',
                    details     = {'champ': 'description', 'avant': '', 'apres': doc.description[:80]},
                    adresse_ip  = '192.168.1.10',
                )
                total += 1

            # Changement de statut
            if doc.statut not in ('COURANT',):
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'CHANGEMENT_STATUT',
                    utilisateur = doc.cree_par,
                    commentaire = f'Passage au statut {doc.get_statut_display()}.',
                    details     = {'nouveau_statut': doc.statut},
                    adresse_ip  = '192.168.1.10',
                )
                total += 1

            # Téléchargement pour les docs confidentiels
            if doc.confidentialite in ('CONFIDENTIEL','SECRET') and random.random() > 0.4:
                MouvementDocument.objects.create(
                    document    = doc,
                    action      = 'TELECHARGEMENT',
                    utilisateur = random.choice(users),
                    commentaire = 'Téléchargement autorisé.',
                    adresse_ip  = f'192.168.1.{random.randint(10, 250)}',
                )
                total += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {total} mouvement(s) d\'audit.\n'))

    # ── 13. NOTIFICATIONS ─────────────────────────────────────────────────────

    def _creer_notifications(self, users, docs):
        self.stdout.write('[13/13] Notifications internes...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        direction   = [u for u in users if u.role == 'DIRECTION']
        agents      = [u for u in users if u.role in ('PERSONNEL', 'ENSEIGNANT')]
        arch        = archivistes[0]
        dir_        = direction[0] if direction else arch
        docs_actifs = [d for d in docs if d.deleted_at is None]
        nb          = 0

        def notif(dest, type_, titre, msg, doc=None, lue=False):
            nonlocal nb
            if Notification.objects.filter(destinataire=dest, titre=titre).exists():
                nb += 1; return
            Notification.objects.create(
                destinataire = dest,
                type         = type_,
                titre        = titre,
                message      = msg,
                document     = doc,
                lue          = lue,
            )
            nb += 1

        # Notifs pour archiviste — dépôts en attente
        notif(arch, 'NOUVEAU_DEPOT',
              'Nouveau dépôt en attente de traitement',
              '5 nouveaux dépôts de documents nécessitent votre traitement.',
              lue=False)

        # Notifs pour archiviste — DUA
        for doc in docs_actifs[:3]:
            if doc.date_fin_dua and doc.date_fin_dua < date.today():
                notif(arch, 'DUA_ECHUE',
                      f'DUA échue — {doc.identifiant}',
                      f'La Durée d\'Utilité Administrative du document « {doc.titre[:60]} » est échue depuis le {doc.date_fin_dua}. Une décision de sort final est nécessaire.',
                      doc=doc, lue=False)

        # Notifs pour agents — demandes traitées
        for agent in agents[:4]:
            notif(agent, 'DEMANDE_TRAITEE',
                  'Votre demande de prêt a été traitée',
                  'L\'archiviste a donné suite à votre demande de prêt. Consultez votre espace "Mes demandes".',
                  lue=random.choice([True, False]))

        # Notifs pour direction — bordereaux
        notif(dir_, 'BORDEREAU_VALIDATION',
              'Bordereau de versement BV-2024-002 en attente de validation',
              'Le bordereau de versement BV-2024-002 a été soumis par l\'archiviste et nécessite votre validation.',
              lue=False)

        # Notifs lues (historique)
        for agent in agents[:6]:
            notif(agent, 'DEPOT_ARCHIVE',
                  'Votre dépôt a été archivé avec succès',
                  'Votre document a été enregistré dans le système d\'archives avec un identifiant unique. Conservez votre numéro de récépissé.',
                  lue=True)

        # Notif de prêt en retard
        notif(arch, 'PRET_EN_RETARD',
              '⚠ Prêts en retard — relance nécessaire',
              '2 documents physiques n\'ont pas été retournés à la date prévue. Veuillez relancer les emprunteurs.',
              lue=False)

        # Notif système
        notif(arch, 'SYSTEME',
              'Vérification d\'intégrité SHA-256 — ALERTE',
              '1 fichier présente une empreinte SHA-256 différente de celle enregistrée à l\'archivage. Consultez le journal des vérifications d\'intégrité.',
              lue=False)

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} notification(s).\n'))

    # ── CORBEILLE — Soft delete sur quelques documents ────────────────────────

    def _mettre_en_corbeille(self, docs, users):
        self.stdout.write('[+] Mise en corbeille (soft delete)...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]

        mots_corbeille = ['CORBEILLE', 'brouillon', 'test', 'fictice']
        nb = 0
        for doc in docs:
            if any(m.upper() in doc.titre.upper() for m in mots_corbeille):
                if doc.deleted_at is None:
                    doc.deleted_at = timezone.now() - timedelta(days=random.randint(1, 30))
                    doc.save(update_fields=['deleted_at'])
                    MouvementDocument.objects.create(
                        document    = doc,
                        action      = 'MODIFICATION',
                        utilisateur = archivistes[0],
                        commentaire = 'Document déplacé en corbeille (soft delete).',
                        details     = {'action': 'CORBEILLE'},
                        adresse_ip  = '192.168.1.10',
                    )
                    nb += 1
                    self.log(f'    🗑 Corbeille : {doc.identifiant[:20]} — {doc.titre[:50]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} document(s) en corbeille.\n'))

    # ── COURRIERS ─────────────────────────────────────────────────────────────

    def _creer_courriers(self, users):
        self.stdout.write('[+] Courriers (arrivée & départ)...')
        archivistes  = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        secretaires  = [u for u in users if u.role in ('PERSONNEL',)] or users[:2]
        arch         = archivistes[0]
        sec          = secretaires[0] if secretaires else arch

        # (sens, objet, expediteur, destinataire, service_interne,
        #  date_courrier, ref_exp, statut, confidentialite, sort_final,
        #  delai_reponse, instructions, description, accuse, avec_reponse_idx)
        # Avec_reponse_idx : index du courrier arrivée auquel ce départ répond (None sinon)
        COURRIERS = [
            # ── ARRIVÉE ──────────────────────────────────────────────────────
            ('ARRIVEE',
             'Demande d\'informations sur les conditions d\'admission en cycle ingénieur — Session 2024',
             'Direction Générale des Mines et de la Géologie (DGMG)',
             'Directeur Général ENSMG',
             'Scolarité',
             date(2024, 1, 8),
             'DGMG/2024/0012',
             'TRAITE', 'INTERNE',
             'ELIMINATION',
             date(2024, 1, 22),
             'Préparer une note de réponse détaillant les conditions d\'admission et le calendrier du concours.',
             'Courrier du Directeur des Mines demandant des précisions sur les modalités d\'inscription au cycle ingénieur pour l\'année 2024.',
             True, None),

            ('ARRIVEE',
             'Notification d\'inspection des établissements d\'enseignement supérieur — Exercice 2024',
             'Ministère de l\'Enseignement Supérieur, de la Recherche et de l\'Innovation (MESRI)',
             'Directeur Général ENSMG',
             'Direction Générale',
             date(2024, 2, 5),
             'MESRI/DGES/2024/0089',
             'TRAITE', 'INTERNE',
             'CONSERVATION',
             date(2024, 2, 19),
             'Préparer les dossiers d\'inspection (programmes, effectifs, équipements, finances).',
             'Notification officielle de l\'inspection annuelle de l\'établissement prévue pour le mois de mars 2024.',
             True, None),

            ('ARRIVEE',
             'Convention de partenariat académique ENSMG / Université Cheikh Anta Diop — Renouvellement',
             'Université Cheikh Anta Diop de Dakar (UCAD) — Bureau des relations extérieures',
             'Directeur Général ENSMG',
             'Direction Générale / Coopération',
             date(2024, 2, 20),
             'UCAD/BRE/2024/0034',
             'EN_TRAITEMENT', 'INTERNE',
             'CONSERVATION',
             date(2024, 3, 20),
             'Analyser les termes du renouvellement de convention, consulter le Conseil d\'administration.',
             'Proposition de renouvellement de la convention de partenariat pour 5 ans, avec extension des échanges d\'enseignants.',
             False, None),

            ('ARRIVEE',
             'Demande de stage de perfectionnement — M. Ibrahima BADJI, Technicien DGM',
             'Direction de la Géologie et des Mines (DGM)',
             'Directeur Général ENSMG',
             'Scolarité / Département Mines',
             date(2024, 3, 4),
             'DGM/STG/2024/0007',
             'TRAITE', 'INTERNE',
             'ELIMINATION',
             date(2024, 3, 18),
             'Vérifier les disponibilités du Département Mines, préparer une convention de stage.',
             'Demande d\'accueil en stage de perfectionnement (3 mois) pour un technicien de la DGM, spécialité gisements miniers.',
             True, None),

            ('ARRIVEE',
             'Réclamation — Résultats délibération jury — Promo 2024, filière Géologie',
             'Association des Étudiants en Géologie de l\'ENSMG (AEGE)',
             'Directeur Général ENSMG',
             'Scolarité',
             date(2024, 8, 3),
             'AEGE/2024/REC-002',
             'EN_TRAITEMENT', 'CONFIDENTIEL',
             'CONSERVATION',
             date(2024, 8, 17),
             'Saisir le Président du jury pour vérification. Réponse motivée obligatoire dans les délais légaux.',
             'Réclamation collective de 12 étudiants contestant les résultats de délibération de la session de juillet 2024.',
             True, None),

            ('ARRIVEE',
             'Convocation à la séance plénière du Comité National des Mines — Octobre 2024',
             'Ministère des Mines et de la Géologie',
             'Directeur Général ENSMG',
             'Direction Générale',
             date(2024, 9, 10),
             'MMG/CNM/2024/0156',
             'TRAITE', 'INTERNE',
             'ELIMINATION',
             date(2024, 9, 20),
             'Confirmer la participation du Directeur. Préparer une note de contribution sur l\'insertion professionnelle des diplômés.',
             'Invitation à la séance plénière du Comité National des Mines, le 1er octobre 2024 à Dakar.',
             True, None),

            ('ARRIVEE',
             'Demande de liste des diplômés de la filière Géotechnique — Années 2020 à 2024',
             'Société Nationale des Chemins de Fer du Sénégal (SNCS) — Direction RH',
             'Directeur Général ENSMG',
             'Scolarité',
             date(2024, 10, 14),
             'SNCS/RH/2024/0298',
             'ENREGISTRE', 'INTERNE',
             'ELIMINATION',
             date(2024, 10, 28),
             'Vérifier les conditions légales de communication. Consulter le DPO avant tout envoi de liste nominative.',
             'Demande de communication des coordonnées des diplômés en géotechnique pour un recrutement direct.',
             False, None),

            ('ARRIVEE',
             'Notification de versement de subvention — Programme d\'équipement pédagogique 2024',
             'Ministère des Finances — Direction Générale de la Comptabilité Publique',
             'Directeur Général ENSMG',
             'DAF',
             date(2024, 11, 5),
             'DGCP/SUB/2024/4512',
             'TRAITE', 'INTERNE',
             'CONSERVATION',
             date(2024, 11, 12),
             'Informer le DAF. Préparer l\'accusé de réception et ouvrir le dossier de suivi de la subvention.',
             'Notification de virement de 45 000 000 FCFA au titre du programme d\'équipement pédagogique ENSMG 2024.',
             True, None),

            # ── DÉPART ───────────────────────────────────────────────────────
            ('DEPART',
             'Réponse à la demande d\'informations DGMG — Conditions d\'admission 2024',
             'Directeur Général ENSMG',
             'Directeur Général des Mines et de la Géologie',
             'Scolarité',
             date(2024, 1, 18),
             'ENSMG/DG/2024/0008',
             'ARCHIVE', 'INTERNE',
             'ELIMINATION',
             None,
             '',
             'Note de réponse détaillant les conditions d\'admission, le calendrier du concours et les filières ouvertes en 2024.',
             False, 0),   # en réponse au courrier arrivée index 0

            ('DEPART',
             'Confirmation de participation — Séance plénière Comité National des Mines',
             'Directeur Général ENSMG',
             'Ministère des Mines et de la Géologie — Secrétariat Général',
             'Direction Générale',
             date(2024, 9, 14),
             'ENSMG/DG/2024/0089',
             'ARCHIVE', 'INTERNE',
             'ELIMINATION',
             None,
             '',
             'Confirmation de la participation du Directeur Général à la séance plénière du 1er octobre 2024 et envoi de la note de contribution.',
             False, 5),   # en réponse au courrier arrivée index 5

            ('DEPART',
             'Accord de stage — M. Ibrahima BADJI — Convention ENSMG/DGM n° 2024-STG-018',
             'Directeur Général ENSMG',
             'Directeur de la Géologie et des Mines',
             'Département Mines / Scolarité',
             date(2024, 3, 12),
             'ENSMG/SCO/2024/0021',
             'ARCHIVE', 'INTERNE',
             'CONSERVATION',
             None,
             '',
             'Envoi de la convention de stage signée pour M. Badji, avec planning d\'accueil au Département Mines (avril – juin 2024).',
             False, 3),   # en réponse au courrier arrivée index 3

            ('DEPART',
             'Accusé de réception — Subvention programme d\'équipement pédagogique 2024',
             'Directeur Général ENSMG',
             'Direction Générale de la Comptabilité Publique',
             'DAF',
             date(2024, 11, 8),
             'ENSMG/DAF/2024/0134',
             'ARCHIVE', 'INTERNE',
             'ELIMINATION',
             None,
             '',
             'Accusé de réception de la subvention de 45 000 000 FCFA et ouverture officielle du dossier de suivi budgétaire.',
             False, 7),   # en réponse au courrier arrivée index 7

            ('DEPART',
             'Demande d\'agrément pour l\'ouverture d\'une filière Ingénieur Environnement — 2025',
             'Directeur Général ENSMG',
             'Ministère de l\'Enseignement Supérieur — Direction des Établissements',
             'Direction Générale',
             date(2024, 12, 2),
             'ENSMG/DG/2024/0156',
             'ENREGISTRE', 'INTERNE',
             'CONSERVATION',
             None,
             '',
             'Dossier complet de demande d\'ouverture d\'une nouvelle filière : maquette pédagogique, liste enseignants, équipements disponibles.',
             False, None),

            ('DEPART',
             'Rapport annuel 2023 — Transmission à la tutelle',
             'Directeur Général ENSMG',
             'Ministère des Mines et de la Géologie — Secrétariat Général',
             'Direction Générale',
             date(2024, 4, 15),
             'ENSMG/DG/2024/0041',
             'ARCHIVE', 'INTERNE',
             'CONSERVATION',
             None,
             '',
             'Envoi du rapport annuel d\'activités 2023, conformément à l\'obligation réglementaire annuelle de reddition de comptes.',
             False, None),
        ]

        crees = []
        for i, row in enumerate(COURRIERS):
            (sens, objet, exp, dest, svc, d_cour, ref_exp, statut, conf,
             sort_final, delai, instr, desc, accuse, rep_idx) = row

            if Courrier.objects.filter(objet=objet, date_courrier=d_cour).exists():
                c = Courrier.objects.get(objet=objet, date_courrier=d_cour)
                crees.append(c)
                continue

            en_rep = None
            if rep_idx is not None and rep_idx < len(crees):
                en_rep = crees[rep_idx]

            c = Courrier(
                sens                  = sens,
                objet                 = objet,
                expediteur            = exp,
                destinataire          = dest,
                service_interne       = svc,
                date_courrier         = d_cour,
                reference_expediteur  = ref_exp,
                statut                = statut,
                confidentialite       = conf,
                sort_final            = sort_final,
                delai_reponse         = delai,
                instructions          = instr,
                description           = desc,
                accuse_reception      = accuse,
                en_reponse_a          = en_rep,
                cree_par              = sec,
                traite_par            = arch if statut in ('TRAITE', 'ARCHIVE') else None,
                date_traitement       = timezone.now() - timedelta(days=random.randint(2, 30)) if statut in ('TRAITE', 'ARCHIVE') else None,
                date_archivage        = timezone.now() - timedelta(days=random.randint(1, 15)) if statut == 'ARCHIVE' else None,
                localisation_physique = f'Registre courriers {d_cour.year}, intercalaire {d_cour.strftime("%B")}',
            )
            c.save()
            crees.append(c)

            # Journal d'audit
            MouvementCourrier.objects.create(
                courrier    = c,
                action      = 'ENREGISTREMENT',
                utilisateur = sec,
                commentaire = f'Enregistrement du courrier {sens}.',
                adresse_ip  = '192.168.1.10',
            )
            if statut in ('TRAITE', 'ARCHIVE'):
                MouvementCourrier.objects.create(
                    courrier    = c,
                    action      = 'TRAITEMENT',
                    utilisateur = arch,
                    commentaire = 'Traitement et instruction du courrier.',
                    adresse_ip  = '192.168.1.10',
                )
            if statut == 'ARCHIVE':
                MouvementCourrier.objects.create(
                    courrier    = c,
                    action      = 'ARCHIVAGE',
                    utilisateur = arch,
                    commentaire = 'Classement définitif dans le registre des courriers.',
                    adresse_ip  = '192.168.1.10',
                )
            arrow = '→' if sens == 'DEPART' else '←'
            self.log(f'    {arrow} [{c.numero_enregistrement}] {objet[:55]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(crees)} courrier(s).\n'))
        return crees

    # ── BORDEREAUX COURRIERS ───────────────────────────────────────────────────

    def _creer_bordereaux_courriers(self, courriers, users):
        self.stdout.write('[+] Bordereaux de versement et d\'élimination (courriers)...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        direction   = [u for u in users if u.role == 'DIRECTION'] or users[:1]
        arch        = archivistes[0]
        dir_        = direction[0] if direction else arch

        c_archives  = [c for c in courriers if c.statut == 'ARCHIVE' and c.deleted_at is None]
        c_elim      = [c for c in courriers if c.sort_final == 'ELIMINATION' and c.deleted_at is None]

        BVC = [
            ('BVC-2024-001', 'BROUILLON',     c_archives[:3],  False, None,
             'Premier bordereau en cours de constitution pour les courriers de 2024.'),
            ('BVC-2024-002', 'EN_VALIDATION', c_archives[3:6], False, None,
             'Soumis à la Direction Générale pour validation avant versement aux Archives nationales.'),
            ('BVC-2023-004', 'EXECUTE',       c_archives[:2],  True,  date(2024, 6, 10),
             'Versé aux Archives nationales du Sénégal le 12 juin 2024. Récépissé ANS/2024/VER-0089.'),
        ]

        BEC = [
            ('BEC-2024-001', 'BROUILLON',     c_elim[:3],
             'DUA échue — Courriers de routine sans valeur historique identifiée.',
             False, None, None, None),
            ('BEC-2024-002', 'VISA_OBTENU',   c_elim[3:5],
             'DUA échue — Correspondances de gestion courante, sort final Élimination selon tableau de gestion.',
             True, date(2024, 5, 20), 'DAS/2024/VIS-0067', None),
            ('BEC-2023-003', 'EXECUTE',       c_elim[:2],
             'DUA échue — Courriers de 2020 éliminés conformément au visa DAS.',
             True, date(2023, 11, 15), 'DAS/2023/VIS-0124', date(2024, 1, 8)),
        ]

        nb_v = nb_e = 0
        for num, statut, c_list, valide, d_val, obs in BVC:
            if BordereauVersementCourrier.objects.filter(numero=num).exists():
                nb_v += 1; continue
            bvc = BordereauVersementCourrier.objects.create(
                numero               = num,
                service_versant      = 'Secrétariat ENSMG',
                service_destinataire = 'Archives nationales du Sénégal',
                statut               = statut,
                observations         = obs,
                cree_par             = arch,
                valide_par           = dir_ if valide else None,
                date_validation      = d_val,
            )
            bvc.courriers.set([c for c in c_list if c])
            nb_v += 1
            self.log(f'    + BVC {num} ({statut}) — {len([c for c in c_list if c])} courrier(s)')

        for num, statut, c_list, motif, visa, d_visa, ref_visa, d_elim in BEC:
            if BordereauEliminationCourrier.objects.filter(numero=num).exists():
                nb_e += 1; continue
            bec = BordereauEliminationCourrier.objects.create(
                numero             = num,
                service_producteur = 'Secrétariat ENSMG',
                statut             = statut,
                motif              = motif,
                cree_par           = arch,
                visa_das           = visa,
                date_visa          = d_visa,
                reference_visa     = ref_visa or '',
                date_elimination   = d_elim,
            )
            bec.courriers.set([c for c in c_list if c])
            nb_e += 1
            self.log(f'    + BEC {num} ({statut}) — {len([c for c in c_list if c])} courrier(s)')

        self.stdout.write(self.style.SUCCESS(
            f'   ✓ {nb_v} bordereau(x) versement courriers, {nb_e} bordereau(x) élimination courriers.\n'
        ))

    # ── MESSAGERIE INTERNE ────────────────────────────────────────────────────

    def _creer_messages(self, users, docs):
        self.stdout.write('[+] Messages internes (messagerie)...')
        archivistes = [u for u in users if u.role == 'ARCHIVISTE'] or users[:1]
        direction   = [u for u in users if u.role == 'DIRECTION']
        agents_cf   = [u for u in users if u.departement and u.departement.code == 'CF']
        agents_cm   = [u for u in users if u.departement and u.departement.code == 'CM']
        agents_rh   = [u for u in users if u.departement and u.departement.code == 'DRH']
        agents_sco  = [u for u in users if u.departement and u.departement.code == 'SCO']
        agents_sec  = [u for u in users if u.departement and u.departement.code == 'SEC']
        agents_all  = [u for u in users if u.role == 'PERSONNEL']

        arch1  = archivistes[0]
        arch2  = archivistes[1] if len(archivistes) > 1 else arch1
        dir_   = direction[0] if direction else arch1
        csa_   = direction[1] if len(direction) > 1 else dir_

        # Raccourcis agents par service
        cf1   = agents_cf[0]  if agents_cf  else arch1
        cf2   = agents_cf[1]  if len(agents_cf)  > 1 else cf1
        cm1   = agents_cm[0]  if agents_cm  else arch1
        rh1   = agents_rh[0]  if agents_rh  else arch1
        rh2   = agents_rh[1]  if len(agents_rh)  > 1 else rh1
        sco1  = agents_sco[0] if agents_sco else arch1
        sco2  = agents_sco[1] if len(agents_sco) > 1 else sco1
        sco3  = agents_sco[2] if len(agents_sco) > 2 else sco1
        sec1  = agents_sec[0] if agents_sec else arch1
        sec2  = agents_sec[1] if len(agents_sec) > 1 else sec1

        doc_ref  = docs[0] if docs else None
        doc_ref2 = docs[5] if len(docs) > 5 else doc_ref

        # (expediteur, [destinataires], objet, corps, doc_lie, parent_idx, marquer_lu)
        MESSAGES = [

            # ── Fil 1 : Validation bordereau versement ─────────────────────────
            (arch1, [dir_, csa_],
             'Validation requise — Bordereau de versement BV-2025-001',
             'Monsieur le Directeur, Madame la CSA,\n\n'
             'Le bordereau de versement BV-2025-001 regroupant 12 dépôts de la Comptabilité Financière et de la Scolarité (exercice 2024) est prêt pour validation.\n\n'
             'Les pièces sont classées, numérotées et l\'inventaire joint. Je reste à votre disposition.\n\n'
             'Cordialement,\nFatou NDIAYE — Archiviste principale',
             doc_ref, None, True),

            (csa_, [arch1],
             'RE: Validation requise — Bordereau de versement BV-2025-001',
             'Madame NDIAYE,\n\n'
             'J\'ai examiné le bordereau BV-2025-001. Il est conforme. Toutefois, je souhaite que les documents de la Comptabilité Financière soient vérifiés par M. THIAM avant signature définitive.\n\n'
             'Merci de me transmettre l\'accusé de réception une fois le versement exécuté.\n\n'
             'Rokhaya MBAYE — Chef des Services Administratifs',
             doc_ref, 0, True),

            (arch1, [dir_],
             'RE: BV-2025-001 — Validation par la CSA obtenue',
             'Monsieur le Directeur,\n\n'
             'La CSA a approuvé le bordereau BV-2025-001 après vérification de la Comptabilité Financière. Le versement peut être exécuté dès votre validation finale.\n\n'
             'Fatou NDIAYE',
             doc_ref, 1, True),

            # ── Fil 2 : Alerte intégrité ───────────────────────────────────────
            (arch2, [arch1, dir_],
             'ALERTE — Discordance SHA-256 sur document archivé',
             'ALERTE SÉCURITÉ\n\n'
             'Lors de la vérification hebdomadaire d\'intégrité, une discordance SHA-256 a été détectée sur un fichier du fonds Comptabilité Financière.\n\n'
             'Référence : CF-2023-FRH-0042\n'
             'Empreinte enregistrée : a3f9c2...\n'
             'Empreinte actuelle    : 9b1d44...\n\n'
             'Une investigation est nécessaire. Document mis en quarantaine.\n\n'
             'Moussa FALL — Archiviste',
             doc_ref2, None, False),

            (arch1, [arch2],
             'RE: ALERTE — Discordance SHA-256',
             'Moussa,\n\n'
             'Bien reçu. J\'ouvre un ticket d\'incident. Merci de ne pas toucher au fichier en attendant.\n'
             'Je contacte M. THIAM (CF) pour vérifier si une modification légitime a eu lieu côté service.\n\n'
             'Fatou',
             doc_ref2, 3, True),

            # ── Fil 3 : Demande de dépôt — Comptabilité Financière ─────────────
            (cf1, [arch1],
             'Dépôt de documents — Clôture exercice 2024 — Comptabilité Financière',
             'Bonjour Madame NDIAYE,\n\n'
             'Dans le cadre de la clôture de l\'exercice 2024, notre service dispose des pièces suivantes à verser aux archives :\n\n'
             '  • Rapport financier annuel 2024 (PDF, 47 pages)\n'
             '  • États de rapprochement bancaire (12 bulletins mensuels)\n'
             '  • Bons de commande exécutés — marchés publics 2024\n'
             '  • Registre des recettes — exercice 2024\n\n'
             'Comment procéder pour le dépôt groupé ?\n\n'
             'Babacar THIAM — Chef de la Comptabilité Financière',
             None, None, True),

            (arch1, [cf1],
             'RE: Dépôt documents CF 2024 — Procédure à suivre',
             'Monsieur THIAM,\n\n'
             'Merci pour votre message. Pour le dépôt groupé, voici la procédure :\n\n'
             '1. Connectez-vous sur le portail Archives → "Nouveau dépôt"\n'
             '2. Sélectionnez la catégorie "Financier et RH (FRH)"\n'
             '3. Déposez chaque document séparément avec son titre exact\n'
             '4. Indiquez "Clôture exercice 2024" dans le champ Observations\n\n'
             'Une fois les dépôts enregistrés, je les traiterai sous 48h.\n\n'
             'Fatou NDIAYE',
             None, 5, True),

            # ── Fil 4 : Scolarité → dossiers étudiants ─────────────────────────
            (sco1, [arch1, arch2],
             'Demande de consultation — Dossiers académiques Promo 2019',
             'Bonjour,\n\n'
             'Dans le cadre de la vérification annuelle, je souhaite consulter les dossiers académiques des diplômés de la Promotion 2019 (37 dossiers).\n\n'
             'Ces documents sont-ils disponibles aux archives ? Quelle est la procédure pour une consultation collective ?\n\n'
             'Aminata SARR — Scolarité',
             None, None, False),

            (arch1, [sco1],
             'RE: Consultation dossiers Promo 2019',
             'Bonjour Madame SARR,\n\n'
             'Les 37 dossiers de la Promo 2019 sont bien archivés (fonds F2.S3). Ils sont en statut INTERMÉDIAIRE avec DUA active jusqu\'en 2029.\n\n'
             'Pour une consultation collective :\n'
             '  - Formulaire de demande de recherche via le portail\n'
             '  - Motif : vérification annuelle des effectifs diplômés\n'
             '  - Délai de mise à disposition : 2 jours ouvrés\n\n'
             'Je vous enverrai une notification dès que les dossiers sont prêts en salle de lecture.\n\n'
             'Fatou NDIAYE',
             None, 7, True),

            # ── Fil 5 : Ressources Humaines — dossier du personnel ─────────────
            (rh1, [arch1],
             'Classement dossier agent — Départ en retraite M. WADE Cheikh',
             'Madame NDIAYE,\n\n'
             'Suite au départ en retraite du Pr. Cheikh WADE le 31 décembre 2024, son dossier de personnel doit être transféré aux archives définitives.\n\n'
             'Le dossier contient :\n'
             '  • Acte de recrutement 2001\n'
             '  • Dossier CAMES (2018)\n'
             '  • 23 évaluations annuelles\n'
             '  • Fiches de paie 2001-2024 (en corbeille numérique)\n\n'
             'Quelle est la procédure de versement pour un dossier de retraité ?\n\n'
             'Marème DIOUF — RH',
             None, None, False),

            (arch1, [rh1],
             'RE: Dossier M. WADE — Procédure de versement retraite',
             'Madame DIOUF,\n\n'
             'Pour les dossiers des agents partant en retraite, la procédure est la suivante :\n\n'
             '1. Déposer le dossier complet sur le portail (catégorie FRH → Dossiers du personnel)\n'
             '2. Préciser "Départ retraite — [NOM]" dans le titre\n'
             '3. Statut de versement : CONSERVATION permanente (valeur juridique)\n\n'
             'Note : les fiches de paie ont une DUA de 10 ans — elles peuvent être éliminées à partir de 2034.\n\n'
             'Fatou NDIAYE',
             None, 9, True),

            # ── Fil 6 : Secrétariat → courriers urgents ────────────────────────
            (sec1, [arch1, csa_],
             'Courrier urgent — Convocation MESRI reçue ce jour',
             'Madame NDIAYE, Madame MBAYE,\n\n'
             'Nous avons reçu ce matin une convocation du MESRI pour une réunion des directeurs d\'établissements le 20 mars 2026.\n'
             'Le courrier original (n° MESRI/DGES/2026/0312) est enregistré au registre des arrivées.\n\n'
             'Merci de l\'archiver dans le fonds Correspondances de la Direction.\n\n'
             'Aissatou BARRY — Secrétariat',
             None, None, False),

            (arch1, [sec1],
             'RE: Convocation MESRI — Pris en charge',
             'Madame BARRY,\n\n'
             'Merci pour le signalement. Le courrier MESRI/DGES/2026/0312 sera indexé dans F1.S3.1 (Courriers entrants) avec le délai de réponse fixé au 18 mars 2026.\n\n'
             'Avez-vous déjà créé l\'entrée dans le registre des courriers du portail ?\n\n'
             'Fatou NDIAYE',
             None, 11, True),

            # ── Fil 7 : Comptabilité des Matières → inventaire ─────────────────
            (cm1, [arch1],
             'Rapport d\'inventaire des équipements — Résultats 2024',
             'Bonjour Madame,\n\n'
             'Suite à l\'inventaire annuel 2024, nous devons archiver les documents suivants :\n\n'
             '  • Procès-verbal d\'inventaire physique — Nov. 2024\n'
             '  • Fiches de mouvement des équipements (92 fiches)\n'
             '  • Rapport de réforme matériel 2024 (3 équipements hors service)\n\n'
             'Ces documents relèvent-ils de la catégorie FRH ou PAT ?\n\n'
             'Mariama CISSÉ — Comptabilité des Matières',
             None, None, False),

            (arch1, [cm1],
             'RE: Documents inventaire CM 2024 — Catégorisation',
             'Madame CISSÉ,\n\n'
             'Pour ces documents :\n'
             '  • PV d\'inventaire → catégorie FRH (valeur administrative, DUA 10 ans)\n'
             '  • Fiches de mouvement → catégorie FRH (DUA 5 ans, sort final Élimination)\n'
             '  • Rapport de réforme → catégorie PAT si concerne du matériel patrimonial, sinon FRH\n\n'
             'Vous pouvez les déposer sur le portail. Je validerai la catégorisation finale.\n\n'
             'Fatou NDIAYE',
             None, 13, True),

            # ── Fil 8 : Direction → information générale ───────────────────────
            (dir_, agents_all[:6],
             'Préparation inspection institutionnelle ANAQ-Sup — Avril 2026',
             'Chers collaborateurs,\n\n'
             'L\'ENSMG sera soumise à l\'inspection de l\'ANAQ-Sup en avril 2026. Dans ce cadre, chaque service doit fournir :\n\n'
             '  1. Bilan d\'activités 2023-2025\n'
             '  2. Procédures internes écrites\n'
             '  3. Rapports d\'archivage des documents sensibles\n\n'
             'Les documents doivent être transmis aux archives avant le 15 mars 2026.\n\n'
             'Ibrahima SECK — Directeur Général',
             None, None, False),

            (arch1, [dir_, csa_] + agents_all[:4],
             'Situation des archives — État des fonds au 1er mars 2026',
             'Monsieur le Directeur, Madame la CSA, Chers collègues,\n\n'
             'Vous trouverez ci-dessous le bilan de l\'état des archives au 1er mars 2026 :\n\n'
             '  • Documents actifs traités     : 47\n'
             '  • Dépôts en attente            :  9\n'
             '  • Dossiers en corbeille        :  2\n'
             '  • DUA échues nécessitant décision : 6\n'
             '  • Bordereaux de versement      :  4 (1 en attente validation)\n\n'
             'Je suis disponible pour tout complément pour l\'inspection ANAQ-Sup.\n\n'
             'Fatou NDIAYE — Archiviste principale',
             doc_ref, None, False),

            # ── Fil 9 : Scolarité → retard de retour ───────────────────────────
            (arch2, [sco2, sco3],
             'RAPPEL — Documents physiques empruntés non retournés',
             'Messieurs, Mesdames,\n\n'
             'Nos registres indiquent que les documents suivants n\'ont pas été retournés dans les délais :\n\n'
             '  • Dossier académique DIALLO Mamadou (Promo 2021) — emprunté depuis 28 jours\n'
             '  • PV jury Promo 2024 — emprunté depuis 21 jours\n\n'
             'Merci de les restituer avant vendredi 14 mars 2026, faute de quoi une pénalité sera signalée à la CSA.\n\n'
             'Moussa FALL — Archiviste',
             None, None, False),

            (sco2, [arch2],
             'RE: Retour documents — Explication',
             'Monsieur FALL,\n\n'
             'Je suis désolé pour ce retard. Le dossier DIALLO est nécessaire pour une vérification de diplôme demandée par un employeur. Je vous le rapporte lundi au plus tard.\n\n'
             'Ousmane GUEYE — Scolarité',
             None, 16, True),

            # ── Fil 10 : Inter-services CF / CM ───────────────────────────────
            (cf2, [cm1, cm1],
             'Demande de clarification — Imputation dépenses matériel 2025',
             'Madame CISSÉ,\n\n'
             'Pourriez-vous me confirmer l\'imputation budgétaire correcte pour l\'acquisition de 3 armoires fortes destinées aux archives ? Est-ce que cela doit passer en équipements (Comptabilité des Matières) ou en fournitures de bureau (Comptabilité Financière) ?\n\n'
             'Merci,\nNdèye DIOP — CF',
             None, None, False),

            (cm1, [cf2],
             'RE: Imputation armoires fortes',
             'Madame DIOP,\n\n'
             'Les armoires fortes constituent des immobilisations (valeur > 50 000 FCFA l\'unité) — elles relèvent donc de la Comptabilité des Matières. Merci de me transmettre le bon de livraison et la facture pour mise à jour de l\'inventaire.\n\n'
             'Mariama CISSÉ — CM',
             None, 18, True),
        ]

        nb = 0
        created_msgs = []
        for i, (exp, dests, objet, corps, doc_lie, parent_idx, lu_par_dest) in enumerate(MESSAGES):
            if Message.objects.filter(objet=objet, expediteur=exp).exists():
                m = Message.objects.get(objet=objet, expediteur=exp)
                created_msgs.append(m)
                nb += 1
                continue

            parent = created_msgs[parent_idx] if parent_idx is not None and parent_idx < len(created_msgs) else None

            m = Message.objects.create(
                expediteur = exp,
                objet      = objet,
                corps      = corps,
                document   = doc_lie,
                parent     = parent,
            )
            created_msgs.append(m)

            for dest in dests:
                if dest == exp:
                    continue
                MessageDestinataire.objects.get_or_create(
                    message      = m,
                    destinataire = dest,
                    defaults     = {
                        'lu': lu_par_dest,
                        'date_lecture': timezone.now() - timedelta(days=random.randint(0, 5)) if lu_par_dest else None,
                        'en_corbeille': False,
                    }
                )
            nb += 1
            self.log(f'    ✉ [{exp.username}→{",".join(d.username for d in dests[:2])}{"…" if len(dests)>2 else ""}] {objet[:55]}')

        self.stdout.write(self.style.SUCCESS(f'   ✓ {nb} message(s).\n'))

    # ── RÉCAP FINAL ───────────────────────────────────────────────────────────

    def _afficher_recap(self, users, docs):
        from archives.models import (
            DepotDocument, DemandePret, PretDocument, DemandeRecherche,
            RetentionJuridique, AuditToken, AccesDocument, VerificationIntegrite,
            MouvementDocument, Notification,
        )
        docs_actifs      = Document.objects.filter(deleted_at__isnull=True)
        courriers_actifs = Courrier.objects.filter(deleted_at__isnull=True)

        self.stdout.write(self.style.SUCCESS(
            '\n╔══════════════════════════════════════════════════════════╗\n'
            '║            ✅  BASE DE DONNÉES PEUPLÉE                   ║\n'
            '╠══════════════════════════════════════════════════════════╣\n'
        ))
        stats = [
            ('Utilisateurs',                    CustomUser.objects.count()),
            ('Documents actifs',                docs_actifs.count()),
            ('Documents en corbeille',          Document.objects.filter(deleted_at__isnull=False).count()),
            ('  → COURANT',                     docs_actifs.filter(statut='COURANT').count()),
            ('  → INTERMÉDIAIRE',               docs_actifs.filter(statut='INTERMEDIAIRE').count()),
            ('  → DÉFINITIF',                   docs_actifs.filter(statut='DEFINITIF').count()),
            ('  → DUA échue',                   docs_actifs.filter(date_fin_dua__lt=date.today()).count()),
            ('Dépôts',                          DepotDocument.objects.count()),
            ('  → En attente',                  DepotDocument.objects.filter(statut='EN_ATTENTE').count()),
            ('Demandes de prêt',                DemandePret.objects.count()),
            ('Prêts physiques',                 PretDocument.objects.count()),
            ('  → En cours / retard',           PretDocument.objects.filter(statut='EN_COURS').count()),
            ('Demandes de recherche',           DemandeRecherche.objects.count()),
            ('Bordereaux de versement',         BordereauVersement.objects.count()),
            ('Bordereaux d\'élimination',       BordereauElimination.objects.count()),
            ('Rétentions juridiques',           RetentionJuridique.objects.count()),
            ('  → Actives',                     RetentionJuridique.objects.filter(active=True).count()),
            ('Tokens d\'audit',                 AuditToken.objects.count()),
            ('Accès ABAC',                      AccesDocument.objects.count()),
            ('Vérifications d\'intégrité',      VerificationIntegrite.objects.count()),
            ('  → Alertes (ECHOUE)',             VerificationIntegrite.objects.filter(resultat='ECHOUE').count()),
            ('Mouvements d\'audit',             MouvementDocument.objects.count()),
            ('Notifications',                   Notification.objects.count()),
            ('  → Non lues',                    Notification.objects.filter(lue=False).count()),
            ('Courriers actifs',                courriers_actifs.count()),
            ('  → Arrivée',                     courriers_actifs.filter(sens='ARRIVEE').count()),
            ('  → Départ',                      courriers_actifs.filter(sens='DEPART').count()),
            ('  → En traitement',               courriers_actifs.filter(statut='EN_TRAITEMENT').count()),
            ('  → En retard',                   sum(1 for c in courriers_actifs if c.est_en_retard)),
            ('BV courriers',                    BordereauVersementCourrier.objects.count()),
            ('BE courriers',                    BordereauEliminationCourrier.objects.count()),
            ('Messages internes',               Message.objects.count()),
            ('  → Non lus',                     MessageDestinataire.objects.filter(lu=False, en_corbeille=False).count()),
        ]
        for label, val in stats:
            self.stdout.write(f'║  {label:<38} {str(val):>5}  ║')

        self.stdout.write(
            '╠══════════════════════════════════════════════════════════╣\n'
            '║  COMPTES DE TEST (mot de passe : passer01)               ║\n'
            '╠══════════════════════════════════════════════════════════╣\n'
            '║  admin.sys   → ADMIN / Django admin                      ║\n'
            '║  directeur   → DIRECTION — Directeur Général             ║\n'
            '║  csa         → DIRECTION — Chef des Services Admin.      ║\n'
            '║  archiviste1 → ARCHIVISTE — Service des Archives         ║\n'
            '║  archiviste2 → ARCHIVISTE — Service des Archives         ║\n'
            '║  cf1         → PERSONNEL  — Comptabilité Financière      ║\n'
            '║  cm1         → PERSONNEL  — Comptabilité des Matières    ║\n'
            '║  rh1         → PERSONNEL  — Ressources Humaines          ║\n'
            '║  sco1        → PERSONNEL  — Scolarité                    ║\n'
            '║  sec1        → PERSONNEL  — Secrétariat                  ║\n'
            '╠══════════════════════════════════════════════════════════╣\n'
            '║  URL : http://127.0.0.1:8000/                            ║\n'
            '╚══════════════════════════════════════════════════════════╝\n'
        )
