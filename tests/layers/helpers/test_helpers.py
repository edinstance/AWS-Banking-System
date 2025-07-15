from response_helpers import create_response


class TestCreateResponse:
    def test_successful_response(self):
        body = {"message": "Success"}
        response = create_response(200, body, "POST")

        assert response["statusCode"] == 200
        assert response["body"] == '{"message": "Success"}'
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["Access-Control-Allow-Methods"] == "POST"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_error_response(self):
        body = {"error": "Bad Request"}
        response = create_response(400, body, "GET")

        assert response["statusCode"] == 400
        assert response["body"] == '{"error": "Bad Request"}'
        assert response["headers"]["Access-Control-Allow-Methods"] == "GET"

    def test_empty_body(self):
        """
        Tests that create_response returns a 204 response with an empty JSON body and correct CORS headers when given an empty dictionary and the DELETE method.
        """
        response = create_response(204, {}, "DELETE")

        assert response["statusCode"] == 204
        assert response["body"] == "{}"
        assert response["headers"]["Access-Control-Allow-Methods"] == "DELETE"

    def test_complex_body(self):
        """
        Test that create_response correctly handles a complex nested dictionary body and returns the expected JSON structure and headers.
        """
        body = {"data": {"id": 1, "items": ["a", "b", "c"], "nested": {"key": "value"}}}
        response = create_response(200, body, "PUT")

        assert response["statusCode"] == 200
        assert '"items": ["a", "b", "c"]' in response["body"]
        assert '"nested": {"key": "value"}' in response["body"]
        assert response["headers"]["Access-Control-Allow-Methods"] == "PUT"
