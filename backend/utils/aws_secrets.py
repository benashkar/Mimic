import os
import json
import logging

logger = logging.getLogger(__name__)

_cached_secrets = None

def get_db_credentials():
    """Get DB credentials from AWS Secrets Manager, fallback to env vars."""
    global _cached_secrets
    if _cached_secrets:
        return _cached_secrets

    secret_name = "/ben/ai-tool/db99"
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response["SecretString"])
        _cached_secrets = {
            "host": secrets["DB_HOST"],
            "port": int(secrets.get("DB_PORT", 3306)),
            "user": secrets["DB_USER"],
            "password": secrets["DB_PASSWORD"],
            "database": os.getenv("DB_NAME", "mimic"),
        }
        logger.info("Loaded DB credentials from AWS Secrets Manager")
    except Exception as e:
        logger.warning(f"AWS Secrets Manager unavailable ({e}), falling back to env vars")
        _cached_secrets = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "mimic"),
        }

    return _cached_secrets


def get_database_url():
    """Build SQLAlchemy database URL."""
    creds = get_db_credentials()
    return (
        f"mysql+pymysql://{creds['user']}:{creds['password']}"
        f"@{creds['host']}:{creds['port']}/{creds['database']}"
    )
