"""
Couche service — logique métier du système d'archives ENSMG.

Principe : les modèles ne contiennent que la structure des données.
Toute règle métier (calcul, validation, workflow) passe par ces services.
Cela rend la logique testable indépendamment de la couche ORM.
"""

import hashlib
import uuid

from django.utils import timezone


class DocumentService:
    """
    Regroupe toutes les règles métier liées au cycle de vie d'un Document.
    Méthodes statiques : pas d'état, appelables depuis n'importe quel contexte.
    """

    @staticmethod
    def generer_identifiant(date_creation, categorie) -> str:
        """
        Génère l'identifiant pérenne au format ENSMG-AAAA-CODE-XXXXXXXX.
        L'identifiant est immuable une fois attribué (critère légal ISO 15489).
        """
        annee    = date_creation.year if date_creation else timezone.now().year
        code_cat = categorie.code if categorie else 'GEN'
        uid      = uuid.uuid4().hex[:8].upper()
        return f"ENSMG-{annee}-{code_cat}-{uid}"

    @staticmethod
    def calculer_date_fin_dua(date_creation, tableau_gestion):
        """
        Calcule la date d'échéance DUA à partir de la date de création et du tableau de gestion.
        Gère le cas du 29 février lors d'un dépassement d'année non bissextile.
        Retourne None si les données sont insuffisantes.
        """
        if not tableau_gestion or not date_creation:
            return None
        duree = tableau_gestion.duree_totale
        try:
            return date_creation.replace(year=date_creation.year + duree)
        except ValueError:
            return date_creation.replace(year=date_creation.year + duree, day=28)

    @staticmethod
    def calculer_sha256(fichier) -> str:
        """
        Calcule l'empreinte SHA-256 d'un fichier Django.
        Lit par chunks pour les gros fichiers (cartes géologiques, jusqu'à 500 Mo).
        Retourne une chaîne vide si le calcul échoue.
        """
        try:
            sha256 = hashlib.sha256()
            fichier.seek(0)
            for chunk in iter(lambda: fichier.read(65536), b''):
                sha256.update(chunk)
            fichier.seek(0)
            return sha256.hexdigest()
        except Exception:
            return ''

    @staticmethod
    def traiter_metadonnees_fichier(document) -> None:
        """
        Met à jour les métadonnées du fichier numérique sur un Document :
        - empreinte SHA-256 (intégrité)
        - taille_fichier
        - nom_fichier_original

        N'est appelé que si le fichier a changé (optimisation C3).
        Modifie l'objet en place sans le sauvegarder.
        """
        if not document.fichier:
            return
        document.empreinte_sha256     = DocumentService.calculer_sha256(document.fichier)
        document.taille_fichier       = document.fichier.size
        document.nom_fichier_original = document.fichier.name.split('/')[-1]

    @staticmethod
    def preparer_sauvegarde(document) -> None:
        """
        Point d'entrée unique appelé par Document.save().
        Applique dans l'ordre :
          1. Génération de l'identifiant pérenne (si absent)
          2. Calcul de la date de fin de DUA (si absente)
          3. Calcul SHA-256 et métadonnées (si fichier ajouté ou remplacé)
        """
        # 1. Identifiant pérenne — ne génère qu'une seule fois
        if not document.identifiant:
            document.identifiant = DocumentService.generer_identifiant(
                document.date_creation, document.categorie if document.categorie_id else None
            )

        # 2. Date de fin de DUA — calcule uniquement si absente
        if document.tableau_gestion and document.date_creation and not document.date_fin_dua:
            document.date_fin_dua = DocumentService.calculer_date_fin_dua(
                document.date_creation, document.tableau_gestion
            )

        # 3. SHA-256 — calcule si le fichier a été ajouté ou remplacé
        if document.fichier and document._fichier_a_change():
            DocumentService.traiter_metadonnees_fichier(document)


class DepotDocumentService:
    """
    Règles métier pour le circuit de dépôt agent → archiviste.
    """

    @staticmethod
    def generer_numero_recepisse(categorie_code: str = 'DOC') -> str:
        """
        Génère le numéro de récépissé au format DEP-AAAA-CODE-XXXXXX.
        """
        annee = timezone.now().year
        uid   = uuid.uuid4().hex[:6].upper()
        return f"DEP-{annee}-{categorie_code}-{uid}"
