import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.homeos.framework.registry import get_model


class TestHomeOSLocalModels(unittest.TestCase):
    def test_ollama_prefixed_model_uses_openai_compatible_model(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "test", "AI_GATEWAY_API_KEY": ""}):
            model = get_model("ollama/qwen3:8b")
        self.assertEqual(model.__class__.__name__, "OpenAIChatModel")

    def test_local_prefixed_model_uses_openai_compatible_model(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "test", "AI_GATEWAY_API_KEY": ""}):
            model = get_model("local/hdb-agent")
        self.assertEqual(model.__class__.__name__, "OpenAIChatModel")

    def test_models_endpoint_includes_local_runtime_options(self):
        res = TestClient(app).get("/models")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        model_ids = {m["id"] for m in body["models"]}
        self.assertIn("ollama/qwen3:8b", model_ids)
        self.assertIn("local/hdb-agent", model_ids)
        self.assertIn("local_runtime", body)


if __name__ == "__main__":
    unittest.main()
