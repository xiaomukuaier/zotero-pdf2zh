import concurrent.futures
import tempfile
import unittest
from pathlib import Path

import fitz

from utils.job_registry import JobRegistry, request_fingerprint


class JobRegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='.test-', dir=Path(__file__).parent)
        self.root = Path(self.directory.name)
        self.registry = JobRegistry(self.root / "jobs.sqlite3")

    def tearDown(self):
        self.directory.cleanup()

    def test_concurrent_requests_share_one_job(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            claims = list(pool.map(lambda _: self.registry.claim("same"), range(24)))
        self.assertEqual(sum(owner for owner, _ in claims), 1)
        self.assertEqual(len({job["taskId"] for _, job in claims}), 1)

    def test_completed_result_survives_reopen_and_missing_output_retries(self):
        _, job = self.registry.claim("same")
        output = self.root / "result.pdf"
        document = fitz.open()
        document.new_page().insert_text((72, 72), "A real PDF result")
        document.save(output)
        document.close()
        result = {"status": "success", "filePaths": [str(output)], "fileList": [output.name]}
        self.registry.complete(job["taskId"], result)
        reopened = JobRegistry(self.root / "jobs.sqlite3")
        owner, cached = reopened.claim("same")
        self.assertFalse(owner)
        self.assertEqual(cached["result"], result)
        output.unlink()
        owner, retry = reopened.claim("same")
        self.assertTrue(owner)
        self.assertNotEqual(retry["taskId"], job["taskId"])

    def test_modified_output_and_failed_job_can_retry(self):
        _, job = self.registry.claim("same")
        output = self.root / "result.pdf"
        document = fitz.open()
        document.new_page()
        document.save(output)
        document.close()
        self.registry.complete(job["taskId"], {"status": "success", "filePaths": [str(output)]})
        output.write_bytes(b"truncated")
        owner, retry = self.registry.claim("same")
        self.assertTrue(owner)
        self.registry.fail(retry["taskId"])
        self.assertTrue(self.registry.claim("same")[0])

    def test_content_configuration_and_operation_define_identity(self):
        config = {"model": "model-a", "targetLang": "zh-CN"}
        first = request_fingerprint(b"document", config, "/translate")
        self.assertEqual(first, request_fingerprint(b"document", dict(reversed(list(config.items()))), "/translate"))
        self.assertNotEqual(first, request_fingerprint(b"changed", config, "/translate"))
        self.assertNotEqual(first, request_fingerprint(b"document", {**config, "model": "model-b"}, "/translate"))
        self.assertNotEqual(first, request_fingerprint(b"document", config, "/compare"))

    def test_restart_allows_interrupted_job_to_retry(self):
        _, interrupted = self.registry.claim('interrupted')
        reopened = JobRegistry(self.root / 'jobs.sqlite3')
        reopened.recover_interrupted()
        owner, retry = reopened.claim('interrupted')
        self.assertTrue(owner)
        self.assertNotEqual(retry['taskId'], interrupted['taskId'])

    def test_missing_outputs_cannot_be_marked_complete(self):
        _, job = self.registry.claim('missing')
        with self.assertRaises(ValueError):
            self.registry.complete(job['taskId'], {'filePaths': []})
        self.assertEqual(self.registry.get(job['taskId'])['status'], 'running')
