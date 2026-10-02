"""Autorisations des départements suivant le cahier des charges."""

from models import Client, Contract, Event


READ_ACTIONS = {"read_client", "read_contract", "read_event"}
MANAGEMENT_ACTIONS = {
    "create_collaborator",
    "update_collaborator",
    "delete_collaborator",
    "create_contract",
    "update_contract",
}


def has_permission(user, action, resource=None):
    """Vérifie les droits d'un collaborateur obtenu par authentification."""
    if user is None or user.id is None or user.role is None:
        return False
    role_name = user.role.name
    if role_name not in {"gestion", "commercial", "support"}:
        return False
    if action in READ_ACTIONS:
        return True
    if role_name == "gestion":
        return action in MANAGEMENT_ACTIONS or (
            action == "assign_support" and isinstance(resource, Event)
        )
    if role_name == "commercial":
        if action == "create_client":
            return True
        if action == "update_client" and isinstance(resource, Client):
            return resource.sales_contact_id == user.id
        if action in {"update_contract", "create_event"} and isinstance(
            resource, Contract
        ):
            if resource.client is None or resource.client.sales_contact_id != user.id:
                return False
            return action == "update_contract" or resource.is_signed is True
    if role_name == "support" and action == "update_event":
        return isinstance(resource, Event) and resource.support_contact_id == user.id
    return False


def require_permission(user, action, resource=None):
    """Interrompt une opération interdite avant toute modification."""
    if not has_permission(user, action, resource):
        raise PermissionError("Vous n'avez pas la permission d'effectuer cette action.")
