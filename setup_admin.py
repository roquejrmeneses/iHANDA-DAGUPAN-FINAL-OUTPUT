"""
iHANDA Dagupan - create an administrator account (run in a terminal).

    python setup_admin.py

* Creates the database automatically if it does not exist yet.
* Asks for a username, email and password (typed password is hidden).
* The password is stored only as a salted hash.
* If an admin already exists, you must sign in as that admin first
  before another admin can be created.
"""

import getpass
import sys

import database


def ask(label):
    return input(label).strip()


def ask_secret(label):
    return getpass.getpass(label)


def main():
    database.init_db()

    print("=" * 56)
    print("  iHANDA Dagupan - Administrator Account Setup")
    print("=" * 56)
    print(f"Database: {database.DB_PATH}\n")

    if database.admin_exists():
        print("An administrator account already exists.")
        print("Sign in as an existing administrator to add another one.\n")

        user, error = database.authenticate(
            ask("Existing admin username or email: "),
            ask_secret("Existing admin password: "),
            "admin"
        )

        if user is None:
            print("\nERROR: " + error)
            sys.exit(1)

        print(f"\nSigned in as {user['username']}.\n")
    else:
        print("No administrator exists yet - creating the first one.\n")

    while True:
        username = ask("New admin username (3-30 characters): ")
        email = ask("New admin email: ")
        password = ask_secret("Password (8+ characters, letters and numbers): ")
        confirm = ask_secret("Confirm password: ")

        ok, message = database.create_admin_account(
            username, email, password, confirm
        )

        if ok:
            print(f"\nSUCCESS: administrator '{username}' was created.")
            print("Start the admin application with:  python ihanda_admin.py")
            return

        print("\nERROR: " + message)

        if ask("Try again? (y/n): ").lower() != "y":
            sys.exit(1)

        print()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
