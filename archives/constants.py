"""
archives/constants.py — Constantes métier centralisées.

Élimine les magic strings dupliqués entre forms.py, views.py et les templates.
Toute valeur codée en dur qui apparaît dans plusieurs fichiers doit figurer ici.
"""


class DecisionDepot:
    ARCHIVE = 'ARCHIVE'
    REJETE  = 'REJETE'
    CHOICES = [
        ('',       '---------'),
        (ARCHIVE,  'Archiver le document'),
        (REJETE,   'Rejeter le dépôt'),
    ]


class DecisionPret:
    ACCORDEE = 'ACCORDEE'
    REFUSEE  = 'REFUSEE'
    CHOICES  = [
        ('',       '---------'),
        (ACCORDEE, 'Accorder le prêt'),
        (REFUSEE,  'Refuser le prêt'),
    ]


class DecisionRecherche:
    ACCORDER = 'ACCORDER'
    REFUSER  = 'REFUSER'
    CHOICES  = [
        ('',       '---------'),
        (ACCORDER, 'Document trouvé — prêt accordé'),
        (REFUSER,  'Document non trouvé / refuser'),
    ]


class TypePret:
    PHYSIQUE  = 'PHYSIQUE'
    NUMERIQUE = 'NUMERIQUE'
    CHOICES   = [
        ('',        '---------'),
        (PHYSIQUE,  'Prêt physique (document papier)'),
        (NUMERIQUE, 'Accès numérique (téléchargement temporaire)'),
    ]


# Limites et durées par défaut
AUDIT_ACCES_MAX_DOCS       = 200
DUREE_ACCES_DEFAUT_HEURES  = 24
MOTIF_MIN_LENGTH           = 20
