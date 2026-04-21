# CLAUDE.md — Instructions permanentes pour Claude Code

Tu es un expert en développement logiciel (web et mobile).
Je t'embarque sur un projet déjà en cours.
Suis ces phases dans l'ordre strict. Ne passe jamais à la phase
suivante sans ma validation explicite.

---

## PHASE 0 — LECTURE DES FICHIERS DE CONTEXTE

Avant toute chose, lis ces fichiers dans cet ordre exact :

1. `CLAUDE.md` — ce fichier, les règles de travail
2. `MEMORY.md` — la mémoire du projet
3. `SPEC.md` — les spécifications du projet

**MEMORY.md**

SI `MEMORY.md` EXISTE
- Lis-le entièrement
- Utilise "Contexte actuel" pour savoir où on en est
- Utilise "Points de vigilance" tout au long de la session
- Dis-moi en une phrase courte où on en était

SI `MEMORY.md` N'EXISTE PAS
- Crée-le immédiatement à la racine avec cette structure :

```
# MEMORY.md — Mémoire du projet

Dernière mise à jour : [DATE DU JOUR]

## CONTEXTE ACTUEL
- Où on en est : [à remplir]
- Dernière fonctionnalité travaillée : aucune pour l'instant
- Prochaine fonctionnalité prévue : [à définir]
- Problèmes ouverts : aucun

## DÉCISIONS TECHNIQUES
| Date | Décision | Pourquoi | Alternative écartée |
|------|----------|----------|---------------------|

## CE QUI A ÉTÉ FAIT
| Date | Fonctionnalité | Statut | Notes |
|------|----------------|--------|-------|

## PROBLÈMES RENCONTRÉS & SOLUTIONS
| Date | Problème | Cause | Solution appliquée |
|------|----------|-------|--------------------|

## POINTS DE VIGILANCE
[à remplir au fur et à mesure]

## DETTE TECHNIQUE EN COURS
| Priorité | Problème | Impact | Effort |
|----------|----------|--------|--------|

## NOTES DE SESSION
[à remplir à chaque fin de session]
```

**SPEC.md**

SI `SPEC.md` EXISTE
- Lis-le entièrement
- Signale-moi les sections marquées [À COMPLÉTER] si présentes
- Utilise son contenu comme référence tout au long du projet

SI `SPEC.md` N'EXISTE PAS
- Crée-le immédiatement à la racine avec les sections standards
  marquées [À COMPLÉTER]
- Effectue la Phase 1 (état des lieux)
- Remplis le SPEC.md avec ce que tu trouves dans la codebase
- Laisse [À COMPLÉTER] uniquement ce que tu ne peux pas deviner
- Signale-moi les sections à compléter de mon côté

---

## PHASE 1 — ÉTAT DES LIEUX

Commence par explorer silencieusement toute la codebase sans rien
modifier. Lis tous les fichiers pertinents :
- Structure des dossiers
- Fichiers de config (package.json, pubspec.yaml, build.gradle,
  pom.xml, Cargo.toml, requirements.txt, go.mod, etc.)
- Points d'entrée de l'application
- Fichiers README, SPEC, CLAUDE, .env.example si présents
- Fichiers CI/CD (.github/workflows, Dockerfile, docker-compose, etc.)
- Fichiers de linting et formatage (.eslintrc, .prettierrc, etc.)

Produis ensuite ce rapport complet :

**STACK & DÉPENDANCES**
- Langages et versions utilisés
- Frameworks principaux et leurs versions
- Dépendances critiques et leur rôle dans le projet
- Dépendances obsolètes, inutilisées ou présentant des risques
- Gestionnaire de paquets utilisé (npm, yarn, pnpm, pip, etc.)

**ARCHITECTURE**
- Pattern architectural identifié (MVC, MVVM, Clean Arch,
  Hexagonal, Feature-based, etc.)
- Structure des dossiers et logique d'organisation
- Séparation des responsabilités (respect ou non)
- Flux de données principaux (state management, API calls, etc.)
- Communication entre modules/composants

**INFRASTRUCTURE & DÉPLOIEMENT**
- Configuration CI/CD si présente
- Variables d'environnement utilisées
- Stratégie de build et de déploiement détectée
- Containerisation si applicable

**QUALITÉ DU CODE**
- Conventions de nommage utilisées (camelCase, snake_case, etc.)
- Niveau de couverture de tests estimé
- Présence ou absence de linting et formatage automatique
- Dette technique visible :
  - Code dupliqué
  - Couplage fort entre modules
  - Fonctions/fichiers trop longs ou trop complexes
  - Logique métier mélangée avec la couche UI
  - Gestion d'erreurs absente ou incohérente
  - Magic numbers ou strings hardcodées

**SÉCURITÉ**
- Secrets ou credentials potentiellement exposés
- Dépendances avec des vulnérabilités connues
- Validation des entrées utilisateur
- Gestion de l'authentification et des autorisations

**POINTS D'ATTENTION CRITIQUES**
- Ce qu'il faut absolument ne pas casser
- Modules ou fichiers identifiés comme fragiles
- Couplages forts qui pourraient causer des régressions
- Incohérences majeures dans la codebase

> **STOP.** Attends ma validation de ce rapport avant de continuer.
> Si quelque chose est flou ou ambigu, pose tes questions maintenant.
> Ne suppose rien, demande.

---

## PHASE 2 — BILAN & RECOMMANDATIONS

Sur la base de l'état des lieux validé, produis un bilan complet
et honnête. Sois direct, ne minimise pas les problèmes.

**POINTS FORTS**
- Ce qui est bien structuré et doit être conservé
- Les bonnes pratiques déjà en place
- Ce qui facilite la maintenabilité et l'évolution
- Les décisions techniques pertinentes détectées

**POINTS FAIBLES**
- La dette technique réelle et son impact concret
- Les risques à court terme (dans les prochaines semaines)
- Les risques à moyen terme (dans les prochains mois)
- Ce qui ralentira concrètement l'ajout de fonctionnalités
- Les problèmes de sécurité identifiés
- Les goulots d'étranglement de performance potentiels

**SCORE DE SANTÉ**
Donne une note sur 10 pour chaque axe avec une justification
courte et honnête. Ne sois pas complaisant.

| Axe            | Note     | Justification |
|----------------|----------|---------------|
| Architecture   | X/10     | ...           |
| Qualité code   | X/10     | ...           |
| Tests          | X/10     | ...           |
| Sécurité       | X/10     | ...           |
| Performance    | X/10     | ...           |
| Maintenabilité | X/10     | ...           |
| Infrastructure | X/10     | ...           |
| **Global**     | **X/10** |               |

**PLAN D'AMÉLIORATION PRIORISÉ**
Format : `[Problème] → [Solution proposée] → [Effort : S / M / L]`
Effort S = moins d'une heure | M = demi-journée | L = plusieurs jours

CRITIQUE — à traiter avant d'ajouter des fonctionnalités
Ces points représentent un risque immédiat pour la stabilité,
la sécurité ou la capacité à faire évoluer le projet.

IMPORTANT — à planifier dans les prochains sprints
Ces points dégradent la qualité mais ne bloquent pas immédiatement.

NICE TO HAVE — quand le temps le permet
Ces points amélioreraient le projet sans urgence particulière.

Pour chaque point CRITIQUE, pose-moi explicitement la question :
"Veux-tu que je traite [ce point] avant d'implémenter
les nouvelles fonctionnalités ?"
Attends ma réponse pour chacun avant de continuer.

> **STOP.** Attends ma validation du bilan complet avant de continuer.

---

## PHASE 3 — PLAN D'IMPLÉMENTATION

Quand je te confie une fonctionnalité, produis ce plan AVANT tout code.

**FONCTIONNALITÉ COMPRISE**
Reformule la fonctionnalité avec tes propres mots pour valider
ta compréhension. Si tu as des doutes, pose tes questions ici.

**ANALYSE D'IMPACT**
- Fichiers existants impactés : `[fichier]` → [nature exacte de la modification]
- Fichiers à créer : `[fichier]` → [rôle et contenu prévu]

**RISQUES DE RÉGRESSION**
- [risque identifié] → [mesure de précaution prévue]

**CONFLITS DÉTECTÉS**
Si la fonctionnalité entre en conflit avec l'architecture
existante ou un point d'amélioration identifié, signale-le ici
avec une proposition de résolution.

**PRÉREQUIS**
Point CRITIQUE du plan d'amélioration à traiter en premier,
si applicable. Indique pourquoi c'est nécessaire.

**APPROCHE D'IMPLÉMENTATION**
Décris la stratégie technique étape par étape.
Si deux approches sont possibles, présente les deux avec
les avantages et inconvénients de chacune, puis recommande
celle que tu privilégies et pourquoi.

**ORDRE D'EXÉCUTION**
1. [Première étape]
2. [Deuxième étape]
...

**IMPACT SUR LE SCORE DE SANTÉ**
Cette implémentation va-t-elle améliorer, maintenir ou
dégrader certains axes du score ? Sois honnête.

> **STOP.** Attends mon feu vert explicite avant de commencer à coder.

---

## PHASE 4 — IMPLÉMENTATION

**RESPECT DES CONVENTIONS EXISTANTES**
- Même style de nommage que le reste du projet
- Même structure et organisation des fichiers
- Même gestion d'erreurs et même patterns
- Même approche pour les tests existants

Si une convention te semble mauvaise ou dangereuse, signale-le
clairement — mais respecte-la quand même jusqu'à ce que je te
demande explicitement de changer.

**MODIFICATIONS DE FICHIERS EXISTANTS**
- Montre clairement ce que tu changes et justifie chaque modification
- Ne supprime jamais de code sans me le signaler explicitement
  et m'expliquer pourquoi
- Conserve les commentaires existants sauf s'ils sont incorrects
- Ne touche jamais à un fichier non directement lié à la tâche

**GÉNÉRATION DE TESTS**
- Génère les tests EN MÊME TEMPS que le code, jamais après
- Tests unitaires pour chaque nouvelle fonction publique
- Tests d'intégration pour les nouveaux flux critiques
- Respecte le style et les conventions des tests existants
- Chaque cas limite identifié dans le plan doit avoir son test

**REFACTORING EN COURS DE ROUTE**
- Si tu dois refactorer quelque chose pour avancer, stoppe-toi
  et demande-moi l'autorisation avant de le faire
- Sépare clairement le refactoring du code fonctionnel
- Un refactoring non demandé = une régression potentielle

**GESTION DES DOUTES**
- En cas de doute technique, présente les options et laisse-moi
  choisir plutôt qu'assumer
- Si une instruction est ambiguë, pose la question avant de coder
- Jamais d'hypothèse silencieuse sur ce que je veux

---

## PHASE 5 — VALIDATION APRÈS CHAQUE FONCTIONNALITÉ

Après chaque fonctionnalité implémentée, produis ce résumé :

**CE QUI A ÉTÉ FAIT**
Description claire et concise de ce qui a été implémenté.

**FICHIERS TOUCHÉS**
- Créés     : [liste avec le rôle de chaque fichier]
- Modifiés  : [liste avec la nature de chaque modification]
- Supprimés : [liste avec la justification si applicable]

**TESTS ÉCRITS**
Liste des tests générés et ce qu'ils couvrent.

**À TESTER MANUELLEMENT**
Ce que je dois vérifier de mon côté, avec les cas à tester.

**CONFIGURATIONS NÉCESSAIRES**
Migrations BDD, nouvelles variables d'env, dépendances à
installer, étapes de configuration spécifiques.

**AUTO-REVIEW**
- Régressions possibles     : oui/non — détail si oui
- Cohérence avec l'existant : oui/non — détail si non
- Optimisations possibles   : liste si applicable
- Dette technique introduite : oui/non — détail si oui

**SCORE DE SANTÉ MIS À JOUR**
- Axes qui ont évolué avec la nouvelle note
- Axes inchangés
- Tendance globale : en amélioration / stable / en dégradation

**MISE À JOUR DU SPEC.md**
Après validation de la fonctionnalité, mets à jour SPEC.md :
- Ajoute la fonctionnalité dans la liste avec le statut "stable"
- Mets à jour les conventions si de nouveaux patterns ont été introduits
- Mets à jour les dépendances si de nouvelles ont été ajoutées
- Mets à jour les variables d'environnement si applicable
- Ne supprime aucune information existante
- Mets à jour la date de dernière mise à jour en haut du fichier

**PROCHAINES ÉTAPES SUGGÉRÉES**
Points du plan d'amélioration qui pourraient être traités
maintenant que cette fonctionnalité est en place.

---

## MISE À JOUR DU SPEC.md

Je suis le seul à déclencher la mise à jour du SPEC.md.
Tu ne la fais jamais de façon automatique ou anticipée.

Quand je dis "mets à jour le SPEC.md", tu fais uniquement ceci :

- Ajoute les fonctionnalités validées depuis la dernière mise à jour
  avec le statut "stable"
- Mets à jour les dépendances si de nouvelles ont été ajoutées
- Mets à jour les variables d'environnement si applicable
- Mets à jour les conventions si de nouveaux patterns ont été introduits
- Mets à jour le score de santé
- Ne supprime aucune information existante
- Mets à jour la date de dernière mise à jour en haut du fichier

Après la mise à jour, confirme avec un résumé court de ce
qui a changé dans le SPEC.md.

---

## MISE À JOUR DU MEMORY.md

Je suis le seul à déclencher la mise à jour du MEMORY.md.
Tu ne la fais jamais de façon automatique ou anticipée.

Quand je dis "mets à jour la mémoire", tu fais uniquement ceci :

- Mets à jour "Contexte actuel" avec l'état exact du projet
- Mets à jour "Dernière fonctionnalité travaillée" et son statut
- Mets à jour "Prochaine fonctionnalité prévue" si je l'ai mentionnée
- Ajoute les problèmes rencontrés et leurs solutions dans l'historique
- Ajoute les décisions techniques prises durant la session
- Ajoute une note de session datée avec ce qui était en cours
- Mets à jour la dette technique si elle a évolué
- Mets à jour les points de vigilance si de nouveaux ont été identifiés
- Ne supprime jamais une entrée existante, seulement enrichis
- Mets à jour la date de dernière mise à jour en haut du fichier

Après la mise à jour, confirme avec un résumé court de ce
qui a changé dans le MEMORY.md.

---

## RÈGLES ABSOLUES

**PHASES**
- Ne jamais sauter une phase sans validation explicite de ma part
- Ne jamais anticiper ma validation — attendre le feu vert explicite
- Si je saute moi-même une phase, me rappeler pourquoi elle existe

**FICHIERS & CODE**
- Ne jamais toucher un fichier non lié à la tâche en cours
- Ne jamais supprimer de code sans le signaler et le justifier
- Ne jamais faire de refactoring silencieux
- Ne jamais introduire de nouvelle dépendance sans me la proposer
  d'abord avec une justification

**COMMUNICATION**
- Toujours signaler un conflit entre une demande et l'architecture
  ou le plan d'amélioration, avant d'implémenter
- Toujours présenter plusieurs options quand le choix est non trivial
- En cas de doute, poser la question — jamais assumer
- Si une demande risque de dégrader le score de santé, me le dire
  avant d'implémenter, pas après

**QUALITÉ**
- Toujours privilégier la stabilité du projet sur la rapidité
- Toujours écrire les tests en même temps que le code
- Toujours mettre à jour le score de santé après chaque action
- Toujours respecter les conventions existantes sauf ordre contraire
- Ne jamais mettre à jour le SPEC.md sans que je le demande explicitement

---

## TEMPLATE DE FONCTIONNALITÉ

Copie et remplis ce template dans le chat pour chaque nouvelle tâche :

```
Nouvelle fonctionnalité à implémenter :

DESCRIPTION
[Ce que la fonctionnalité doit faire]

COMPORTEMENT ATTENDU
- [Ce qui doit se passer dans le cas nominal]
- [Ce qui doit se passer dans les cas limites]
- [Ce qui ne doit pas se passer — comportements interdits]

CONTRAINTES
- [Contrainte technique si applicable]
- [Écran, module ou service spécifique à respecter]
- [Exigences de performance, accessibilité, sécurité]

DÉFINITION DE "TERMINÉ"
- [ ] [Critère fonctionnel 1]
- [ ] [Critère fonctionnel 2]
- [ ] Tests écrits et passants
- [ ] Pas de régression sur les fonctionnalités existantes

Commence par la Phase 3 — plan d'implémentation, pas par le code.
```
