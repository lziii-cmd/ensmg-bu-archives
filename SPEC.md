# SPEC.md — Spécifications du projet ENSMG Archives

Dernière mise à jour : 2026-04-21
Version : 1.0 (générée depuis état des lieux codebase)

---

## 1. PRÉSENTATION DU PROJET

**Nom** : Système de Gestion des Archives de l'ENSMG (École Nationale des Sciences et Mesures Géologiques)
**Contexte** : Application web de gestion électronique des archives institutionnelles, conforme aux normes archivistiques internationales (ISO 15489) et à la législation sénégalaise (Loi 2006-19).
**Stack** : Django 5.0.6 / Python 3.x / SQLite (dev) → PostgreSQL (prod)

---

## 2. RÔLES ET UTILISATEURS

| Rôle | Code | Description |
|------|------|-------------|
| Administrateur | ADMIN | Accès total, gestion utilisateurs |
| Archiviste | ARCHIVISTE | Traitement archives, validation dépôts, gestion prêts |
| Direction | DIRECTION | Accès documents confidentiels, validation éliminations |
| Personnel | PERSONNEL | Dépôt documents, demandes de prêt |
| Enseignant | ENSEIGNANT | Dépôt documents, demandes de prêt |

---

## 3. MODULES FONCTIONNELS

### 3.1 Gestion des Documents
- **Statut** : stable
- Création/modification de documents avec identifiant pérenne (ENSMG-YYYY-CODE-XXXXXXXX)
- Support multi-formats : numérique (fichiers) + papier (localisation physique)
- 7 niveaux de statut : COURANT → INTERMEDIAIRE → DEFINITIF → EN_VERSEMENT → VERSE → EN_ELIMINATION → ELIMINE
- 4 niveaux de confidentialité : PUBLIC, INTERNE, CONFIDENTIEL, SECRET
- Soft delete avec purge automatique 30 jours

### 3.2 Plan de Classement
- **Statut** : stable
- Arborescence hiérarchique à 4 niveaux : FONDS > SÉRIE > SOUS-SÉRIE > DOSSIER
- Codes de classification (ex: F1.S1.1)
- 8 catégories : ADM, PED, SCI, GEO, TER, PAR, FRH, PAT

### 3.3 DUA — Durée d'Utilité Administrative
- **Statut** : stable
- Tableau de gestion (durée courante + intermédiaire)
- Sort final : CONSERVATION | ELIMINATION | TRI
- Calcul automatique date_fin_dua à l'enregistrement
- Commande management `check_dua` pour alertes

### 3.4 Circuit de Dépôt
- **Statut** : stable
- Dépôt simplifié par les agents (avec récépissé DEP-YYYY-CODE-XXXXXX)
- File de traitement archiviste
- Workflow : EN_ATTENTE → ARCHIVE | REJETE
- Provenance interne (service ENSMG) ou externe (référentiel contrôlé)

### 3.5 Gestion des Prêts
- **Statut** : stable
- Demandes d'accès numérique ou physique
- Bons de prêt numérotés (BON-YYYY-XXXXXX)
- Accès temporaire (AccesDocument avec date_fin)
- Suivi retours et retards

### 3.6 Versements et Éliminations
- **Statut** : stable
- Bordereaux de versement aux Archives nationales du Sénégal
- Bordereaux d'élimination avec visa obligatoire DAS
- Gestion par exercice budgétaire

### 3.7 Audit Trail
- **Statut** : stable
- Journal immuable (MouvementDocument) — 10 types d'actions
- Traçabilité IP, utilisateur, avant/après (JSONField)
- Tokens d'audit temporaires

### 3.8 Messagerie Interne
- **Statut** : stable
- Messages entre utilisateurs avec fils de discussion
- Corbeille, état lu/non-lu

### 3.9 Module Courrier
- **Statut** : stable
- Réception et distribution de courriers entrants
- Bordereaux versement/élimination pour courriers

### 3.10 Notifications
- **Statut** : stable
- 12 types d'événements
- Notifications in-app (pas d'email pour l'instant)

### 3.11 Recherche Documentaire
- **Statut** : stable (partiel)
- Recherche par titre, mots-clés, catégorie, dates, statut
- Demandes de recherche agent → archiviste
- ⚠️ texte_extrait (OCR/full-text) non implémenté

---

## 4. PERMISSIONS (RBAC/ABAC)

### Matrice des rôles
| Action | ADMIN | ARCHIVISTE | DIRECTION | PERSONNEL | ENSEIGNANT |
|--------|-------|-----------|-----------|-----------|-----------|
| Créer document | ✅ | ✅ | ✅ | ❌ (dépôt) | ❌ (dépôt) |
| Voir CONFIDENTIEL | ✅ | ✅ | ✅ | ❌ | ❌ |
| Voir SECRET | ✅ | ✅ | ✅ | ❌ | ❌ |
| Valider dépôt | ✅ | ✅ | ❌ | ❌ | ❌ |
| Éliminer | ✅ | ✅ | ✅ | ❌ | ❌ |
| Verser | ✅ | ✅ | ❌ | ❌ | ❌ |
| Gestion utilisateurs | ✅ | ❌ | ❌ | ❌ | ❌ |

### ABAC (AccesDocument)
- Accès individuel par document, indépendant du rôle
- Durée limitée (24h par défaut pour numérique)
- Types : LECTURE | TELECHARGEMENT

---

## 5. ARCHITECTURE TECHNIQUE

### Stack
- **Backend** : Django 5.0.6, Python 3.x
- **BD DEV** : SQLite 3
- **BD PROD** : PostgreSQL (psycopg2-binary 2.9.11) [À CONFIGURER]
- **Serveur PROD** : Gunicorn 25.1.0
- **PDF** : WeasyPrint 68.1 + ReportLab 4.4.3
- **Images** : Pillow 11.3.0
- **Config** : python-decouple 3.8
- **Timezone** : Africa/Dakar (tzdata 2025.2)
- **API** : DRF 3.16.1 (présent, partiellement utilisé)

### Conventions de nommage
- Python : snake_case
- Modèles Django : PascalCase
- Constantes/Choix : MAJUSCULE
- URLs : kebab-case
- Templates : snake_case.html

### Organisation des apps
- `users/` — Authentification, rôles, départements
- `archives/` — Logique métier principale (documents, prêts, bordereaux, messagerie, courriers)
- `ensmg_bu_archives_project/` — Configuration Django

### Pattern architecture actuel
- MVC Django standard
- Permissions centralisées dans `archives/permissions.py`
- Logique métier partiellement dans les `save()` (dette technique)
- Pas encore de couche services/sélecteurs (à créer)

---

## 6. VARIABLES D'ENVIRONNEMENT

| Variable | Valeur DEV | Description |
|----------|-----------|-------------|
| SECRET_KEY | django-insecure-... ⚠️ | Clé secrète Django |
| DEBUG | True | Mode debug |
| ALLOWED_HOSTS | * | Hosts autorisés |
| DATABASE_URL | sqlite:///db.sqlite3 | Connexion BD |
| MEDIA_ROOT | ./media | Stockage fichiers |

**[À COMPLÉTER]** — Créer `.env.example` et migrer settings.py vers python-decouple

---

## 7. SCORE DE SANTÉ INITIAL

| Axe | Note | Justification |
|-----|------|---------------|
| Architecture | 6/10 | Modèles excellents, mais pas de couche services |
| Qualité code | 6/10 | Code lisible, conventions respectées, magic strings |
| Tests | 1/10 | 0% coverage, aucun test automatisé |
| Sécurité | 4/10 | SECRET_KEY en dur, DEBUG=True, ALLOWED_HOSTS=* |
| Performance | 5/10 | SQLite OK dev, SHA-256 dans save() coûteux |
| Maintenabilité | 6/10 | Bonne structure, manque services et tests |
| Infrastructure | 3/10 | Pas de Docker, CI/CD, .env |
| **Global** | **4.4/10** | Solide fonctionnellement, fragile opérationnellement |

---

## 8. FONCTIONNALITÉS À VENIR

**[À COMPLÉTER]** — À renseigner avec les nouvelles fonctionnalités planifiées

---

## 9. CONFORMITÉ LÉGALE

- **ISO 15489** : Gestion des documents d'activité — ✅ partiellement conforme
- **Loi sénégalaise 2006-19** : Élimination avec visa DAS — ✅ implémenté
- **RGPD / protection données personnelles** : [À COMPLÉTER]
- **Archives nationales Sénégal** : Versements via bordereaux — ✅ implémenté
