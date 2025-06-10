import json
from typing import Dict, Any


def create_response(
    status_code: int, body_dict: Dict[str, Any], methods: str
) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": methods,
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body_dict) if body_dict else "{}",
    }
