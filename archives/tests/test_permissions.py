"""
Tests unitaires — Logique RBAC/ABAC du système d'archives ENSMG.
Vérifie la matrice des permissions pour chaque rôle × niveau de confidentialité.
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from archives.permissions import (
    est_admin, est_archiviste, est_direction, est_personnel, est_enseignant,
    a_acces_gestion, a_acces_lecture_etendue,
    get_confidentialites_autorisees,
    peut_voir_document, peut_modifier_document, peut_supprimer_document,
    peut_eliminer, peut_verser, peut_deposer, peut_traiter_depot,
    peut_demander_pret, peut_gerer_prets,
)
from users.models import CustomUser


def _utilisateur(role, superuser=False, actif=True):
    """Crée un mock utilisateur avec le rôle et les attributs nécessaires."""
    user = MagicMock()
    user.role          = role
    user.is_superuser  = superuser
    user.is_authenticated = True
    user.is_active     = actif
    user.departement   = None
    return user


def _document(confidentialite, producteur='Direction'):
    doc = MagicMock()
    doc.confidentialite = confidentialite
    doc.producteur      = producteur
    return doc


# =============================================================================
# HELPERS DE RÔLE
# =============================================================================

class TestHelpersRole(TestCase):

    def test_est_admin(self):
        self.assertTrue(est_admin(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(est_admin(_utilisateur(None, superuser=True)))
        self.assertFalse(est_admin(_utilisateur(CustomUser.Role.ARCHIVISTE)))

    def test_est_archiviste(self):
        self.assertTrue(est_archiviste(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(est_archiviste(_utilisateur(CustomUser.Role.ADMIN)))

    def test_est_direction(self):
        self.assertTrue(est_direction(_utilisateur(CustomUser.Role.DIRECTION)))
        self.assertFalse(est_direction(_utilisateur(CustomUser.Role.PERSONNEL)))

    def test_a_acces_gestion(self):
        self.assertTrue(a_acces_gestion(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(a_acces_gestion(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(a_acces_gestion(_utilisateur(CustomUser.Role.DIRECTION)))
        self.assertFalse(a_acces_gestion(_utilisateur(CustomUser.Role.PERSONNEL)))
        self.assertFalse(a_acces_gestion(_utilisateur(CustomUser.Role.ENSEIGNANT)))

    def test_a_acces_lecture_etendue(self):
        self.assertTrue(a_acces_lecture_etendue(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(a_acces_lecture_etendue(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertTrue(a_acces_lecture_etendue(_utilisateur(CustomUser.Role.DIRECTION)))
        self.assertFalse(a_acces_lecture_etendue(_utilisateur(CustomUser.Role.PERSONNEL)))
        self.assertFalse(a_acces_lecture_etendue(_utilisateur(CustomUser.Role.ENSEIGNANT)))


# =============================================================================
# CONFIDENTIALITÉS AUTORISÉES PAR RÔLE
# =============================================================================

class TestConfidentialitesAutorisees(TestCase):

    def test_admin_voit_tout(self):
        niveaux = get_confidentialites_autorisees(_utilisateur(CustomUser.Role.ADMIN))
        self.assertIn('SECRET', niveaux)
        self.assertIn('CONFIDENTIEL', niveaux)

    def test_archiviste_voit_tout(self):
        niveaux = get_confidentialites_autorisees(_utilisateur(CustomUser.Role.ARCHIVISTE))
        self.assertIn('SECRET', niveaux)

    def test_direction_ne_voit_pas_secret(self):
        niveaux = get_confidentialites_autorisees(_utilisateur(CustomUser.Role.DIRECTION))
        self.assertNotIn('SECRET', niveaux)
        self.assertIn('CONFIDENTIEL', niveaux)

    def test_personnel_voit_public_interne(self):
        niveaux = get_confidentialites_autorisees(_utilisateur(CustomUser.Role.PERSONNEL))
        self.assertIn('PUBLIC', niveaux)
        self.assertIn('INTERNE', niveaux)
        self.assertNotIn('CONFIDENTIEL', niveaux)
        self.assertNotIn('SECRET', niveaux)

    def test_enseignant_voit_uniquement_public(self):
        niveaux = get_confidentialites_autorisees(_utilisateur(CustomUser.Role.ENSEIGNANT))
        self.assertEqual(niveaux, ['PUBLIC'])

    def test_superuser_voit_tout(self):
        user = _utilisateur(None, superuser=True)
        niveaux = get_confidentialites_autorisees(user)
        self.assertIn('SECRET', niveaux)


# =============================================================================
# PEUT_VOIR_DOCUMENT — RBAC + ABAC
# =============================================================================

class TestPeutVoirDocument(TestCase):

    def test_utilisateur_non_authentifie_bloque(self):
        user = MagicMock()
        user.is_authenticated = False
        doc  = _document('PUBLIC')
        self.assertFalse(peut_voir_document(user, doc))

    def test_admin_voit_document_secret(self):
        user = _utilisateur(CustomUser.Role.ADMIN)
        doc  = _document('SECRET')
        with patch('archives.models.AccesDocument') as mock_acces:
            mock_acces.objects.filter.return_value.first.return_value = None
            self.assertTrue(peut_voir_document(user, doc))

    def test_enseignant_bloque_sur_interne(self):
        user = _utilisateur(CustomUser.Role.ENSEIGNANT)
        doc  = _document('INTERNE')
        with patch('archives.models.AccesDocument') as mock_acces:
            mock_acces.objects.filter.return_value.first.return_value = None
            self.assertFalse(peut_voir_document(user, doc))

    def test_personnel_voit_interne_meme_departement(self):
        user = _utilisateur(CustomUser.Role.PERSONNEL)
        dept = MagicMock()
        dept.nom = 'Direction des ressources humaines'
        user.departement = dept
        doc = _document('INTERNE', producteur='Direction des ressources humaines')
        with patch('archives.models.AccesDocument') as mock_acces:
            mock_acces.objects.filter.return_value.first.return_value = None
            self.assertTrue(peut_voir_document(user, doc))

    def test_personnel_bloque_interne_autre_departement(self):
        user = _utilisateur(CustomUser.Role.PERSONNEL)
        dept = MagicMock()
        dept.nom = 'Scolarité'
        user.departement = dept
        doc = _document('INTERNE', producteur='Direction des ressources humaines')
        with patch('archives.models.AccesDocument') as mock_acces:
            mock_acces.objects.filter.return_value.first.return_value = None
            self.assertFalse(peut_voir_document(user, doc))

    def test_abac_passe_outre_restriction_role(self):
        """Un accès individuel accordé dépasse la restriction RBAC."""
        user = _utilisateur(CustomUser.Role.ENSEIGNANT)
        doc  = _document('SECRET')
        acces_mock = MagicMock()
        acces_mock.date_fin = None
        with patch('archives.models.AccesDocument') as mock_acces:
            mock_acces.objects.filter.return_value.first.return_value = acces_mock
            self.assertTrue(peut_voir_document(user, doc))


# =============================================================================
# PERMISSIONS DE GESTION
# =============================================================================

class TestPermissionsGestion(TestCase):

    def test_peut_modifier_document(self):
        self.assertTrue(peut_modifier_document(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(peut_modifier_document(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(peut_modifier_document(_utilisateur(CustomUser.Role.DIRECTION)))
        self.assertFalse(peut_modifier_document(_utilisateur(CustomUser.Role.PERSONNEL)))

    def test_peut_supprimer_document(self):
        self.assertTrue(peut_supprimer_document(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertFalse(peut_supprimer_document(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(peut_supprimer_document(_utilisateur(CustomUser.Role.DIRECTION)))

    def test_peut_eliminer(self):
        self.assertTrue(peut_eliminer(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(peut_eliminer(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(peut_eliminer(_utilisateur(CustomUser.Role.DIRECTION)))

    def test_peut_verser(self):
        self.assertTrue(peut_verser(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertTrue(peut_verser(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(peut_verser(_utilisateur(CustomUser.Role.DIRECTION)))

    def test_peut_traiter_depot(self):
        self.assertTrue(peut_traiter_depot(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertTrue(peut_traiter_depot(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertFalse(peut_traiter_depot(_utilisateur(CustomUser.Role.PERSONNEL)))

    def test_peut_deposer_tout_utilisateur_actif(self):
        for role in CustomUser.Role:
            self.assertTrue(peut_deposer(_utilisateur(role)))

    def test_peut_deposer_bloque_si_inactif(self):
        user = _utilisateur(CustomUser.Role.PERSONNEL, actif=False)
        user.is_active = False
        self.assertFalse(peut_deposer(user))

    def test_peut_demander_pret_agents_seulement(self):
        self.assertTrue(peut_demander_pret(_utilisateur(CustomUser.Role.PERSONNEL)))
        self.assertTrue(peut_demander_pret(_utilisateur(CustomUser.Role.ENSEIGNANT)))
        self.assertTrue(peut_demander_pret(_utilisateur(CustomUser.Role.DIRECTION)))
        self.assertFalse(peut_demander_pret(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertFalse(peut_demander_pret(_utilisateur(CustomUser.Role.ADMIN)))

    def test_peut_gerer_prets(self):
        self.assertTrue(peut_gerer_prets(_utilisateur(CustomUser.Role.ARCHIVISTE)))
        self.assertTrue(peut_gerer_prets(_utilisateur(CustomUser.Role.ADMIN)))
        self.assertFalse(peut_gerer_prets(_utilisateur(CustomUser.Role.PERSONNEL)))
