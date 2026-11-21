/* LINUX-01: сравнение перевода с оригиналом на случайных входах. Оригинал собран с переименованием (orig_*),
 * перевод — под настоящими именами. Входы — из генератора xorshift64* с фиксированным зерном на функцию; порциями по 1000
 * в отдельном процессе: падение перевода засчитывает всю порцию как расхождения. Вывод — JSON.
 *   diff_main MODULE [N]      MODULE: int_pow | int_sqrt | gcd | rational | int_log | cmdline */
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

/* бинарник собирается под один модуль: функции остальных модулей объявлены слабыми и не вызываются */
#define W __attribute__((weak))
W u64 orig_int_pow(u64 base, unsigned int exp);
W unsigned long orig_int_sqrt(unsigned long x);
W unsigned long orig_gcd(unsigned long a, unsigned long b);
W void orig_rational_best_approximation(unsigned long, unsigned long, unsigned long, unsigned long, unsigned long *, unsigned long *);
W unsigned int orig_intlog2(u32 value);
W unsigned int orig_intlog10(u32 value);
W int orig_get_option(char **str, int *pint);
W char *orig_get_options(const char *str, int nints, int *ints);
W unsigned long long orig_memparse(const char *ptr, char **retptr);
W bool orig_parse_option_str(const char *str, const char *option);
W char *orig_next_arg(char *args, char **param, char **val);
#pragma weak int_pow
#pragma weak int_sqrt
#pragma weak gcd
#pragma weak rational_best_approximation
#pragma weak intlog2
#pragma weak intlog10
#pragma weak get_option
#pragma weak get_options
#pragma weak memparse
#pragma weak parse_option_str
#pragma weak next_arg

static u64 g_s;
static u64 rnd(void) { g_s ^= g_s >> 12; g_s ^= g_s << 25; g_s ^= g_s >> 27; return g_s * 0x2545F4914F6CDD1DULL; }
static u64 pick64(void)
{
	switch (rnd() % 7) {
	case 0: return rnd();
	case 1: return rnd() & 0xFFFF;
	case 2: return rnd() % 100;
	case 3: return 1ULL << (rnd() % 64);
	case 4: return ~0ULL - (rnd() % 4);
	case 5: { u64 k = rnd() & 0xFFFFFFFFULL; return k * k + (rnd() % 3) - 1; }
	default: return rnd() >> (rnd() % 64);
	}
}

static void rand_str(char *buf, size_t cap, const char *alphabet, int with_nbsp)
{
	size_t n = rnd() % (cap - 1), la = strlen(alphabet);
	for (size_t i = 0; i < n; i++)
		buf[i] = (with_nbsp && rnd() % 40 == 0) ? (char)0xA0 : alphabet[rnd() % la];
	buf[n] = '\0';
}

/* одна проверка; возвращает 1 при расхождении и пишет пример в ex */
typedef int (*check_fn)(char *ex, size_t exn);

static int c_int_pow(char *ex, size_t exn)
{
	u64 b = pick64(); unsigned int e = rnd() % 130;
	u64 a = orig_int_pow(b, e), c = int_pow(b, e);
	if (a != c) { snprintf(ex, exn, "int_pow(%llu, %u): %llu против %llu", (unsigned long long)b, e, (unsigned long long)a, (unsigned long long)c); return 1; }
	return 0;
}
static int c_int_sqrt(char *ex, size_t exn)
{
	unsigned long x = pick64();
	unsigned long a = orig_int_sqrt(x), c = int_sqrt(x);
	if (a != c) { snprintf(ex, exn, "int_sqrt(%lu): %lu против %lu", x, a, c); return 1; }
	return 0;
}
static int c_gcd(char *ex, size_t exn)
{
	unsigned long x = pick64(), y = pick64();
	unsigned long a = orig_gcd(x, y), c = gcd(x, y);
	if (a != c) { snprintf(ex, exn, "gcd(%lu, %lu): %lu против %lu", x, y, a, c); return 1; }
	return 0;
}
static unsigned long pick_num(void)
{
	switch (rnd() % 5) {
	case 0: return rnd() % 1000;
	case 1: return rnd() % 100000;
	case 2: return pick64();
	case 3: return 0;
	default: return rnd() % 300;
	}
}
static int c_rational(char *ex, size_t exn)
{
	unsigned long gn = pick_num(), gd = pick_num(), mn = pick_num(), md = pick_num();
	unsigned long an = 7, ad = 7, cn = 7, cd = 7;
	orig_rational_best_approximation(gn, gd, mn, md, &an, &ad);
	rational_best_approximation(gn, gd, mn, md, &cn, &cd);
	if (an != cn || ad != cd) {
		snprintf(ex, exn, "rational(%lu/%lu, max %lu/%lu): %lu/%lu против %lu/%lu", gn, gd, mn, md, an, ad, cn, cd);
		return 1;
	}
	return 0;
}
static int c_intlog2(char *ex, size_t exn)
{
	u32 v = (u32)pick64();
	unsigned int a = orig_intlog2(v), c = intlog2(v);
	if (a != c) { snprintf(ex, exn, "intlog2(%u): %u против %u", v, a, c); return 1; }
	return 0;
}
static int c_intlog10(char *ex, size_t exn)
{
	u32 v = (u32)pick64();
	unsigned int a = orig_intlog10(v), c = intlog10(v);
	if (a != c) { snprintf(ex, exn, "intlog10(%u): %u против %u", v, a, c); return 1; }
	return 0;
}

static const char *ALPHA = "0123456789,-+ \"=xXkKmMgGtTpPeEaz\t";
static int c_get_option(char *ex, size_t exn)
{
	char b1[32], b2[32];
	rand_str(b1, sizeof(b1), ALPHA, 1);
	memcpy(b2, b1, sizeof(b1));
	char *p1 = b1, *p2 = b2;
	int v1 = 0x5A5A5A5A, v2 = 0x5A5A5A5A;
	int r1 = orig_get_option(&p1, &v1), r2 = get_option(&p2, &v2);
	if (r1 != r2 || v1 != v2 || (p1 - b1) != (p2 - b2)) {
		snprintf(ex, exn, "get_option(\"%s\"): (%d, %d, +%td) против (%d, %d, +%td)", b1, r1, v1, p1 - b1, r2, v2, p2 - b2);
		return 1;
	}
	return 0;
}
static int c_get_options(char *ex, size_t exn)
{
	static const int NS[] = { 0, 1, 2, 3, 5, 8, 16 };
	char s[32];
	rand_str(s, sizeof(s), "0123456789,-+ a", 0);
	int nints = NS[rnd() % 7];
	int a1[40], a2[40];
	for (int i = 0; i < 40; i++) a1[i] = a2[i] = 0x5A5A5A5A;
	char *r1 = orig_get_options(s, nints, a1), *r2 = get_options(s, nints, a2);
	if ((r1 - s) != (r2 - s) || memcmp(a1, a2, sizeof(a1)) != 0) {
		snprintf(ex, exn, "get_options(\"%s\", %d): +%td, [0]=%d против +%td, [0]=%d", s, nints, r1 - s, a1[0], r2 - s, a2[0]);
		return 1;
	}
	return 0;
}
static int c_memparse(char *ex, size_t exn)
{
	char s[40];
	if (rnd() % 3 == 0) {
		int n = 1 + rnd() % 24, i = 0;
		if (rnd() % 2) { s[i++] = '0'; s[i++] = (rnd() % 2) ? 'x' : 'X'; }
		for (; i < n; i++) s[i] = "0123456789abcdefABCDEF"[rnd() % 22];
		s[i++] = "kKmMgGtTpPeEz@ ,"[rnd() % 16];
		s[i] = '\0';
	} else
		rand_str(s, sizeof(s), "xkKmMgGtTpPeEaz@:,0123456789", 0);
	char *e1 = 0, *e2 = 0;
	unsigned long long r1 = orig_memparse(s, &e1), r2 = memparse(s, &e2);
	if (r1 != r2 || (e1 - s) != (e2 - s)) {
		snprintf(ex, exn, "memparse(\"%s\"): (%llu, +%td) против (%llu, +%td)", s, r1, e1 - s, r2, e2 - s);
		return 1;
	}
	return 0;
}
static int c_parse_option_str(char *ex, size_t exn)
{
	static const char *T[] = { "ro", "rw", "a", "b", "noacpi", "", "ro=1", "r" };
	char s[64] = "";
	int k = rnd() % 5;
	for (int i = 0; i < k; i++) {
		strcat(s, T[rnd() % 8]);
		if (i + 1 < k || rnd() % 4 == 0) strcat(s, ",");
	}
	const char *opt = T[rnd() % 8];
	bool r1 = orig_parse_option_str(s, opt), r2 = parse_option_str(s, opt);
	if (r1 != r2) { snprintf(ex, exn, "parse_option_str(\"%s\", \"%s\"): %d против %d", s, opt, r1, r2); return 1; }
	return 0;
}
static int c_next_arg(char *ex, size_t exn)
{
	char b1[48], b2[48];
	memset(b1, 0, sizeof(b1));
	rand_str(b1, sizeof(b1), "ab=\" \tcd=e", 1);
	memcpy(b2, b1, sizeof(b1));
	char show[48];
	memcpy(show, b1, sizeof(b1));
	char *pa1 = 0, *va1 = 0, *pa2 = 0, *va2 = 0;
	char *r1 = orig_next_arg(b1, &pa1, &va1), *r2 = next_arg(b2, &pa2, &va2);
	int bad = (r1 - b1) != (r2 - b2) || (pa1 - b1) != (pa2 - b2) || (!va1) != (!va2) || (va1 && (va1 - b1) != (va2 - b2))
		  || memcmp(b1, b2, sizeof(b1)) != 0;
	if (bad) {
		snprintf(ex, exn, "next_arg(\"%s\"): ret +%td param +%td val %s против ret +%td param +%td val %s", show, r1 - b1, pa1 - b1,
			 va1 ? "есть" : "NULL", r2 - b2, pa2 - b2, va2 ? "есть" : "NULL");
		return 1;
	}
	return 0;
}

struct fn { const char *name; check_fn f; };

static void run_fn(const struct fn *F, long n, u64 seed, int *first)
{
	long mism = 0, crashed_chunks = 0, done = 0;
	char example[300] = "";
	g_s = seed;
	for (long start = 0; start < n; start += 1000) {
		long m = (n - start) < 1000 ? (n - start) : 1000;
		u64 chunk_seed = seed ^ (u64)(start + 1) * 0x9E3779B97F4A7C15ULL;
		int fd[2];
		if (pipe(fd) != 0) { perror("pipe"); exit(2); }
		fflush(stdout);
		pid_t pid = fork();
		if (pid == 0) {
			close(fd[0]);
			g_s = chunk_seed | 1;
			long bad = 0;
			char ex[300] = "";
			for (long i = 0; i < m; i++) {
				char e[300];
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
			if (!example[0]) snprintf(example, sizeof(example), "падение в порции с входа %ld (сигнал или паника)", start);
		} else {
			mism += bad;
			if (!example[0] && ex[0]) memcpy(example, ex, sizeof(example));
		}
		done += m;
	}
	printf("%s\"%s\": {\"n\": %ld, \"mismatches\": %ld, \"crashed_chunks\": %ld, \"example\": \"", *first ? "" : ", ", F->name, done, mism, crashed_chunks);
	for (const char *p = example; *p; p++) {
		unsigned char c = (unsigned char)*p;
		if (c == '"' || c == '\\') printf("\\%c", c);
		else if (c < 0x20) printf("\\u%04x", c);
		else putchar(c);
	}
	printf("\"}");
	*first = 0;
}

int main(int argc, char **argv)
{
	const char *mod = argc > 1 ? argv[1] : "";
	long n = argc > 2 ? atol(argv[2]) : 100000;
	static const struct fn MATH[][2] = {
		{ { "int_pow", c_int_pow }, { 0, 0 } }, { { "int_sqrt", c_int_sqrt }, { 0, 0 } }, { { "gcd", c_gcd }, { 0, 0 } },
		{ { "rational_best_approximation", c_rational }, { 0, 0 } }, { { "intlog2", c_intlog2 }, { "intlog10", c_intlog10 } },
	};
	static const struct fn CMD[] = { { "get_option", c_get_option }, { "get_options", c_get_options }, { "memparse", c_memparse },
					 { "parse_option_str", c_parse_option_str }, { "next_arg", c_next_arg } };
	const struct fn *list = 0;
	int cnt = 0;
	if (!strcmp(mod, "int_pow")) { list = MATH[0]; cnt = 1; }
	else if (!strcmp(mod, "int_sqrt")) { list = MATH[1]; cnt = 1; }
	else if (!strcmp(mod, "gcd")) { list = MATH[2]; cnt = 1; }
	else if (!strcmp(mod, "rational")) { list = MATH[3]; cnt = 1; }
	else if (!strcmp(mod, "int_log")) { list = MATH[4]; cnt = 2; }
	else if (!strcmp(mod, "cmdline")) { list = CMD; cnt = 5; }
	else { fprintf(stderr, "неизвестный модуль %s\n", mod); return 2; }
	int first = 1;
	printf("{");
	for (int i = 0; i < cnt; i++)
		run_fn(&list[i], n, 0xC0FFEE00ULL + (u64)i * 7919ULL, &first);
	printf("}\n");
	return 0;
}
