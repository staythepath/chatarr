# Import necessary modules (this assumes your DataManager class is defined in the same file or imported appropriately)
from data_manager import DataManager  # Adjust import based on your project structure
from config_manager import ConfigManager  # Replace with actual import if available

# Initialize ConfigManager and DataManager
config_manager = ConfigManager()  # Adjust this as needed
data_manager = DataManager(config_manager)

# Get the names of all tables in your database
data_manager.db_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [table[0] for table in data_manager.db_cursor.fetchall()]

# Loop through each table, print its name, and display its structure
for table in tables:
    print(f"Structure of table: {table}")

    # Get table columns
    data_manager.db_cursor.execute(f"PRAGMA table_info({table});")
    columns = data_manager.db_cursor.fetchall()

    # Print each column's details
    for column in columns:
        print(column)
    print("\n")

# Optionally, if you want to see some data rows for each table:
for table in tables:
    print(f"Data from table: {table}")

    # Fetch all rows from the table
    data_manager.db_cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
    rows = data_manager.db_cursor.fetchall()

    # Print each row
    for row in rows:
        print(dict(row))  # Convert sqlite3.Row object to dict for easier readability
    print("\n")
