import csv
import sqlite3

def remove_trailing_comma(s):
    if s[-1] == ',':
        return s[0:-1]
    return s


def csv_to_sqlite(csv_file_path, db_name, table_name):
    # Connect to the SQLite3 database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Open the CSV file and read its contents
    with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        csv_reader = csv.DictReader(csvfile)

        # Get the column names from the first line of the CSV
        columns = csv_reader.fieldnames
        if not columns:
            raise ValueError("CSV file does not contain column names in the first line.")
        if columns[-1] == ',':
            columns = columns[0:-1]

        # Prepare the SQL insert statement
        placeholders = ', '.join(['?'] * len(columns))
        insert_sql = f'INSERT INTO {table_name} ({", ".join(columns)}) VALUES ({placeholders})'

        # Insert the data into the SQLite3 database
        for row in csv_reader:
            values = [row[column] for column in columns]
            print (insert_sql, values)
            cursor.execute(insert_sql, values)

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()

# Example usage
csv_file_path = 'beerexport.csv'
db_name = 'beer.db'
table_name = 'beers'
csv_to_sqlite(csv_file_path, db_name, table_name)
