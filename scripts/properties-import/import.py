"""
Azure Table Storage Property Import Script

This script imports property data from a CSV file into Azure Table Storage.
The CSV file should contain columns including PartitionKey and RowKey.
Automatically detects and converts data types including JSON, booleans, and numbers.
Supports Azure Table Storage type annotations (@type columns).

Usage:
    python import.py <connection_string_or_keyvault_url>

Arguments:
    connection_string_or_keyvault_url: Either:
        - Azure Storage Account connection string in the format:
          "DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net"
        - Azure Key Vault secret URL in the format:
          "https://<vault>.vault.azure.net/secrets/<secret-name>/<version>"

Examples:
    python import.py "DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=mykey;EndpointSuffix=core.windows.net"
    python import.py "https://myvault.vault.azure.net/secrets/STORAGE-CONNECTION-STRING/5c97553cbb604bc3b46d53c940e19e20"

Requirements:
    - pandas
    - azure-data-tables
    - properties.csv file in the same directory

The script will:
1. Read the properties.csv file with any columns
2. Auto-detect and parse JSON structures (arrays/objects)
3. Auto-detect and convert booleans (true/false strings)
4. Auto-detect and convert numbers (integers/floats)
5. Handle Azure Table Storage type annotations (@type columns) for explicit typing
6. Serialize complex data types (lists/objects) as JSON strings for Azure Table Storage compatibility
7. Create the 'properties' table if it doesn't exist
8. Upload/upsert each row as an entity in the table
9. Convert PartitionKey and RowKey to strings as required by Azure Table Storage

Supported automatic conversions:
- JSON arrays: [ {...}, {...} ] -> JSON string (Azure Table Storage compatible)
- JSON objects: { "key": "value" } -> JSON string (Azure Table Storage compatible)  
- Booleans: "true"/"false" -> True/False
- Numbers: "123" -> 123, "12.34" -> 12.34
- Empty arrays: "[ ]" or "[]" -> "[]" (JSON string)
- Empty objects: "{ }" or "{}" -> "{}" (JSON string)

Note: Azure Table Storage doesn't support complex data types (lists, objects) natively,
so they are automatically serialized as JSON strings for storage and retrieval.
"""

import pandas as pd
import sys
import json
import subprocess
from azure.data.tables import TableServiceClient, TableEntity

def get_connection_string(connection_string_or_url):
    """Get connection string, supporting Key Vault URLs"""
    # Check if it's a Key Vault URL
    if connection_string_or_url.startswith('https://') and '.vault.azure.net/' in connection_string_or_url:
        print("Detected Key Vault URL, retrieving secret...")
        try:
            # Use Azure CLI to get the secret value
            result = subprocess.run([
                'az', 'keyvault', 'secret', 'show', 
                '--id', connection_string_or_url,
                '--query', 'value',
                '--output', 'tsv'
            ], capture_output=True, text=True, check=True)
            
            connection_string = result.stdout.strip()
            print("Successfully retrieved connection string from Key Vault")
            return connection_string
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving secret from Key Vault: {e}")
            print("Make sure you're logged in with 'az login' and have permissions to the Key Vault")
            sys.exit(1)
        except FileNotFoundError:
            print("Error: Azure CLI not found. Please install Azure CLI or provide the actual connection string.")
            sys.exit(1)
    else:
        # It's already a connection string
        return connection_string_or_url

def parse_json_field(value):
    """Parse JSON string fields, handling empty arrays and objects"""
    if pd.isna(value) or value == '':
        return None
    
    # Handle empty arrays and objects
    if value in ['[ ]', '[]', '[ ]']:
        return []
    if value in ['{ }', '{}', '{ }']:
        return {}
    
    # Try to detect if this looks like JSON
    if isinstance(value, str) and (
        (value.strip().startswith('[') and value.strip().endswith(']')) or
        (value.strip().startswith('{') and value.strip().endswith('}'))
    ):
        try:
            # Handle the CSV escaping of quotes (double quotes become double-double quotes)
            cleaned_value = value.replace('""', '"')
            return json.loads(cleaned_value)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON field '{value[:50]}...': {e}")
            return value
    
    return value

def detect_and_convert_type(value, type_hint=None):
    """Detect and convert data types based on content and type hints"""
    if pd.isna(value) or value == '':
        return None
    
    # Use type hint if available
    if type_hint == 'Boolean':
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)
    
    # Auto-detect JSON structures
    parsed_json = parse_json_field(value)
    if parsed_json != value:  # JSON was successfully parsed
        return parsed_json
    
    # Auto-detect booleans
    if isinstance(value, str) and value.lower() in ['true', 'false']:
        return value.lower() == 'true'
    
    # Auto-detect numbers
    if isinstance(value, str):
        # Try integer
        try:
            if '.' not in value and value.isdigit():
                return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            if '.' in value:
                return float(value)
        except ValueError:
            pass
    
    # Return as-is (string or original type)
    return value

def process_entity(row, df_columns):
    """Process a row into an entity, handling type annotations and auto-detecting data types"""
    entity = {}
    
    for column in df_columns:
        # Skip @type columns as they're metadata
        if column.endswith('@type'):
            continue
            
        value = row[column]
        
        # Skip null/NaN values
        if pd.isna(value):
            continue
        
        # Get type hint from corresponding @type column if it exists
        type_hint = None
        type_column = column + '@type'
        if type_column in df_columns and not pd.isna(row.get(type_column)):
            type_hint = row[type_column]
        
        # Convert value based on type hint or auto-detection
        converted_value = detect_and_convert_type(value, type_hint)
        
        # Azure Table Storage doesn't support lists/dicts directly
        # Serialize complex types as JSON strings
        if isinstance(converted_value, (list, dict)):
            entity[column] = json.dumps(converted_value)
        else:
            entity[column] = converted_value
    
    return entity

def main():
    # Check for command line argument
    if len(sys.argv) != 2:
        print("Usage: python import.py <connection_string_or_keyvault_url>")
        print("Example 1: python import.py \"DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey;EndpointSuffix=core.windows.net\"")
        print("Example 2: python import.py \"https://myvault.vault.azure.net/secrets/STORAGE-CONNECTION-STRING/version\"")
        sys.exit(1)
    
    # Get connection string from command line or Key Vault
    connection_string = get_connection_string(sys.argv[1])
    
    # CSV file path
    csv_file = 'properties.csv'

    # Azure Table Storage connection info
    table_name = "properties"

    print(f"Reading CSV file: {csv_file}")
    # Read CSV
    try:
        df = pd.read_csv(csv_file)
        print(f"Found {len(df)} rows in CSV file")
        print(f"Columns: {list(df.columns)}")
    except FileNotFoundError:
        print(f"Error: Could not find {csv_file} in the current directory")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    print("Connecting to Azure Table Storage...")
    # Create table client
    try:
        service = TableServiceClient.from_connection_string(conn_str=connection_string)
        table_client = service.get_table_client(table_name=table_name)
    except Exception as e:
        print(f"Error connecting to Azure Table Storage: {e}")
        sys.exit(1)

    # Optionally create the table if it doesn't exist
    try:
        table_client.create_table()
        print(f"Created table: {table_name}")
    except Exception:
        print(f"Table {table_name} already exists")

    print("Uploading entities...")
    # Upload each row
    successful_uploads = 0
    for index, row in df.iterrows():
        try:
            entity = process_entity(row, df.columns)
            
            # Ensure PartitionKey and RowKey are strings
            if 'PartitionKey' in entity:
                entity["PartitionKey"] = str(entity["PartitionKey"])
            if 'RowKey' in entity:
                entity["RowKey"] = str(entity["RowKey"])
                
            # Debug: print first entity to verify parsing
            if index == 0:
                print(f"Sample entity: {json.dumps(entity, indent=2, default=str)}")
            
            table_client.upsert_entity(entity=entity)
            successful_uploads += 1
            if successful_uploads % 10 == 0:
                print(f"Uploaded {successful_uploads} entities...")
        except Exception as e:
            print(f"Error uploading row {index} (PartitionKey: {row.get('PartitionKey', 'N/A')}): {e}")

    print(f"Upload complete. Successfully uploaded {successful_uploads} out of {len(df)} entities.")

if __name__ == "__main__":
    main()
