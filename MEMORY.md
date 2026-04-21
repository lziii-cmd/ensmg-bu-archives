# MEMORY.md — Mémoire du projet

Dernière mise à jour : 2026-04-21 (session 2)

## CONTEXTE ACTUEL
- Où on en est : Phases 0-5 complétées et validées. 6 points critiques traités.
- Dernière fonctionnalité travaillée : Refactoring sécurité + architecture + tests + Docker/CI
- Prochaine fonctionnalité prévue : à définir par l'utilisateur
- Problèmes ouverts : dettes IMPORTANT/NICE restantes (voir tableau)

## DÉCISIONS TECHNIQUES
| Date | Décision | Pourquoi | Alternative écartée |
|------|----------|----------|---------------------|
| 2026-04-21 | Lancement protocole CLAUDE_NEW.md | Structurer le travail en phases avec validation | Travail ad-hoc sans phases |
| 2026-04-21 | DocumentService comme couche service | Logique métier testable hors ORM | Signals Django (plus implicites) |
| 2026-04-21 | _fichier_a_change() via __init__ tracking | Éviter recalcul SHA-256 inutile sur gros fichiers | django-model-utils FieldTracker (dépendance externe) |
| 2026-04-21 | Migration 0008 doublon → renommée 0014 | Chaîne de migration propre sans casser l'état appliqué | Merge migration (plus complexe) |

## CE QUI A ÉTÉ FAIT
| Date | Fonctionnalité | Statut | Notes |
|------|----------------|--------|-------|
| 2026-04-21 | Exploration complète codebase | Stable | 88 fichiers Python, 14 migrations, 0 tests |
| 2026-04-21 | C1 — Sécurisation config (.env + python-decouple) | Stable | SECRET_KEY, DEBUG, ALLOWED_HOSTS externalisés |
| 2026-04-21 | C2 — Correction doublon migration 0008 | Stable | Renommée 0014, dépendance corrigée, appliquée |
| 2026-04-21 | C3 — Optimisation SHA-256 | Stable | Ne recalcule que si fichier changé (_fichier_a_change) |
| 2026-04-21 | C4 — Couche DocumentService | Stable | archives/services.py, Document.save() délègue au service |
| 2026-04-21 | C5 — Tests unitaires (43 tests) | Stable | archives/tests/ — services + permissions, 43/43 OK |
| 2026-04-21 | C6 — Docker + CI/CD GitHub Actions | Stable | Dockerfile, docker-compose.yml, .github/workflows/ci.yml |

## PROBLÈMES RENCONTRÉS & SOLUTIONS
| Date | Problème | Cause | Solution appliquée |
|------|----------|-------|--------------------|

## POINTS DE VIGILANCE
- Deux migrations 0008 (alter_notification + document_corbeille) — conflits possibles à surveiller
- SECRET_KEY codée en dur dans settings.py — ne jamais commiter une vraie clé
- Logique métier dans save() (Document, DepotDocument) — modifier avec précaution
- Document.identifiant est pérenne (critère légal) — ne jamais changer la logique de génération
- MouvementDocument est immuable (audit légal) — ne jamais ajouter update/delete

## DETTE TECHNIQUE EN COURS
| Priorité | Problème | Impact | Effort | Statut |
|----------|----------|--------|--------|--------|
| ~~CRITIQUE~~ | ~~SECRET_KEY codée en dur~~ | — | — | ✅ Résolu |
| ~~CRITIQUE~~ | ~~DEBUG=True + ALLOWED_HOSTS=*~~ | — | — | ✅ Résolu |
| ~~CRITIQUE~~ | ~~Logique métier dans save()~~ | — | — | ✅ Résolu |
| ~~CRITIQUE~~ | ~~Aucun test unitaire~~ | — | — | ✅ 43 tests |
| ~~CRITIQUE~~ | ~~Pas de Docker / CI-CD~~ | — | — | ✅ Résolu |
| IMPORTANT | Magic strings répétées | Maintenance difficile | S | En attente |
| IMPORTANT | Couplage vues ← modèles (vues monolithiques) | Non-testable | M | En attente |
| IMPORTANT | Pas de validation clean() dans forms.py | Données incohérentes | M | En attente |
| IMPORTANT | Pas d'intégration email pour notifications | Fonctionnalité incomplète | M | En attente |
| IMPORTANT | texte_extrait jamais populé (OCR absent) | Recherche plein texte inopérante | L | En attente |
| NICE | Pagination absente sur certaines listes | UX dégradée gros volumes | S | En attente |
| NICE | Pas de logging centralisé | Debug difficile en prod | M | En attente |
| NICE | Pas de cache Redis | Performance listes volumineuses | M | En attente |

## NOTES DE SESSION
### Session 2026-04-21
- Démarrage avec CLAUDE_NEW.md comme protocole de travail
- MEMORY.md et SPEC.md créés (inexistants au départ)
- État des lieux complet réalisé (88 fichiers, 14 migrations après correction)
- Phases 1-5 complétées et validées par l'utilisateur
- 6 points CRITIQUES traités : sécurité, migrations, SHA-256, services, tests, Docker/CI
- Score global passé de 4.4/10 → 6.25/10
- Prêt pour implémenter les nouvelles fonctionnalités
