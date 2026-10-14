"""Relie les arguments du terminal aux services métier et aux vues."""

from authentication import authorize_current_user
import read_data
import views
import write_data


def _values(args, fields):
    return {
        field: getattr(args, field)
        for field in fields
        if getattr(args, field, None) is not None
    }


def _password(password_reader):
    password = password_reader("Mot de passe : ")
    if password != password_reader("Confirmez le mot de passe : "):
        raise ValueError("Les mots de passe ne correspondent pas.")
    return password


def _collaborators(session, args, password_reader):
    if args.action == "list":
        views.show_collaborators(read_data.get_all_collaborators(session))
    elif args.action == "show":
        views.show_collaborator(read_data.get_collaborator(session, args.record_id))
    elif args.action in ("create", "update"):
        action = (
            "create_collaborator" if args.action == "create" else "update_collaborator"
        )
        authorize_current_user(session, action)
        values = _values(args, ("full_name", "email", "role_name"))
        if args.action == "create" or args.change_password:
            values["password"] = _password(password_reader)
        if args.action == "create":
            user = write_data.create_collaborator(session, **values)
            return f"Collaborateur créé. Numéro d'employé : {user.id}"
        user = write_data.update_collaborator(session, args.record_id, **values)
        return f"Collaborateur {user.id} modifié."
    else:
        authorize_current_user(session, "delete_collaborator")
        read_data.get_collaborator(session, args.record_id)
        confirmation = input(
            f"Supprimer le collaborateur {args.record_id} ? Tapez OUI : "
        )
        if confirmation.strip() != "OUI":
            return "Suppression annulée."
        write_data.delete_collaborator(
            session, args.record_id, args.replacement_commercial
        )
        return f"Collaborateur {args.record_id} supprimé."


def _clients(session, args):
    if args.action == "list":
        views.show_clients(read_data.get_all_clients(session))
    elif args.action == "show":
        views.show_client(read_data.get_client(session, args.record_id))
    else:
        values = _values(args, write_data.CLIENT_FIELDS)
        if args.action == "create":
            client = write_data.create_client(session, **values)
            return f"Client créé. Identifiant : {client.id}"
        client = write_data.update_client(session, args.record_id, **values)
        return f"Client {client.id} modifié."


def _contracts(session, args):
    if args.action == "list":
        views.show_contracts(
            read_data.get_all_contracts(
                session, unsigned=args.unsigned, unpaid=args.unpaid
            )
        )
    elif args.action == "show":
        views.show_contract(read_data.get_contract(session, args.record_id))
    else:
        values = _values(args, write_data.CONTRACT_FIELDS)
        if args.action == "create":
            contract = write_data.create_contract(session, **values)
            return f"Contrat créé. Identifiant : {contract.id}"
        contract = write_data.update_contract(session, args.record_id, **values)
        return f"Contrat {contract.id} modifié."


def _events(session, args):
    if args.action == "list":
        views.show_events(
            read_data.get_all_events(
                session, unassigned=args.unassigned, mine=args.mine
            )
        )
    elif args.action == "show":
        views.show_event(read_data.get_event(session, args.record_id))
    elif args.action == "assign":
        current = write_data.assign_support(session, args.record_id, args.support_id)
        return f"Affectation de l'événement {current.id} modifiée."
    else:
        values = _values(args, write_data.EVENT_FIELDS)
        if args.action == "create":
            current = write_data.create_event(session, **values)
            return f"Événement créé. Identifiant : {current.id}"
        if args.clear_notes:
            values["notes"] = None
        current = write_data.update_event(session, args.record_id, **values)
        return f"Événement {current.id} modifié."


def execute(session, args, password_reader):
    if args.command == "collaborators":
        return _collaborators(session, args, password_reader)
    if args.command == "clients":
        return _clients(session, args)
    if args.command == "contracts":
        return _contracts(session, args)
    return _events(session, args)
