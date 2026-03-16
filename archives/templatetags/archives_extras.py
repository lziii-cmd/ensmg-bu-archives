"""
archives/templatetags/archives_extras.py
Filtres et tags personnalisés pour les templates du système d'archives ENSMG.
"""

from django import template

register = template.Library()


@register.filter
def split_pipe(value):
    """
    Découpe une chaîne en segments séparés par '|', chaque segment
    étant lui-même découpé par ',' en une liste de valeurs.

    Exemple d'usage dans un template :
        {% for step, label, icon in 'BROUILLON,Brouillon,pencil|VALIDE,Validé,check-circle'|split_pipe %}
            {{ step }} — {{ label }} — {{ icon }}
        {% endfor %}

    Retourne une liste de listes : [['BROUILLON', 'Brouillon', 'pencil'], ...]
    """
    if not value:
        return []
    return [segment.split(',') for segment in value.split('|') if segment.strip()]


@register.filter
def split(value, sep=','):
    """
    Découpe une chaîne selon un séparateur (virgule par défaut).

    Exemple : {{ 'a,b,c'|split }} → ['a', 'b', 'c']
    """
    if not value:
        return []
    return [s.strip() for s in value.split(sep)]


@register.filter
def get_item(dictionary, key):
    """
    Accède à une valeur de dictionnaire dans un template.
    Exemple : {{ my_dict|get_item:key }}
    """
    return dictionary.get(key)


@register.filter
def abs_value(value):
    """Valeur absolue d'un nombre."""
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value


@register.filter
def taille_lisible(octets):
    """
    Convertit une taille en octets en format lisible (Ko, Mo, Go).
    Exemple : {{ document.taille_fichier|taille_lisible }}
    """
    if not octets:
        return '—'
    for unite, seuil in [('Go', 1_073_741_824), ('Mo', 1_048_576), ('Ko', 1024)]:
        if octets >= seuil:
            return f"{octets / seuil:.1f} {unite}"
    return f"{octets} o"
