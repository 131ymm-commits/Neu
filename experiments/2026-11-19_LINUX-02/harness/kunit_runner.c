/* LINUX-02: исполнитель тестов KUnit вне ядра (расширение LINUX-01). Каждый случай и каждый его параметр идёт в отдельном
 * процессе: падение перевода (паника Rust → abort, сигнал) — провал этого случая, остальные идут дальше. Время на случай —
 * не больше KUNIT_CASE_TIMEOUT секунд (зависание — провал).
 * Новое: ASSERT при провале прекращает случай; kunit_skip — случай пропущен; случай без единого утверждения — «пустой»
 * (план пилота: пустой случай пройденным не считается); init/exit набора и случая.
 * Вывод — JSON в stdout: по случаю — имя, параметр, утверждений, провалов, упал ли, пропущен ли, пустой ли, ok. */
#include <signal.h>
#include <stdarg.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <kunit/test.h>

#define MAX_SUITES 16
#define KUNIT_CASE_TIMEOUT 120
static struct kunit_suite *g_suites[MAX_SUITES];
static int g_nsuites;
static int g_out_fd = -1;

void kunit_register_suites(struct kunit_suite **suites)
{
	for (; *suites && g_nsuites < MAX_SUITES; suites++)
		g_suites[g_nsuites++] = *suites;
}

void kunit_record(struct kunit *test, int ok, const char *file, int line, const char *what, const char *fmt, ...)
{
	__atomic_add_fetch(&test->expectations, 1, __ATOMIC_SEQ_CST);
	if (!ok) {
		int f = __atomic_add_fetch(&test->failures, 1, __ATOMIC_SEQ_CST);
		if (f <= 3) {
			char msg[256] = "";
			va_list ap;
			va_start(ap, fmt);
			vsnprintf(msg, sizeof(msg), fmt, ap);
			va_end(ap);
			fprintf(stderr, "  ПРОВАЛ %s:%d %s %s\n", file, line, what, msg);
		}
	}
}

static void finish_child(struct kunit *test) __attribute__((noreturn));
static void finish_child(struct kunit *test)
{
	int out[3] = { test->expectations, test->failures, test->skipped };
	if (write(g_out_fd, out, sizeof(out)) != (ssize_t)sizeof(out))
		_exit(3);
	_exit(0);
}

void kunit_abort_case(struct kunit *test) { finish_child(test); }

void kunit_skip_case(struct kunit *test, const char *fmt, ...)
{
	(void)fmt;
	test->skipped = 1;
	finish_child(test);
}

void *kunit_kmalloc(struct kunit *test, size_t size, gfp_t gfp)
{
	(void)test;
	void *p = malloc(size ? size : 1);
	if (p && (gfp & __GFP_ZERO))
		memset(p, 0, size);
	return p;
}
void *kunit_kzalloc(struct kunit *test, size_t size, gfp_t gfp) { return kunit_kmalloc(test, size, gfp | __GFP_ZERO); }
void *kunit_kmalloc_array(struct kunit *test, size_t n, size_t size, gfp_t gfp)
{
	size_t b;
	if (__builtin_mul_overflow(n, size, &b))
		return NULL;
	return kunit_kmalloc(test, b, gfp);
}

static void json_str(const char *s)
{
	putchar('"');
	for (; s && *s; s++) {
		unsigned char c = (unsigned char)*s;
		if (c == '"' || c == '\\')
			printf("\\%c", c);
		else if (c < 0x20)
			printf("\\u%04x", c);
		else
			putchar(c);
	}
	putchar('"');
}

static void run_one(struct kunit_suite *suite, const struct kunit_case *kc, const void *param, int res[3], int *crashed)
{
	int fd[2];
	if (pipe(fd) != 0) {
		perror("pipe");
		exit(2);
	}
	fflush(stdout);
	pid_t pid = fork();
	if (pid == 0) {
		struct kunit t = { .param_value = param, .name = kc->name };
		close(fd[0]);
		g_out_fd = fd[1];
		alarm(KUNIT_CASE_TIMEOUT);
		if (suite->init && suite->init(&t) != 0) {
			kunit_record(&t, 0, __FILE__, __LINE__, "suite init", "");
			finish_child(&t);
		}
		kc->run_case(&t);
		if (suite->exit)
			suite->exit(&t);
		finish_child(&t);
	}
	close(fd[1]);
	int in[3] = { 0, 0, 0 };
	ssize_t got = read(fd[0], in, sizeof(in));
	close(fd[0]);
	int status = 0;
	waitpid(pid, &status, 0);
	*crashed = !(WIFEXITED(status) && WEXITSTATUS(status) == 0) || got != (ssize_t)sizeof(in);
	memcpy(res, in, sizeof(in));
}

int main(void)
{
	int first = 1, total = 0, failed = 0, skipped = 0, empty = 0;
	printf("{\"cases\": [");
	for (int s = 0; s < g_nsuites; s++) {
		struct kunit_suite *suite = g_suites[s];
		if (suite->suite_init && suite->suite_init(suite) != 0) {
			fprintf(stderr, "suite_init %s не прошёл\n", suite->name);
			continue;
		}
		for (struct kunit_case *kc = suite->test_cases; kc->run_case; kc++) {
			const void *param = 0;
			char desc[KUNIT_PARAM_DESC_SIZE];
			for (;;) {
				desc[0] = '\0';
				if (kc->generate_params) {
					param = kc->generate_params(param, desc);
					if (!param)
						break;
				}
				int res[3] = { 0, 0, 0 }, crashed = 0;
				run_one(suite, kc, param, res, &crashed);
				int is_skip = !crashed && res[2];
				int is_empty = !crashed && !is_skip && res[0] == 0;
				int ok = !crashed && !is_skip && res[1] == 0 && res[0] > 0;
				total++;
				failed += !ok && !is_skip;
				skipped += is_skip;
				empty += is_empty;
				printf("%s{\"suite\": ", first ? "" : ", ");
				json_str(suite->name);
				printf(", \"case\": ");
				json_str(kc->name);
				printf(", \"param\": ");
				json_str(desc);
				printf(", \"expectations\": %d, \"failures\": %d, \"crashed\": %s, \"skipped\": %s, \"empty\": %s, \"ok\": %s}",
				       res[0], res[1], crashed ? "true" : "false", is_skip ? "true" : "false", is_empty ? "true" : "false",
				       ok ? "true" : "false");
				first = 0;
				if (!kc->generate_params)
					break;
			}
		}
		if (suite->suite_exit)
			suite->suite_exit(suite);
	}
	printf("], \"total\": %d, \"failed\": %d, \"skipped\": %d, \"empty\": %d}\n", total, failed, skipped, empty);
	return 0;
}
