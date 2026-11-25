import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from agent import daily, editorial
from agent.responses import Drafts
from agent.store import Ledger, TZ


class CapacityError(Exception):
    code = 503


class GenerationRecovery(unittest.TestCase):
    def setUp(self):
        self.model = editorial.Model.__new__(editorial.Model)
        self.model.calls = 0
        self.model.models = ['first', 'second', 'third']
        self.model.client = Mock()
        self.generate = self.model.client.models.generate_content
        delay = patch.object(editorial.time, 'sleep')
        delay.start()
        self.addCleanup(delay.stop)

    def test_fallback_recovers_on_second_round(self):
        response = Mock(text=json.dumps({'texts': ['A question about music.']}))
        self.generate.side_effect = [CapacityError()] * 3 + [response]
        result = self.model.ask('Write a draft', {}, Drafts)
        self.assertEqual(result, {'texts': ['A question about music.']})
        self.assertEqual([c.kwargs['model'] for c in self.generate.call_args_list],
                         ['first', 'second', 'third', 'first'])

    def test_non_capacity_error_is_not_deferred(self):
        self.generate.side_effect = [ValueError(), CapacityError(), CapacityError(),
                                     CapacityError(), CapacityError()]
        with self.assertRaisesRegex(RuntimeError, '^model_unavailable$'):
            self.model.ask('Write a draft', {}, Drafts)

    def test_outage_defers_then_next_worker_can_publish_once(self):
        now = datetime.now(TZ).replace(hour=17, minute=0)
        ledger = Ledger.__new__(Ledger)
        state = {'slot': None, 'topics': []}
        ledger.load = lambda: (None, state)
        ledger.update = lambda change: change(state)
        self.generate.side_effect = CapacityError()
        publisher = Mock()
        publisher.send.return_value = '123'
        recovered = {'text': 'A question about music.', 'topic': 'music'}

        def draft(*_):
            return self.model.ask('Write a draft', {}, Drafts)

        with patch('agent.store.datetime', wraps=datetime) as state_time:
            state_time.now.return_value = now
            self.assertEqual(daily.run(ledger, publisher, draft, lambda: now, True),
                             'generation_deferred')
            self.assertEqual(self.generate.call_count, 6)
            self.assertEqual(state['slot']['attempts'], 0)
            self.assertEqual(daily.run(ledger, publisher, draft, lambda: now, True), 'occupied')
            publisher.send.assert_not_called()
            later = now + timedelta(minutes=31)
            state_time.now.return_value = later
            self.assertEqual(daily.run(ledger, publisher, lambda *_: recovered, lambda: later, True),
                             'published')
            self.assertEqual(daily.run(ledger, publisher, draft, lambda: later, True), 'published')
            publisher.send.assert_called_once_with(recovered['text'], publisher.attach.return_value)
