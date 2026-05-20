import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import tools
import importlib
import agent


# Environment update with fake values — must be set before modules are imported

os.environ.update({
    "AZURE_OPENAI_API_KEY": "test-key",
    "AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com/",
    "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-test",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "emb-test",
    "CHROMA_DIR": "/tmp/chroma_test",
    "COLLECTION": "test_collection",
    "TOP_K": "3",
    "CHUNK_SIZE": "512",
    "CHUNK_OVERLAP": "64",
})



# tools.py — get_epa_facilities


class TestGetEpaFacilities(unittest.TestCase):

    @patch("tools.requests.get")
    def test_returns_json_string_on_success(self, mock_get):
        """To check whether a valid API response is returned as a JSON string."""

        payload = {"results": [{"name": "Facility A", "zip": "60085"}]}
        mock_get.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value=payload))

        result = tools.get_epa_facilities("60085")

        self.assertIsInstance(result, str)
        self.assertEqual(json.loads(result), payload)





# agent.py — retrieve, chat


def fake_tiktoken():
    enc = MagicMock()
    enc.encode.side_effect = lambda t: t.split() if t else []
    enc.decode.side_effect = lambda tokens: " ".join(tokens)
    mod = MagicMock()
    mod.get_encoding.return_value = enc
    return mod


def build_agent(docs, metas, chat_content="Answer.", tool_calls=False):
    """Return (agent module, fake_client) with all deps mocked."""


    fake_emb_item = MagicMock()
    fake_emb_item.embedding = [0.1, 0.2]
    fake_emb_resp = MagicMock()
    fake_emb_resp.data = [fake_emb_item]

    fake_col = MagicMock()
    fake_col.query.return_value = {"documents": docs, "metadatas": metas}

    fake_db = MagicMock()
    fake_db.get_or_create_collection.return_value = fake_col
    fake_chromadb = MagicMock()
    fake_chromadb.PersistentClient.return_value = fake_db

    call_count = [0]

    def make_response(with_tools=False):
        msg = MagicMock()
        msg.content = chat_content
        if with_tools:
            tc = MagicMock()
            tc.id = "tc-1"
            tc.function.name = "get_epa_facilities"
            tc.function.arguments = json.dumps({"zip_code": "60085"})
            msg.tool_calls = [tc]
            msg.model_dump.return_value = {"role": "assistant", "content": None}
        else:
            msg.tool_calls = None
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        return resp

    def completion_side_effect(**kwargs):
        call_count[0] += 1
        return make_response(with_tools=(tool_calls and call_count[0] == 1))

    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = fake_emb_resp
    fake_client.chat.completions.create.side_effect = completion_side_effect

    with patch.dict("sys.modules", {"chromadb": fake_chromadb, "tiktoken": fake_tiktoken()}):
        with patch("openai.AzureOpenAI", return_value=fake_client):
            
            importlib.reload(agent)
            agent.client = fake_client
            agent.col = fake_col

    return agent, fake_client


class TestRetrieve(unittest.TestCase):

    def test_formats_context_with_source_and_content(self):
        """retrieve() should return numbered context blocks with source metadata."""
        agent, _ = build_agent(
            docs=[["water treatment chunk"]],
            metas=[[{"source": "report.pdf"}]],
        )
        result = agent.retrieve("water treatment")
        self.assertIn("Context 1", result)
        self.assertIn("report.pdf", result)
        self.assertIn("water treatment chunk", result)

    def test_returns_fallback_when_no_results(self):
        """retrieve() should return a clear message when ChromaDB finds nothing."""
        agent, _ = build_agent(docs=[[]], metas=[[]])
        result = agent.retrieve("unknown topic")
        self.assertEqual(result, "No relevant context found.")


class TestChat(unittest.TestCase):

    def test_returns_reply_and_appends_to_history(self):
        """chat() must return the model reply and extend history by 2 entries."""
        agent, _ = build_agent(docs=[[]], metas=[[]], chat_content="Here is the answer.")
        reply, history = agent.chat("What is water treatment?", [])
        self.assertEqual(reply, "Here is the answer.")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["content"], "Here is the answer.")

    @patch("tools.requests.get")
    def test_tool_call_triggers_second_completion(self, mock_get):
        """When model returns a tool_call, a follow-up completion must be made."""
        mock_get.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={}))
        agent, fake_client = build_agent(
            docs=[[]], metas=[[]],
            chat_content="EPA answer.",
            tool_calls=True,
        )
        agent.chat("EPA facilities near 60085", [])
        self.assertGreaterEqual(fake_client.chat.completions.create.call_count, 2)



# ingest.py — embeddings


class TestEmbed(unittest.TestCase):

    def test_embeddings_returned_sorted_by_index(self):
        """embed() must sort results by index even if API returns them out of order."""
        

        item0 = MagicMock(); item0.index = 0; item0.embedding = [0.1]
        item1 = MagicMock(); item1.index = 1; item1.embedding = [0.9]
        fake_resp = MagicMock(); fake_resp.data = [item1, item0]  # reversed

        fake_client = MagicMock()
        fake_client.embeddings.create.return_value = fake_resp

        with patch.dict("sys.modules", {"chromadb": MagicMock(), "tiktoken": fake_tiktoken()}):
            with patch("openai.AzureOpenAI", return_value=fake_client):
                import ingest
                importlib.reload(ingest)
                ingest.client = fake_client
                result = ingest.embed(["text a", "text b"])

        self.assertEqual(result, [[0.1], [0.9]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
