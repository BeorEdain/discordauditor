from mysql.connector import (
    IntegrityError, MySQLConnection, ProgrammingError, connect)

def get_credentials() -> MySQLConnection:
    """
    A helper function used to get the credentials for the server, simplifying
    the process.
    """
    # Try to get the credentials for the server.
    credentials = []
    try:
        with open("sensitive/database_credentials", 'rt') as key:
            for item in key:
                credentials.append(str(item).strip())
    
    # If the file isn't there, exit.
    # TODO: If exception is raised, revert to manual input from user and save
    # output to the file.
    except FileNotFoundError:
        print("database_credentials does not exist.")
        exit()

    # Try the connection.
    try:
        mydb = connect(
            host=credentials[0],
            user=credentials[1],
            password=credentials[2],
            database=credentials[3])
        
        return mydb

    # If the connection cannot be established due to input error, log and quit.
    except ProgrammingError:
        print("There was an error with the credentials.")
        exit()

def new_message(message):
    pass

def edited_message(message):
    pass

def deleted_message(message):
    pass