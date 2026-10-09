import unittest

from utils.execute import _parse_progress
from utils.task_manager import TaskManager, task_manager


class TaskProgressTests(unittest.TestCase):
    def test_only_successful_completion_reports_100(self):
        manager = TaskManager()
        manager.add_task('progress', {'active': True, 'progress': 0})
        manager.update_task('progress', {'progress': 100})
        self.assertEqual(manager.get_active_tasks_list()[0]['progress'], 99)
        manager.complete_task('progress', 'success')
        manager.update_task('progress', {'progress': 20, 'status': 'running'})
        task = manager.get_active_tasks_list()[0]
        self.assertEqual(task['progress'], 100)
        self.assertTrue(task['finished'])

    def test_truncated_substep_does_not_replace_overall_progress(self):
        task_manager.add_task('truncated', {'active': True, 'progress': 23})
        _parse_progress('Parse PDF and Create Intermediate Representation (1/1) 36/…', 'truncated')
        self.assertEqual(task_manager.active_tasks['truncated']['progress'], 23)
        with task_manager.lock:
            del task_manager.active_tasks['truncated']
