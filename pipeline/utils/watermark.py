import boto3


def get_watermark(table_name: str, dynamodb_table: str) -> str:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(dynamodb_table)
    response = table.get_item(Key={"table_name": table_name})
    item = response.get("Item")
    if item and "last_extracted_at" in item:
        return item["last_extracted_at"]
    return "1970-01-01T00:00:00+00:00"


def update_watermark(table_name: str, dynamodb_table: str, timestamp: str) -> None:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(dynamodb_table)
    table.put_item(Item={"table_name": table_name, "last_extracted_at": timestamp})
