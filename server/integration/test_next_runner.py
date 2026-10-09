import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fitz
from babeldoc.progress_monitor import ProgressMonitor

from utils.structured_progress import PREFIX, progress_update


class NextRunnerTests(unittest.TestCase):
    def test_real_babeldoc_events_preserve_weighted_progress(self):
        events = []
        monitor = ProgressMonitor([('Parse PDF', 1), ('Translate Paragraphs', 3)], progress_change_callback=lambda **event: events.append(event), report_interval=0)
        with monitor.stage_start('Parse PDF', 36) as stage:
            stage.advance(36)
        self.assertEqual(progress_update(events[-1])['progress'], 25)
        with monitor.stage_start('Translate Paragraphs', 100) as stage:
            stage.advance(50)
            self.assertEqual(progress_update(events[-1])['progress'], 62)

    def test_engine_process_finishes_and_writes_valid_pdfs(self):
        with tempfile.TemporaryDirectory(prefix='.test-', dir=Path(__file__).parent) as directory:
            root = Path(directory)
            source = root / 'sample.pdf'
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), 'Quantum computing uses quantum states to process information.')
            document.save(source)
            document.close()
            runner = Path(__file__).resolve().parents[1] / 'utils' / 'next_runner.py'
            service = os.environ.get('PDF2ZH_TEST_SERVICE', 'siliconflowfree')
            self.assertIn(service, {'google', 'bing', 'siliconflowfree'})
            command = [sys.executable, str(runner), str(source), '--' + service, '--no-auto-extract-glossary', '--skip-scanned-detection', '--watermark-output-mode', 'no_watermark', '--output', str(root)]
            process = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy(), timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            events = [json.loads(line[len(PREFIX):]) for line in process.stdout.splitlines() if line.startswith(PREFIX)]
            self.assertTrue(any(event['type'] == 'finish' for event in events))
            self.assertTrue(any('overall_progress' in event for event in events))
            outputs = list(root.glob('*.mono.pdf')) + list(root.glob('*.dual.pdf'))
            self.assertEqual(len(outputs), 2)
            for output in outputs:
                with fitz.open(output) as result:
                    self.assertGreater(len(result), 0)
