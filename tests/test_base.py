import unittest
import time
from contextlib import suppress
from queue import Queue as ThreadQueue
from threading import Thread
from threading import Event as ThreadEvent

import numpy as np

from pdp.base import InterruptableQueue, StopEvent, start_one2one_transformer

DEFAULT_LOOP_TIMEOUT = 0.02


def set_event_after_timeout(event, timeout):
    def target():
        time.sleep(timeout)
        event.set()

    Thread(target=target).start()


class TestInterruptableQueue(unittest.TestCase):
    def setUp(self):
        self.maxsize = 10
        self.loop_timeout = DEFAULT_LOOP_TIMEOUT
        self.wait_timeout = 7.5 * self.loop_timeout
        self.receive_timeout = 0.5 * self.loop_timeout

        self.stop_event = ThreadEvent()
        self.q = InterruptableQueue(ThreadQueue(self.maxsize), self.loop_timeout, self.stop_event)

    def test_get(self):
        def target():
            with suppress(StopEvent):
                self.q.get()

        thread = Thread(target=target)
        thread.start()
        self.assertTrue(thread.is_alive())
        set_event_after_timeout(event=self.stop_event, timeout=self.wait_timeout + self.receive_timeout)
        self.assertTrue(thread.is_alive())
        time.sleep(self.wait_timeout)
        self.assertTrue(thread.is_alive())
        time.sleep(self.receive_timeout * 2)
        self.assertFalse(thread.is_alive())

    def test_put(self):
        for i in range(self.maxsize):
            self.q.put(i)

        def target():
            with suppress(StopEvent):
                self.q.put(-1)

        thread = Thread(target=target)
        thread.start()

        self.assertTrue(thread.is_alive())
        set_event_after_timeout(event=self.stop_event, timeout=self.wait_timeout + self.receive_timeout)
        self.assertTrue(thread.is_alive())
        time.sleep(self.wait_timeout)
        self.assertTrue(thread.is_alive())
        time.sleep(self.receive_timeout * 2)
        self.assertFalse(thread.is_alive())


class testOne2One(unittest.TestCase):
    def setUp(self):
        self.buffer_size = 20
        self.loop_timeout = DEFAULT_LOOP_TIMEOUT
        self.stop_event = ThreadEvent()
        self.q_in = InterruptableQueue(ThreadQueue(self.buffer_size), self.loop_timeout, self.stop_event)
        self.q_out = InterruptableQueue(ThreadQueue(self.buffer_size), self.loop_timeout, self.stop_event)

    def tearDown(self):
        self.q_in.join()
        self.q_out.join()

    def data_pass(self, n_workers):
        data_in = np.random.randn(self.buffer_size * 10)

        def f(x):
            return x ** 2

        data_out_true = f(data_in)

        start_one2one_transformer(f, q_in=self.q_in, q_out=self.q_out, stop_event=self.stop_event, n_workers=n_workers)

        i = 0
        data_out = []
        for d in data_in:
            self.q_in.put(d)
            i += 1

            if i == self.buffer_size:
                for j in range(self.buffer_size):
                    data_out.append(self.q_out.get())
                    self.q_out.task_done()
                i = 0

        if n_workers > 1:
            data_out_true = sorted(data_out_true)
            data_out = sorted(data_out)

        np.testing.assert_equal(data_out, data_out_true)

    def test_data_pass(self):
        for n_workers in (1, 4, 10):
            with self.subTest(f'n_workers={n_workers}'):
                self.data_pass(n_workers=n_workers)
