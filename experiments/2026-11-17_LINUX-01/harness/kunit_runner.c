/* LINUX-01: исполнитель тестов KUnit вне ядра. Каждый случай (и каждый параметр случая) идёт в отдельном процессе:
 * падение перевода (паника Rust → abort, сигнал) считается провалом этого случая и не останавливает остальные.
 * Вывод — JSON в stdout: по случаю — имя, параметр, ожиданий, провалов, упал ли. */
#include <stdarg.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <kunit/test.h>

#define MAX_SUITES 16
static struct kunit_suite *g_suites[MAX_SUITES];
static int g_nsuites;

void kunit_register_suites(struct kunit_suite **suites)
{
	for (; *suites && g_nsuites < MAX_SUITES; suites++)
		g_suites[g_nsuites++] = *suites;
}

void kunit_record(struct kunit *test, int ok, const char *file, int line, const char *what, const char *fmt, ...)
{
	test->expectations++;
	if (!ok) {
		test->failures++;
		if (test->failures <= 3) {
			char msg[256] = "";
			va_list ap;
			va_start(ap, fmt);
			vsnprintf(msg, sizeof(msg), fmt, ap);
			va_end(ap);
			fprintf(stderr, "  ПРОВАЛ %s:%d %s %s\n", file, line, what, msg);
		}
	}
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

/* один прогон в дочернем процессе; результат — через канал: ожиданий и провалов */
static void run_one(const struct kunit_case *kc, const void *param, int *exp, int *fail, int *crashed)
{
	int fd[2];
	if (pipe(fd) != 0) {
		perror("pipe");
		exit(2);
	}
	fflush(stdout);
	pid_t pid = fork();
	if (pid == 0) {
		struct kunit t = { .param_value = param };
		close(fd[0]);
		kc->run_case(&t);
		int out[2] = { t.expectations, t.failures };
		if (write(fd[1], out, sizeof(out)) != (ssize_t)sizeof(out))
			_exit(3);
		_exit(0);
	}
	close(fd[1]);
	int in[2] = { 0, 0 };
	ssize_t got = read(fd[0], in, sizeof(in));
	close(fd[0]);
	int status = 0;
	waitpid(pid, &status, 0);
	*crashed = !(WIFEXITED(status) && WEXITSTATUS(status) == 0) || got != (ssize_t)sizeof(in);
	*exp = in[0];
	*fail = in[1];
}

int main(void)
{
	int first = 1, total = 0, failed = 0;
	printf("{\"cases\": [");
	for (int s = 0; s < g_nsuites; s++) {
		for (struct kunit_case *kc = g_suites[s]->test_cases; kc->run_case; kc++) {
			const void *param = 0;
			char desc[KUNIT_PARAM_DESC_SIZE];
			for (;;) {
				desc[0] = '\0';
				if (kc->generate_params) {
					param = kc->generate_params(param, desc);
					if (!param)
						break;
				}
				int exp = 0, fail = 0, crashed = 0;
				run_one(kc, param, &exp, &fail, &crashed);
				int ok = !crashed && fail == 0 && exp > 0;
				total++;
				failed += !ok;
				printf("%s{\"suite\": ", first ? "" : ", ");
				json_str(g_suites[s]->name);
				printf(", \"case\": ");
				json_str(kc->name);
				printf(", \"param\": ");
				json_str(desc);
				printf(", \"expectations\": %d, \"failures\": %d, \"crashed\": %s, \"ok\": %s}",
				       exp, fail, crashed ? "true" : "false", ok ? "true" : "false");
				first = 0;
				if (!kc->generate_params)
					break;
			}
		}
	}
	printf("], \"total\": %d, \"failed\": %d}\n", total, failed);
	return 0;
}
