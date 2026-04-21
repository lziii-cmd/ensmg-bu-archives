"""
Tests unitaires — DocumentService et DepotDocumentService.
Ces tests vérifient la logique métier indépendamment de la base de données.
"""

import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from archives.services import DocumentService, DepotDocumentService


class TestGenererIdentifiant(TestCase):

    def test_format_standard(self):
        date    = datetime.date(2024, 6, 15)
        categorie = MagicMock()
        categorie.code = 'ADM'
        identifiant = DocumentService.generer_identifiant(date, categorie)
        self.assertTrue(identifiant.startswith('ENSMG-2024-ADM-'))
        parties = identifiant.split('-')
        self.assertEqual(len(parties), 4)
        self.assertEqual(len(parties[3]), 8)

    def test_sans_categorie_utilise_gen(self):
        date        = datetime.date(2024, 1, 1)
        identifiant = DocumentService.generer_identifiant(date, None)
        self.assertIn('-GEN-', identifiant)

    def test_sans_date_utilise_annee_courante(self):
        identifiant = DocumentService.generer_identifiant(None, None)
        annee_courante = str(timezone.now().year)
        self.assertIn(annee_courante, identifiant)

    def test_unicite(self):
        date      = datetime.date(2024, 1, 1)
        categorie = MagicMock()
        categorie.code = 'SCI'
        ids = {DocumentService.generer_identifiant(date, categorie) for _ in range(100)}
        self.assertEqual(len(ids), 100)


class TestCalculerDateFinDua(TestCase):

    def _tableau(self, courante, intermediaire):
        t = MagicMock()
        t.duree_totale = courante + intermediaire
        return t

    def test_calcul_simple(self):
        date    = datetime.date(2020, 3, 15)
        tableau = self._tableau(5, 3)
        resultat = DocumentService.calculer_date_fin_dua(date, tableau)
        self.assertEqual(resultat, datetime.date(2028, 3, 15))

    def test_sans_tableau_retourne_none(self):
        date = datetime.date(2020, 1, 1)
        self.assertIsNone(DocumentService.calculer_date_fin_dua(date, None))

    def test_sans_date_retourne_none(self):
        tableau = self._tableau(5, 0)
        self.assertIsNone(DocumentService.calculer_date_fin_dua(None, tableau))

    def test_29_fevrier_annee_non_bissextile(self):
        # 2020 est bissextile, 2020 + 3 = 2023 ne l'est pas → doit donner le 28
        date    = datetime.date(2020, 2, 29)
        tableau = self._tableau(3, 0)
        resultat = DocumentService.calculer_date_fin_dua(date, tableau)
        self.assertEqual(resultat, datetime.date(2023, 2, 28))


class TestCalculerSha256(TestCase):

    def test_sha256_correct(self):
        import hashlib
        contenu = b'contenu de test pour les archives ENSMG'
        fichier = MagicMock()
        fichier.read.side_effect = [contenu, b'']
        empreinte = DocumentService.calculer_sha256(fichier)
        attendu = hashlib.sha256(contenu).hexdigest()
        self.assertEqual(empreinte, attendu)

    def test_erreur_retourne_chaine_vide(self):
        fichier = MagicMock()
        fichier.seek.side_effect = IOError('lecture impossible')
        empreinte = DocumentService.calculer_sha256(fichier)
        self.assertEqual(empreinte, '')


class TestPreparerSauvegarde(TestCase):

    def _document_minimal(self):
        """Crée un document mock avec les attributs minimaux."""
        doc = MagicMock()
        doc.identifiant       = ''
        doc.date_fin_dua      = None
        doc.empreinte_sha256  = ''
        doc.fichier           = None
        doc._fichier_a_change = MagicMock(return_value=False)

        cat = MagicMock()
        cat.code = 'ADM'
        doc.categorie     = cat
        doc.categorie_id  = 1
        doc.date_creation = datetime.date(2024, 1, 1)

        doc.tableau_gestion = None
        return doc

    def test_identifiant_genere_si_absent(self):
        doc = self._document_minimal()
        DocumentService.preparer_sauvegarde(doc)
        self.assertTrue(doc.identifiant.startswith('ENSMG-2024-ADM-'))

    def test_identifiant_non_ecrase_si_present(self):
        doc = self._document_minimal()
        doc.identifiant = 'ENSMG-2020-ADM-EXISTANT'
        DocumentService.preparer_sauvegarde(doc)
        self.assertEqual(doc.identifiant, 'ENSMG-2020-ADM-EXISTANT')

    def test_dua_calculee_si_tableau_present(self):
        doc = self._document_minimal()
        tableau = MagicMock()
        tableau.duree_totale = 10
        doc.tableau_gestion = tableau
        DocumentService.preparer_sauvegarde(doc)
        self.assertEqual(doc.date_fin_dua, datetime.date(2034, 1, 1))

    def test_sha256_calcule_si_fichier_change(self):
        doc = self._document_minimal()
        doc.fichier = MagicMock()
        doc.fichier.name  = 'rapport.pdf'
        doc.fichier.size  = 1024
        doc._fichier_a_change = MagicMock(return_value=True)
        with patch.object(DocumentService, 'traiter_metadonnees_fichier') as mock_traiter:
            DocumentService.preparer_sauvegarde(doc)
            mock_traiter.assert_called_once_with(doc)

    def test_sha256_non_recalcule_si_fichier_inchange(self):
        doc = self._document_minimal()
        doc.fichier = MagicMock()
        doc._fichier_a_change = MagicMock(return_value=False)
        with patch.object(DocumentService, 'traiter_metadonnees_fichier') as mock_traiter:
            DocumentService.preparer_sauvegarde(doc)
            mock_traiter.assert_not_called()


class TestDepotDocumentService(TestCase):

    def test_format_numero_recepisse(self):
        numero = DepotDocumentService.generer_numero_recepisse('ADM')
        annee  = str(timezone.now().year)
        self.assertTrue(numero.startswith(f'DEP-{annee}-ADM-'))
        self.assertEqual(len(numero.split('-')), 4)

    def test_unicite_numeros(self):
        numeros = {DepotDocumentService.generer_numero_recepisse() for _ in range(50)}
        self.assertEqual(len(numeros), 50)
