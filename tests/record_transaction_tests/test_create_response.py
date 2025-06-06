import json

from functions.record_transactions.app import create_response


class TestCreateResponse:

    def test_successful_response_creation(self):
        status_code = 200
        body_dict = {"message": "Success", "data": {"key": "value"}}
        expected_headers = {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        expected_body = json.dumps(body_dict)

        response = create_response(status_code, body_dict, "POST")

        assert response["statusCode"] == status_code
        assert response["headers"] == expected_headers
        assert response["body"] == expected_body

    def test_empty_body_dict(self):
        status_code = 204
        body_dict = {}
        expected_body = json.dumps(body_dict)

        response = create_response(status_code, body_dict, "DELETE")

        assert response["statusCode"] == status_code
        assert json.loads(response["body"]) == {}
        assert response["body"] == expected_body

    def test_different_status_codes(self):
        body_dict = {"status": "error"}

        status_code_400 = 400
        response_400 = create_response(status_code_400, body_dict, "POST")
        assert response_400["statusCode"] == status_code_400
        assert json.loads(response_400["body"]) == body_dict

        status_code_500 = 500
        response_500 = create_response(status_code_500, body_dict, "POST")
        assert response_500["statusCode"] == status_code_500
        assert json.loads(response_500["body"]) == body_dict

    def test_body_dict_with_complex_data(self):
        status_code = 200
        body_dict = {
            "user": {
                "id": "123",
                "name": "Test User",
                "roles": ["admin", "editor"],
                "isActive": True,
            },
            "timestamp": "2023-10-27T10:00:00Z",
        }
        expected_body = json.dumps(body_dict)

        response = create_response(status_code, body_dict, "GET")

        assert response["statusCode"] == status_code
        assert response["body"] == expected_body
        assert json.loads(response["body"]) == body_dict
