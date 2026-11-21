/* LINUX-02: общая часть драйверов сравнения (diff_<модуль>.c). Как в LINUX-01 (harness/diff_main.c): генератор xorshift64*,
 * порции по CHUNK проверок в отдельных процессах — падение перевода (паника Rust → abort, сигнал) засчитывает всю порцию
 * как расхождения (верхняя граница). Новое:
 *   --boundary — генератор крайних значений (пустой вход, 0, наибольшие значения, длины на границах блоков и буферов):
 *                вместе с другим зерном и большим N это независимый поиск, по которому решается, меняет ли мутант
 *                поведение (план пилота);
 *   журнал вызовов внешних функций (kalloc_log.h) — сверяется у оригинала и перевода;
 *   охранные буферы входов (gbuf) — чтение за концом входа роняет процесс, как в ядре на границе страницы.
 *   diff_<модуль> [N] [--seed S] [--boundary] → JSON в stdout. */
#pragma once
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include "kalloc_log.h"

#ifndef CHUNK
#define CHUNK 500
#endif

static u64 g_s;
static int g_boundary;
static u64 rnd(void) { g_s ^= g_s >> 12; g_s ^= g_s << 25; g_s ^= g_s >> 27; return g_s * 0x2545F4914F6CDD1DULL; }
static u64 rnd_below(u64 n) { return n ? rnd() % n : 0; }

/* число: смесь случайных, малых, степеней двойки, близких к наибольшему; в режиме границ — только крайние */
static u64 pick64(void)
{
	if (g_boundary) {
		static const u64 B[] = { 0, 1, 2, 3, 7, 8, 63, 64, 255, 256, 4095, 4096, 0x7fffffffULL, 0x80000000ULL, 0xffffffffULL,
					 0x100000000ULL, 0x7fffffffffffffffULL, 0x8000000000000000ULL, ~0ULL - 1, ~0ULL };
		return B[rnd_below(ARRAY_SIZE(B))];
	}
	switch (rnd() % 7) {
	case 0: return rnd();
	case 1: return rnd() & 0xFFFF;
	case 2: return rnd() % 100;
	case 3: return 1ULL << (rnd() % 64);
	case 4: return ~0ULL - (rnd() % 4);
	case 5: return rnd() & 0xFFFFFFFFULL;
	default: return rnd() >> (rnd() % 64);
	}
}

/* длина до max: в режиме границ — 0, 1, max−1, max и кратные block ± 1 */
static size_t pick_len(size_t max, size_t block)
{
	if (g_boundary) {
		size_t c[8] = { 0, 1, max ? max - 1 : 0, max, block, block ? block - 1 : 0, block + 1, 2 * block };
		size_t v = c[rnd_below(8)];
		return v > max ? max : v;
	}
	switch (rnd() % 4) {
	case 0: return rnd_below(max + 1);
	case 1: return rnd_below(max < 16 ? max + 1 : 17);
	case 2: { size_t b = block ? block * rnd_below(max / (block ? block : 1) + 1) : 0; size_t v = b + rnd_below(3) - 1; return v > max ? max : v; }
	default: return max - rnd_below(max < 4 ? max + 1 : 4);
	}
}

static void rand_fill(u8 *p, size_t n)
{
	int kind = rnd() % 4;
	for (size_t i = 0; i < n; i++) {
		switch (kind) {
		case 0: p[i] = (u8)rnd(); break;
		case 1: p[i] = (u8)(rnd() % 4); break;                   /* мало разных байтов — повторы */
		case 2: p[i] = (rnd() % 3) ? 0 : (u8)rnd(); break;       /* много нулей */
		default: p[i] = (u8)(i & 0xff); break;
		}
	}
}

/* журнал внешних вызовов: снимок и сравнение */
struct klog_snap { int n; int overflow; struct klog_entry e[256]; };
static void klog_take(struct klog_snap *s)
{
	s->n = kalloc_log_n < 256 ? kalloc_log_n : 256;
	s->overflow = kalloc_log_overflow || kalloc_log_n > 256;
	memcpy(s->e, kalloc_log, (size_t)s->n * sizeof(s->e[0]));
}
static int klog_equal(const struct klog_snap *a, const struct klog_snap *b)
{
	if (a->n != b->n || a->overflow != b->overflow)
		return 0;
	for (int i = 0; i < a->n; i++)
		if (a->e[i].op != b->e[i].op || a->e[i].arg != b->e[i].arg)
			return 0;
	return 1;
}

/* Охранные буферы (разбор, Н10): данные кладутся вплотную к странице без доступа — чтение или запись за конец данных роняет
 * процесс (падение порции = расхождения), как в ядре на границе страницы. У каждой стороны (оригинал, перевод) — своя копия;
 * после вызова копия сверяется с исходными данными (запись во входной буфер — расхождение). Область создаётся один раз. */
#include <sys/mman.h>
struct gbuf { u8 *end; size_t cap; };
static void gbuf_init(struct gbuf *g, size_t cap)
{
	if (g->end)
		return;
	size_t pg = (size_t)sysconf(_SC_PAGESIZE), span = (cap + pg - 1) / pg * pg;
	u8 *p = mmap(NULL, span + pg, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (p == MAP_FAILED || mprotect(p + span, pg, PROT_NONE)) {
		perror("gbuf");
		exit(2);
	}
	g->end = p + span;
	g->cap = span;
}
/* копия n байт src так, что за последним байтом — недоступная страница; возвращает начало копии */
static void *gbuf_put(struct gbuf *g, const void *src, size_t n)
{
	if (n > g->cap) {
		fprintf(stderr, "gbuf: %zu > %zu\n", n, g->cap);
		exit(2);
	}
	u8 *p = g->end - n;
	if (n)
		memcpy(p, src, n);
	return p;
}

typedef int (*check_fn)(char *ex, size_t exn);
struct fn { const char *name; check_fn f; };

/* Пример расхождения в JSON (разбор, Н12; ERRORS № 219): верные последовательности UTF-8 (кириллица сообщений) идут как есть,
 * всякий другой байт ≥ 0x80 (сырые байты входа) и управляющие — как \u00XX. Так JSON всегда верный UTF-8. */
static int utf8_len(const unsigned char *p)
{
	int n = p[0] >= 0xC2 && p[0] <= 0xDF ? 2 : p[0] >= 0xE0 && p[0] <= 0xEF ? 3 : p[0] >= 0xF0 && p[0] <= 0xF4 ? 4 : 0;
	for (int i = 1; i < n; i++)
		if ((p[i] & 0xC0) != 0x80)
			return 0;
	return n;
}
static void json_puts(const char *p)
{
	const unsigned char *q = (const unsigned char *)p;
	while (*q) {
		unsigned char c = *q;
		int n = c >= 0x80 ? utf8_len(q) : 1;
		if (c == '"' || c == '\\') { printf("\\%c", c); q++; }
		else if (c < 0x20 || c == 0x7f || (c >= 0x80 && n == 0)) { printf("\\u%04x", c); q++; }
		else { fwrite(q, 1, (size_t)n, stdout); q += n; }
	}
}

static void run_fn(const struct fn *F, long n, u64 seed, int *first)
{
	long mism = 0, crashed_chunks = 0, done = 0;
	char example[300] = "";
	for (long start = 0; start < n; start += CHUNK) {
		long m = (n - start) < CHUNK ? (n - start) : CHUNK;
		u64 chunk_seed = seed ^ (u64)(start + 1) * 0x9E3779B97F4A7C15ULL;
		int fd[2];
		if (pipe(fd) != 0) { perror("pipe"); exit(2); }
		fflush(stdout);
		pid_t pid = fork();
		if (pid == 0) {
			close(fd[0]);
			alarm(600);
			g_s = chunk_seed | 1;
			long bad = 0;
			char ex[300] = "";
			for (long i = 0; i < m; i++) {
				char e[300] = "";
				if (F->f(e, sizeof(e))) { bad++; if (!ex[0]) memcpy(ex, e, sizeof(ex)); }
			}
			if (write(fd[1], &bad, sizeof(bad)) != sizeof(bad) || write(fd[1], ex, sizeof(ex)) != sizeof(ex)) _exit(3);
			_exit(0);
		}
		close(fd[1]);
		long bad = 0;
		char ex[300] = "";
		ssize_t g1 = read(fd[0], &bad, sizeof(bad));
		ssize_t g2 = read(fd[0], ex, sizeof(ex));
		close(fd[0]);
		int st = 0;
		waitpid(pid, &st, 0);
		if (!(WIFEXITED(st) && WEXITSTATUS(st) == 0) || g1 != sizeof(bad) || g2 != sizeof(ex)) {
			crashed_chunks++;
			mism += m;
			if (!example[0]) snprintf(example, sizeof(example), "падение в порции с проверки %ld (сигнал, паника или зависание)", start);
		} else {
			mism += bad;
			if (!example[0] && ex[0]) memcpy(example, ex, sizeof(example));
		}
		done += m;
	}
	printf("%s\"%s\": {\"n\": %ld, \"mismatches\": %ld, \"crashed_chunks\": %ld, \"example\": \"", *first ? "" : ", ", F->name, done, mism, crashed_chunks);
	json_puts(example);
	printf("\"}");
	*first = 0;
}

static int diff_main(const struct fn *list, int cnt, int argc, char **argv)
{
	long n = 20000;
	u64 seed = 0xC0FFEE00ULL;
	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--boundary")) g_boundary = 1;
		else if (!strcmp(argv[i], "--seed") && i + 1 < argc) seed = strtoull(argv[++i], NULL, 0);
		else n = atol(argv[i]);
	}
	int first = 1;
	printf("{\"boundary\": %s, \"seed\": %llu, \"fns\": {", g_boundary ? "true" : "false", (unsigned long long)seed);
	for (int i = 0; i < cnt; i++)
		run_fn(&list[i], n, seed + (u64)i * 7919ULL, &first);
	printf("}}\n");
	return 0;
}

#define DIFF_EX(...) do { snprintf(ex, exn, __VA_ARGS__); return 1; } while (0)
