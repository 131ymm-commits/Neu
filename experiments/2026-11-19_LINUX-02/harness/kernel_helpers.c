/* LINUX-02: функции ядра и среды, которые нужны модулям, их тестам и драйверам сравнения. Перенесены из исходников ядра
 * 7.4-rc3 там, где их поведение влияет на результат: lib/kstrtox.c и lib/vsprintf.c (simple_strto*, как в LINUX-01),
 * lib/hexdump.c (hex_asc, hex_to_bin), lib/crc/crc32-main.c и gen_crc32table.c (crc32_be: таблица MSB-first, полином 0x04c11db7).
 * get_options/get_option — сам lib/cmdline.c (src/lib/cmdline.c, собирается с -Dskip_spaces=harness_skip_spaces, чтобы не
 * брать skip_spaces у проверяемого string_helpers). Выделение памяти пишет журнал вызовов: драйвер сравнения сверяет журналы
 * оригинала и перевода. Случайные байты — детерминированный поток xorshift64*, сбрасывается harness_random_reset().
 * SPDX: GPL-2.0, как исходники ядра (перенесённые части). */
#include <stdarg.h>
#include <stdlib.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include "kalloc_log.h"

#define KSTRTOX_OVERFLOW (1U << 31)

static const char *_parse_integer_fixup_radix(const char *s, unsigned int *base)
{
	if (*base == 0) {
		if (s[0] == '0') {
			if (_tolower(s[1]) == 'x' && isxdigit(s[2]))
				*base = 16;
			else
				*base = 8;
		} else
			*base = 10;
	}
	if (*base == 16 && s[0] == '0' && _tolower(s[1]) == 'x')
		s += 2;
	return s;
}

static unsigned int _parse_integer_limit(const char *s, unsigned int base, unsigned long long *p,
					 size_t max_chars, unsigned long long init)
{
	unsigned int rv, overflow = 0;
	unsigned long long res;

	res = init;
	for (rv = 0; rv < max_chars; rv++, s++) {
		unsigned int c = (unsigned char)*s;
		unsigned int lc = _tolower(c);
		unsigned int val;

		if (isdigit(c))
			val = c - '0';
		else if ('a' <= lc && lc <= 'f')
			val = lc - 'a' + 10;
		else
			break;

		if (val >= base)
			break;
		if (unlikely(res & (~0ull << 60))) {
			if (check_mul_overflow(res, base, &res) ||
			    check_add_overflow(res, val, &res)) {
				res = ULLONG_MAX;
				overflow = KSTRTOX_OVERFLOW;
			}
		} else {
			res = res * base + val;
		}
	}
	*p = res;
	return rv | overflow;
}

static unsigned long long simple_strntoull(const char *startp, char **endp, unsigned int base, size_t max_chars)
{
	const char *cp;
	unsigned long long result = 0ULL;
	size_t prefix_chars;
	unsigned int rv;

	cp = _parse_integer_fixup_radix(startp, &base);
	prefix_chars = cp - startp;
	if (prefix_chars < max_chars) {
		rv = _parse_integer_limit(cp, base, &result, max_chars - prefix_chars, 0);
		cp += (rv & ~KSTRTOX_OVERFLOW);
	} else {
		cp = startp + max_chars;
	}

	if (endp)
		*endp = (char *)cp;

	return result;
}

unsigned long long simple_strtoull(const char *cp, char **endp, unsigned int base)
{
	return simple_strntoull(cp, endp, base, INT_MAX);
}

unsigned long simple_strtoul(const char *cp, char **endp, unsigned int base)
{
	return simple_strtoull(cp, endp, base);
}

long simple_strtol(const char *cp, char **endp, unsigned int base)
{
	if (*cp == '-')
		return -simple_strtoul(cp + 1, endp, base);

	return simple_strtoul(cp, endp, base);
}

ssize_t strscpy(char *dest, const char *src, size_t count)
{
	size_t n = strlen(src);
	if (count == 0)
		return -7;
	if (n >= count) {
		memcpy(dest, src, count - 1);
		dest[count - 1] = '\0';
		return -7;			/* -E2BIG */
	}
	memcpy(dest, src, n + 1);
	return (ssize_t)n;
}


char *harness_skip_spaces(const char *str)
{
	while (isspace(*str))
		++str;
	return (char *)str;
}

/* lib/hexdump.c (hex_to_bin — дословно) */
const char hex_asc[] = "0123456789abcdef";
const char hex_asc_upper[] = "0123456789ABCDEF";
int hex_to_bin(unsigned char ch)
{
	unsigned char cu = ch & 0xdf;
	return -1 +
		((ch - '0' +  1) & (unsigned)((ch - '9' - 1) & ('0' - 1 - ch)) >> 8) +
		((cu - 'A' + 11) & (unsigned)((cu - 'F' - 1) & ('A' - 1 - cu)) >> 8);
}

/* lib/crc/crc32-main.c: crc32_be_base с таблицей из gen_crc32table.c (crc32init_be) */
static u32 crc32table_be[256];
static int crc32table_ready;
static void crc32init_be(void)
{
	unsigned i, j;
	u32 crc = 0x80000000;
	crc32table_be[0] = 0;
	for (i = 1; i < 256; i <<= 1) {
		crc = (crc << 1) ^ ((crc & 0x80000000) ? 0x04c11db7 : 0);
		for (j = 0; j < i; j++)
			crc32table_be[i + j] = crc ^ crc32table_be[j];
	}
	crc32table_ready = 1;
}
u32 crc32_be(u32 crc, const u8 *p, size_t len)
{
	if (!crc32table_ready)
		crc32init_be();
	kalloc_log_add(KLOG_CRC32_BE, len);
	while (len--)
		crc = (crc << 8) ^ crc32table_be[(crc >> 24) ^ *p++];
	return crc;
}

/* журнал вызовов внешних функций (для сравнения оригинала и перевода) */
struct klog_entry kalloc_log[KLOG_MAX];
int kalloc_log_n;
int kalloc_log_overflow;
int harness_kmalloc_fail_at = -1;
static int harness_kmalloc_calls;
void kalloc_log_reset(void) { kalloc_log_n = 0; kalloc_log_overflow = 0; harness_kmalloc_calls = 0; }
/* отказ выделения по заказу драйвера: тот же номер вызова у обеих сторон */
static int harness_inject_fail(void) { return harness_kmalloc_fail_at >= 0 && harness_kmalloc_calls++ == harness_kmalloc_fail_at; }
void kalloc_log_add(int op, size_t arg)
{
	if (kalloc_log_n < KLOG_MAX)
		kalloc_log[kalloc_log_n++] = (struct klog_entry){ op, arg };
	else
		kalloc_log_overflow = 1;
}

/* выделение памяти (include/linux/slab.h): поведение — как у успешного kmalloc; флаги не влияют, кроме __GFP_ZERO */
void *kmalloc(size_t size, gfp_t flags)
{
	if (harness_inject_fail() || size > KMALLOC_MAX_SIZE_K) {   /* отказ по заказу; как ядро: больше KMALLOC_MAX_SIZE (4 МиБ) — NULL */
		kalloc_log_add(KLOG_KMALLOC_FAIL, size);
		return NULL;
	}
	kalloc_log_add(KLOG_KMALLOC, size);
	void *p = malloc(size ? size : 1);
	if (p && (flags & __GFP_ZERO))
		memset(p, 0, size);
	return p;
}
void *kzalloc(size_t size, gfp_t flags) { return kmalloc(size, flags | __GFP_ZERO); }
void *kmalloc_array(size_t n, size_t size, gfp_t flags)
{
	size_t bytes;
	if (__builtin_mul_overflow(n, size, &bytes)) {
		kalloc_log_add(KLOG_KMALLOC_FAIL, n);
		return NULL;
	}
	return kmalloc(bytes, flags);
}
void *kcalloc(size_t n, size_t size, gfp_t flags) { return kmalloc_array(n, size, flags | __GFP_ZERO); }
void *krealloc(const void *p, size_t new_size, gfp_t flags)
{
	(void)flags;
	if (harness_inject_fail()) {
		kalloc_log_add(KLOG_KMALLOC_FAIL, new_size);
		return NULL;
	}
	kalloc_log_add(KLOG_KREALLOC, new_size);
	return realloc((void *)p, new_size ? new_size : 1);
}
void kfree(const void *p)
{
	kalloc_log_add(KLOG_KFREE, p != NULL);
	free((void *)p);
}
char *kstrdup(const char *s, gfp_t gfp)
{
	if (!s)
		return NULL;
	size_t n = strlen(s) + 1;
	char *d = kmalloc(n, gfp);
	if (d)
		memcpy(d, s, n);
	return d;
}
char *kstrndup(const char *s, size_t max, gfp_t gfp)
{
	if (!s)
		return NULL;
	size_t n = strnlen(s, max);
	char *d = kmalloc(n + 1, gfp);
	if (d) {
		memcpy(d, s, n);
		d[n] = '\0';
	}
	return d;
}
void *kmemdup(const void *src, size_t len, gfp_t gfp)
{
	void *p = kmalloc(len, gfp);
	if (p)
		memcpy(p, src, len);
	return p;
}
char *kasprintf(gfp_t gfp, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	int n = vsnprintf(NULL, 0, fmt, ap);
	va_end(ap);
	char *p = kmalloc((size_t)n + 1, gfp);
	if (!p)
		return NULL;
	va_start(ap, fmt);
	vsnprintf(p, (size_t)n + 1, fmt, ap);
	va_end(ap);
	return p;
}
void *memdup_user_nul(const void *src, size_t len)
{
	char *p = kmalloc(len + 1, GFP_KERNEL);
	if (!p)
		return ERR_PTR(-ENOMEM);
	memcpy(p, src, len);
	p[len] = '\0';
	return p;
}
/* vmalloc: буфер, за которым сразу идёт недоступная страница (как ждёт alloc_guarded_buf в шаблоне тестов хешей) */
void *vmalloc(unsigned long size)
{
	size_t full = (size + PAGE_SIZE - 1) / PAGE_SIZE * PAGE_SIZE;
	char *p = mmap(NULL, full + PAGE_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (p == MAP_FAILED)
		return NULL;
	mprotect(p + full, PAGE_SIZE, PROT_NONE);
	return p;
}
void vfree(const void *p) { (void)p; }    /* случай идёт в своём процессе — память вернётся при выходе */

/* заглушки ядра для string_helpers (kstrdup_quotable_cmdline, kstrdup_quotable_file, devm_kasprintf_strarray): данные задаёт
 * драйвер перед парой вызовов — одинаковые для оригинала и перевода (разбор, Н2). По умолчанию — прежние постоянные данные. */
static char harness_cmdline[8192] = "prog\0arg one\0\tx\001\0";
static int harness_cmdline_n = 17;
void harness_set_cmdline(const char *p, int n)
{
	if (n < 0) n = 0;
	if (n > (int)sizeof(harness_cmdline)) n = (int)sizeof(harness_cmdline);
	memcpy(harness_cmdline, p, (size_t)n);
	harness_cmdline_n = n;
}
int get_cmdline(struct task_struct *task, char *buffer, int buflen)
{
	(void)task;
	kalloc_log_add(KLOG_GET_CMDLINE, (size_t)buflen);
	int n = harness_cmdline_n;
	if (n > buflen)
		n = buflen;
	memcpy(buffer, harness_cmdline, (size_t)n);
	return n;
}
static char harness_path[8192] = "/tmp/a b\\c\"\177";
static int harness_path_err;
void harness_set_file_path(const char *path, int err)
{
	size_t n = strlen(path);
	if (n >= sizeof(harness_path)) n = sizeof(harness_path) - 1;
	memcpy(harness_path, path, n);
	harness_path[n] = '\0';
	harness_path_err = err;
}
/* как d_path ядра: путь кладётся в конец буфера; не помещается (с NUL) — ERR_PTR(-ENAMETOOLONG) */
char *file_path(struct file *file, char *buf, int buflen)
{
	kalloc_log_add(KLOG_FILE_PATH, (size_t)buflen);
	if (!file)
		return ERR_PTR(-ENOENT);
	if (harness_path_err)
		return ERR_PTR(-harness_path_err);
	size_t n = strlen(harness_path) + 1;
	if ((int)n > buflen)
		return ERR_PTR(-ENAMETOOLONG_K);
	char *p = buf + buflen - n;
	memcpy(p, harness_path, n);
	return p;
}
void *harness_devres_res;
void (*harness_devres_release)(struct device *dev, void *res);
void *__devres_alloc_node(dr_release_t release, size_t size, gfp_t gfp, int nid, const char *name)
{
	(void)nid; (void)name;
	kalloc_log_add(KLOG_DEVRES_ALLOC, size);
	harness_devres_release = release;
	harness_devres_res = NULL;
	return kzalloc(size, gfp);
}
void devres_add(struct device *dev, void *res) { (void)dev; harness_devres_res = res; kalloc_log_add(KLOG_DEVRES_ADD, 0); }
void devres_free(void *res) { kalloc_log_add(KLOG_DEVRES_FREE, res != NULL); free(res); }

/* случайные числа: xorshift64*, один поток на процесс; сбрасывается драйвером перед парой вызовов оригинал / перевод */
static u64 harness_rng = 0x9E3779B97F4A7C15ULL;
void harness_random_reset(u64 seed) { harness_rng = seed ? seed : 0x9E3779B97F4A7C15ULL; }
static u64 harness_next(void)
{
	harness_rng ^= harness_rng >> 12;
	harness_rng ^= harness_rng << 25;
	harness_rng ^= harness_rng >> 27;
	return harness_rng * 0x2545F4914F6CDD1DULL;
}
static int harness_small;
void harness_random_small(int on) { harness_small = on; }
void get_random_bytes(void *buf, size_t len)
{
	kalloc_log_add(KLOG_RANDOM_BYTES, len);
	u8 *p = buf;
	while (len) {
		u64 v = harness_next();
		if (harness_small) {                     /* каждое 32-битное слово — малое (< 131) с вероятностью 1/2 */
			u32 w[2] = { (u32)v, (u32)(v >> 32) };
			u64 c = harness_next();
			for (int i = 0; i < 2; i++)
				if ((c >> i) & 1)
					w[i] = (u32)((c >> (8 + 16 * i)) % 131);
			memcpy(&v, w, 8);
		}
		size_t k = len < 8 ? len : 8;
		memcpy(p, &v, k);
		p += k;
		len -= k;
	}
}
u32 get_random_u32(void) { return (u32)(harness_next() >> 32); }
u32 get_random_u32_below(u32 ceil) { return ceil ? (u32)(((u64)get_random_u32() * ceil) >> 32) : 0; }
u8 get_random_u8(void) { return (u8)(harness_next() >> 56); }

/* время и процессоры */
unsigned long harness_jiffies(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (unsigned long)ts.tv_sec * 1000UL + (unsigned long)(ts.tv_nsec / 1000000);
}
u64 ktime_get_ns(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
}
/* процессоры по маске сродства процесса (не все на машине): под taskset или квотой гонке негде идти (разбор, Н5) */
unsigned int num_online_cpus(void)
{
	unsigned long mask[16] = { 0 };            /* до 1024 процессоров; системный вызов — без _GNU_SOURCE */
	long r = syscall(SYS_sched_getaffinity, 0, sizeof(mask), mask);
	if (r > 0) {
		int n = 0;
		for (long i = 0; i < r / (long)sizeof(long); i++)
			n += __builtin_popcountl(mask[i]);
		if (n > 0)
			return (unsigned int)n;
	}
	long n = sysconf(_SC_NPROCESSORS_ONLN);
	return n > 0 ? (unsigned int)n : 1;
}
void cond_resched(void) { sched_yield(); }

/* kthread на pthreads: kthread_should_stop() читает флаг своей нити */
struct task_struct { pthread_t th; int (*fn)(void *); void *data; volatile int stop; };
static __thread struct task_struct *harness_current;
static void *harness_kthread_main(void *p)
{
	struct task_struct *t = p;
	harness_current = t;
	t->fn(t->data);
	return NULL;
}
struct task_struct *kthread_run(int (*fn)(void *), void *data, const char *namefmt, ...)
{
	(void)namefmt;
	struct task_struct *t = calloc(1, sizeof(*t));
	if (!t)
		return ERR_PTR(-ENOMEM);
	t->fn = fn;
	t->data = data;
	if (pthread_create(&t->th, NULL, harness_kthread_main, t) != 0) {
		free(t);
		return ERR_PTR(-ENOMEM);
	}
	return t;
}
bool kthread_should_stop(void) { return harness_current && harness_current->stop; }
int kthread_stop(struct task_struct *t)
{
	t->stop = 1;
	pthread_join(t->th, NULL);
	free(t);
	return 0;
}
