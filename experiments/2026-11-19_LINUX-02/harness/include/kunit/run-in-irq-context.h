/* LINUX-02: замена kunit_run_irq_test (include/kunit/run-in-irq-context.h). В ядре функция вызывается из задачи, из hardirq
 * (таймер) и из softirq (BH-работа) вперемежку — так проверяется, что код не держит общего состояния между вызовами.
 * Здесь: задача — вызывающий поток, «hardirq» и «softirq» — два потока pthreads, которые зовут ту же функцию одновременно с
 * задачей. Это истинная параллельность, а не вытеснение на одном процессоре; ожидания — те же пять, что в ядре. */
#pragma once
#include <kunit/test.h>
#include <pthread.h>
#include <time.h>

struct __kunit_irq_ctx {
	bool (*func)(void *);
	void *state;
	volatile int stop;
	atomic_t calls;
	volatile bool failed;
};

static void *__kunit_irq_thread(void *p)
{
	struct __kunit_irq_ctx *c = p;
	while (!c->stop) {
		if (!c->func(c->state))
			c->failed = true;
		atomic_inc(&c->calls);
	}
	return NULL;
}

static inline void kunit_run_irq_test(struct kunit *test, bool (*func)(void *), int max_iterations, void *test_specific_state)
{
	struct __kunit_irq_ctx hard = { .func = func, .state = test_specific_state };
	struct __kunit_irq_ctx soft = { .func = func, .state = test_specific_state };
	pthread_t th, ts;
	bool task_failed = false;
	int task_calls = 0;
	unsigned long end = harness_jiffies() + HZ;

	pthread_create(&th, NULL, __kunit_irq_thread, &hard);
	pthread_create(&ts, NULL, __kunit_irq_thread, &soft);
	do {
		if (!func(test_specific_state))
			task_failed = true;
		task_calls++;
	} while ((task_calls + atomic_read(&hard.calls) + atomic_read(&soft.calls) < max_iterations ||
		  atomic_read(&hard.calls) == 0 || atomic_read(&soft.calls) == 0) && !time_after(harness_jiffies(), end));
	hard.stop = 1;
	soft.stop = 1;
	pthread_join(th, NULL);
	pthread_join(ts, NULL);
	KUNIT_EXPECT_GT_MSG(test, atomic_read(&hard.calls), 0, "Timer function was not called");
	KUNIT_EXPECT_GT_MSG(test, atomic_read(&soft.calls), 0, "BH work function was not called");
	KUNIT_EXPECT_FALSE_MSG(test, task_failed, "Failure reported from task context");
	KUNIT_EXPECT_FALSE_MSG(test, hard.failed, "Failure reported from hardirq context");
	KUNIT_EXPECT_FALSE_MSG(test, soft.failed, "Failure reported from softirq context");
}
