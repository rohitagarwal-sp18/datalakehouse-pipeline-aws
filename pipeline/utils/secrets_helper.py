import json
import boto3


def get_rds_credentials(secret_name: str) -> dict:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return {
        "username": secret["username"],
        "password": secret["password"],
        "host": secret["host"],
        "port": secret["port"],
        "dbname": secret["dbname"],
    }
