from django.contrib.auth.models import AbstractUser
from django.db import models


class Departement(models.Model):
    """
    Département ou service de l'ENSMG.
    Référentiel contrôlé — remplace le champ texte libre `service`
    pour garantir la cohérence du filtrage RBAC du Personnel.
    """

    class Type(models.TextChoices):
        DIRECTION    = 'DIRECTION',    'Direction et gouvernance'
        PEDAGOGIQUE  = 'PEDAGOGIQUE',  'Pédagogique'
        SCIENTIFIQUE = 'SCIENTIFIQUE', 'Scientifique et technique'
        ADMINISTRATIF = 'ADMINISTRATIF', 'Administratif'
        SUPPORT      = 'SUPPORT',      'Support et logistique'

    code        = models.CharField(max_length=20, unique=True, verbose_name='Code')
    nom         = models.CharField(max_length=200, verbose_name='Nom du département / service')
    type        = models.CharField(max_length=20, choices=Type.choices, verbose_name='Type')
    description = models.TextField(blank=True, verbose_name='Description')
    actif       = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name        = 'Département / Service'
        verbose_name_plural = 'Départements / Services'
        ordering            = ['type', 'nom']

    def __str__(self):
        return f"{self.nom}"


class CustomUser(AbstractUser):
    """
    Modèle utilisateur personnalisé avec gestion des rôles (RBAC).
    Remplace le User Django par défaut via AUTH_USER_MODEL.
    """

    class Role(models.TextChoices):
        ADMIN       = 'ADMIN',      'Administrateur système'
        ARCHIVISTE  = 'ARCHIVISTE', 'Archiviste'
        DIRECTION   = 'DIRECTION',  'Direction'
        PERSONNEL   = 'PERSONNEL',  'Personnel administratif'
        ENSEIGNANT  = 'ENSEIGNANT', 'Enseignant-chercheur'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PERSONNEL,
        verbose_name='Rôle',
    )
    departement = models.ForeignKey(
        Departement,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Département / Service',
        help_text='Service de rattachement de l\'utilisateur.',
    )
    telephone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Téléphone',
    )

    class Meta:
        verbose_name        = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering            = ['last_name', 'first_name']

    def __str__(self):
        nom_complet = self.get_full_name() or self.username
        dept = f" — {self.departement}" if self.departement else ''
        return f"{nom_complet} ({self.get_role_display()}){dept}"

    # --- Propriétés de commodité ---

    @property
    def est_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def est_archiviste(self):
        return self.role == self.Role.ARCHIVISTE

    @property
    def est_direction(self):
        return self.role == self.Role.DIRECTION

    @property
    def peut_eliminer(self):
        return self.role in (self.Role.ARCHIVISTE, self.Role.DIRECTION, self.Role.ADMIN)

    @property
    def peut_verser(self):
        return self.role in (self.Role.ARCHIVISTE, self.Role.ADMIN)

    @property
    def nom_departement(self):
        """Retourne le nom du département pour comparaison avec Document.producteur."""
        return self.departement.nom if self.departement else ''
