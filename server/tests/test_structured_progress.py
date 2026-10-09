import unittest

from utils.structured_progress import progress_update


class StructuredProgressTests(unittest.TestCase):
    def test_stage_completion_does_not_complete_job(self):
        event = {"type": "progress_update", "stage": "Parse PDF", "overall_progress": 12.5, "current": 36, "total": 36}
        update = progress_update(event)
        self.assertEqual(update["progress"], 12)
        self.assertEqual(update["message"], "Parse PDF")

    def test_engine_finish_waits_for_server_output_validation(self):
        self.assertEqual(progress_update({"type": "finish"})["progress"], 99)
        self.assertEqual(progress_update({"type": "progress_update", "overall_progress": 100})["progress"], 99)

    def test_error_events_fail_immediately(self):
        with self.assertRaisesRegex(RuntimeError, "translation failed"):
            progress_update({"type": "error", "error": "translation failed"})

    def test_missing_progress_does_not_reset_percentage(self):
        self.assertNotIn("progress", progress_update({"type": "progress_start", "stage": "Translate Paragraphs"}))
