import base64
import concurrent.futures
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import fitz


class JobEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='.test-', dir=Path(__file__).parent)
        cls.previous_data_path = os.environ.get('ZOTERO_PDF2ZH_DATA')
        os.environ['ZOTERO_PDF2ZH_DATA'] = cls.directory.name
        import server
        cls.server = server
        server.prepare_path()
        cls.translator = server.PDFTranslator(SimpleNamespace(enable_venv=False))
        cls.app = cls.translator.app
        cls.app.testing = True

    @classmethod
    def tearDownClass(cls):
        if cls.previous_data_path is None:
            del os.environ['ZOTERO_PDF2ZH_DATA']
        else:
            os.environ['ZOTERO_PDF2ZH_DATA'] = cls.previous_data_path
        cls.directory.cleanup()

    def request_data(self, title):
        document = fitz.open()
        for text in (title, title + ' translated'):
            document.new_page().insert_text((72, 72), text)
        content = document.tobytes()
        document.close()
        return dict(fileName=title + '.dual.pdf', fileContent=base64.b64encode(content).decode(), engine='pdf2zh_next', dualMode='TB')

    def post(self, data):
        with self.app.test_client() as client:
            response = client.post('/compare', json=data)
            self.assertEqual(response.status_code, 200)
            return response.get_json()

    def test_concurrent_real_pdf_requests_publish_one_result(self):
        data = self.request_data('concurrent')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.post, [data] * 16))
        self.assertEqual(len({result['taskId'] for result in results}), 1)
        self.assertEqual(len({tuple(result['filePaths']) for result in results}), 1)
        result = results[0]
        with fitz.open(result['filePaths'][0]) as document:
            self.assertEqual(len(document), 1)
            self.assertIn('translated', document[0].get_text())
        with self.app.test_client() as client:
            response = client.get('/translatedFile/' + result['fileList'][0])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, Path(result['filePaths'][0]).read_bytes())
        tasks = self.server.task_manager.get_active_tasks_list()
        task = next(task for task in tasks if task['taskId'] == result['taskId'])
        self.assertTrue(task['finished'])
        self.assertEqual(task['progress'], 100)

    def test_same_content_with_renamed_input_reuses_result(self):
        data = self.request_data('renamed')
        first = self.post(data)
        second = self.post(dict(data, fileName='other-name.dual.pdf'))
        self.assertEqual(first, second)

    def test_different_content_with_same_filename_is_isolated(self):
        first = self.post(self.request_data('shared'))
        data = self.request_data('different text')
        data['fileName'] = 'shared.dual.pdf'
        second = self.post(data)
        self.assertNotEqual(first['filePaths'], second['filePaths'])
        with fitz.open(first['filePaths'][0]) as document:
            self.assertIn('shared', document[0].get_text())

    def test_async_submission_returns_retrievable_completed_files(self):
        import time
        result = self.post(dict(self.request_data('async'), asyncJob=True))
        self.assertEqual(result['status'], 'accepted')
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.translator.jobs.get(result['taskId'])
            if state['status'] != 'running':
                break
            time.sleep(0.01)
        self.assertEqual(state['status'], 'success')
        self.assertTrue(Path(state['result']['filePaths'][0]).is_file())
