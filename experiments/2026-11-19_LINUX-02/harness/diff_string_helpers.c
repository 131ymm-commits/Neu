/* LINUX-02: сравнение перевода lib/string_helpers.c с оригиналом — каждая экспортируемая функция своей проверкой.
 * Строки — случайные байты с перекосом к экранированиям, пробелам (в том числе 160), кавычкам, \n, NUL; флаги — любые
 * подмножества ESCAPE_ALL_MASK и UNESCAPE_ALL_MASK; размеры выходных буферов — 0…, буферы с запасом и заливкой (запись
 * за пределы видна). Функции, которые выделяют память, сравниваются ещё и по журналу вызовов kmalloc / kfree / devres.
 * Указатели в возврате сравниваются как смещения от начала своего буфера. */
#include <linux/string_helpers.h>
#include "diff_common.h"

#define O(name) orig_##name
int O(string_get_size)(u64 size, u64 blk_size, const enum string_size_units units, char *buf, int len);
int O(parse_int_array)(const char *buf, size_t count, int **array);
int O(parse_int_array_user)(const char *from, size_t count, int **array);
int O(string_unescape)(char *src, char *dst, size_t size, unsigned int flags);
int O(string_escape_mem)(const char *src, size_t isz, char *dst, size_t osz, unsigned int flags, const char *only);
char *O(kstrdup_quotable)(const char *src, gfp_t gfp);
char *O(kstrdup_quotable_cmdline)(struct task_struct *task, gfp_t gfp);
char *O(kstrdup_quotable_file)(struct file *file, gfp_t gfp);
char *O(kstrdup_and_replace)(const char *src, char old, char new, gfp_t gfp);
char **O(kasprintf_strarray)(gfp_t gfp, const char *prefix, size_t n);
void O(kfree_strarray)(char **array, size_t n);
char **O(devm_kasprintf_strarray)(struct device *dev, const char *prefix, size_t n);
char *O(skip_spaces)(const char *str);
char *O(strim)(char *s);
bool O(sysfs_streq)(const char *s1, const char *s2);
int O(match_string)(const char *const *array, size_t n, const char *string);
int O(__sysfs_match_string)(const char *const *array, size_t n, const char *str);
char *O(strreplace)(char *str, char old, char new);
void O(memcpy_and_pad)(void *dest, size_t dest_len, const void *src, size_t count, int pad);
char *kstrdup_quotable(const char *src, gfp_t gfp);
char *kstrdup_quotable_cmdline(struct task_struct *task, gfp_t gfp);
char *kstrdup_quotable_file(struct file *file, gfp_t gfp);
char *kstrdup_and_replace(const char *src, char old, char new, gfp_t gfp);
char **kasprintf_strarray(gfp_t gfp, const char *prefix, size_t n);
void kfree_strarray(char **array, size_t n);
char **devm_kasprintf_strarray(struct device *dev, const char *prefix, size_t n);
char *strim(char *s);
bool sysfs_streq(const char *s1, const char *s2);
int match_string(const char *const *array, size_t n, const char *string);
int __sysfs_match_string(const char *const *array, size_t n, const char *str);
void memcpy_and_pad(void *dest, size_t dest_len, const void *src, size_t count, int pad);
char *skip_spaces(const char *str);

static const char ALPHA[] = "\\\\\\abtnvfre\"' \t\n\x0b\x0c\r0123456789xXabcdefABCDEF,-;:=.\x7f\x80\xa0\xff\x01\x1b";
/* случайная строка до max байт без NUL (NUL-окончание дописывается) */
static size_t rand_str(char *buf, size_t max)
{
	size_t n = g_boundary ? pick_len(max, 8) : rnd_below(max + 1);
	for (size_t i = 0; i < n; i++)
		buf[i] = (rnd() % 4) ? ALPHA[rnd_below(sizeof(ALPHA) - 1)] : (char)(1 + rnd_below(255));
	buf[n] = '\0';
	return n;
}
static size_t rand_mem(char *buf, size_t max)
{
	size_t n = rand_str(buf, max);
	for (size_t k = 0; k < n; k++)
		if (rnd() % 30 == 0)
			buf[k] = '\0';                                  /* в памяти встречается NUL */
	return n;
}

static int c_get_size(char *ex, size_t exn)
{
	char ba[40], bb[40];
	u64 size = pick64(), blk = (rnd() % 3) ? (1ULL << rnd_below(16)) : pick64();
	unsigned int units = (unsigned int)rnd_below(2) | ((rnd() % 2) ? STRING_UNITS_NO_SPACE : 0) | ((rnd() % 2) ? STRING_UNITS_NO_BYTES : 0);
	int len = (int)rnd_below(24);
	memset(ba, 'Z', sizeof(ba));
	memset(bb, 'Z', sizeof(bb));
	int ra = O(string_get_size)(size, blk, units, ba, len), rb = string_get_size(size, blk, units, bb, len);
	if (ra != rb || memcmp(ba, bb, sizeof(ba)))
		DIFF_EX("string_get_size(%llu, %llu, %#x, len %d): %d против %d, «%.20s» против «%.20s»",
			(unsigned long long)size, (unsigned long long)blk, units, len, ra, rb, ba, bb);
	return 0;
}

static int c_unescape(char *ex, size_t exn)
{
	char src[260], sa[260], sb[260], da[600], db[600];
	rand_str(src, 250);
	unsigned int flags = (unsigned int)rnd_below(16);
	int inplace = rnd() % 3 == 0;
	size_t size = (rnd() % 3) ? rnd_below(300) : 0;
	memcpy(sa, src, sizeof(src));
	memcpy(sb, src, sizeof(src));
	memset(da, 'Q', sizeof(da));
	memset(db, 'Q', sizeof(db));
	int ra, rb;
	if (inplace) { ra = O(string_unescape)(sa, sa, 0, flags); rb = string_unescape(sb, sb, 0, flags); }
	else { ra = O(string_unescape)(sa, da, size, flags); rb = string_unescape(sb, db, size, flags); }
	if (ra != rb || memcmp(da, db, sizeof(da)) || memcmp(sa, sb, sizeof(sa)))
		DIFF_EX("string_unescape(%s, size %zu, flags %#x, длина входа %zu): %d против %d", inplace ? "на месте" : "в буфер", size, flags, strlen(src), ra, rb);
	return 0;
}

static int c_escape(char *ex, size_t exn)
{
	char src[200], only[12], da[1000], db[1000];
	size_t isz = rand_mem(src, 150);
	int with_only = rnd() % 3 == 0;
	if (with_only) rand_str(only, 8);
	unsigned int flags = (unsigned int)rnd_below(1u << 9);
	int nulldst = rnd() % 8 == 0;
	size_t osz = nulldst ? 0 : (rnd() % 3 ? rnd_below(700) : 900);
	memset(da, 'Q', sizeof(da));
	memset(db, 'Q', sizeof(db));
	int ra = O(string_escape_mem)(src, isz, nulldst ? NULL : da, osz, flags, with_only ? only : NULL);
	int rb = string_escape_mem(src, isz, nulldst ? NULL : db, osz, flags, with_only ? only : NULL);
	if (ra != rb || memcmp(da, db, sizeof(da)))
		DIFF_EX("string_escape_mem(isz %zu, osz %zu, flags %#x, only %s): %d против %d", isz, osz, flags, with_only ? "есть" : "NULL", ra, rb);
	return 0;
}

static int cmp_alloc_str(char *ex, size_t exn, const char *what, char *a, char *b, const struct klog_snap *la, const struct klog_snap *lb)
{
	int bad = (!a) != (!b) || (a && b && strcmp(a, b)) || !klog_equal(la, lb);
	if (bad)
		snprintf(ex, exn, "%s: «%.40s» против «%.40s», вызовов kmalloc/kfree %d против %d", what, a ? a : "NULL", b ? b : "NULL", la->n, lb->n);
	free(a);
	free(b);
	return bad;
}

static int c_quotable(char *ex, size_t exn)
{
	char src[200];
	rand_str(src, 150);
	int which = (int)rnd_below(4), nullsrc = rnd() % 10 == 0, nullfile = rnd() % 4 == 0;
	char oldc = src[0] ? src[rnd_below(strlen(src))] : 'x', newc = (char)rnd();
	struct file *fakefile = nullfile ? NULL : (struct file *)(uintptr_t)0x1000;
	struct klog_snap la, lb;
	char *a = NULL, *b = NULL;
	static const char *NAMES[] = { "kstrdup_quotable", "kstrdup_quotable_cmdline", "kstrdup_quotable_file", "kstrdup_and_replace" };
	kalloc_log_reset();
	switch (which) {
	case 0: a = O(kstrdup_quotable)(nullsrc ? NULL : src, GFP_KERNEL); break;
	case 1: a = O(kstrdup_quotable_cmdline)(NULL, GFP_KERNEL); break;
	case 2: a = O(kstrdup_quotable_file)(fakefile, GFP_KERNEL); break;
	default: a = O(kstrdup_and_replace)(src, oldc, newc, GFP_KERNEL); break;
	}
	klog_take(&la);
	kalloc_log_reset();
	switch (which) {
	case 0: b = kstrdup_quotable(nullsrc ? NULL : src, GFP_KERNEL); break;
	case 1: b = kstrdup_quotable_cmdline(NULL, GFP_KERNEL); break;
	case 2: b = kstrdup_quotable_file(fakefile, GFP_KERNEL); break;
	default: b = kstrdup_and_replace(src, oldc, newc, GFP_KERNEL); break;
	}
	klog_take(&lb);
	return cmp_alloc_str(ex, exn, NAMES[which], a, b, &la, &lb);
}

static int c_strarray(char *ex, size_t exn)
{
	char prefix[20];
	rand_str(prefix, 10);
	for (char *q = prefix; *q; q++)
		if (*q == '%') *q = 'p';
	size_t n = g_boundary ? pick_len(40, 8) : rnd_below(41);
	int devm = rnd() % 3 == 0;
	struct klog_snap la, lb;
	kalloc_log_reset();
	char **a = devm ? O(devm_kasprintf_strarray)(NULL, prefix, n) : O(kasprintf_strarray)(GFP_KERNEL, prefix, n);
	klog_take(&la);
	kalloc_log_reset();
	char **b = devm ? devm_kasprintf_strarray(NULL, prefix, n) : kasprintf_strarray(GFP_KERNEL, prefix, n);
	klog_take(&lb);
	int bad = IS_ERR_OR_NULL(a) != IS_ERR_OR_NULL(b) || !klog_equal(&la, &lb);
	if (!bad && !IS_ERR_OR_NULL(a))
		for (size_t k = 0; k < n; k++)
			if ((!a[k]) != (!b[k]) || (a[k] && strcmp(a[k], b[k]))) { bad = 1; break; }
	if (bad)
		DIFF_EX("%s(«%s», %zu): разные массивы или вызовы (%d против %d)", devm ? "devm_kasprintf_strarray" : "kasprintf_strarray", prefix, n, la.n, lb.n);
	if (!devm && a && b) {
		kalloc_log_reset();
		O(kfree_strarray)(a, n);
		klog_take(&la);
		kalloc_log_reset();
		kfree_strarray(b, n);
		klog_take(&lb);
		if (!klog_equal(&la, &lb))
			DIFF_EX("kfree_strarray(%zu): разные вызовы kfree (%d против %d)", n, la.n, lb.n);
	}
	return 0;
}

static int c_parse_int(char *ex, size_t exn)
{
	char buf[200];
	size_t n = rnd_below(12);
	size_t pos = 0;
	long prev = 0;
	for (size_t k = 0; k < n && pos < 150; k++) {
		long v = (long)(rnd_below(2000)) - 1000;
		if (rnd() % 8 == 0) v = (long)(int)rnd();
		/* «a-b» get_options разворачивает в b − a + 1 чисел: диапазон — только узкий (иначе миллиарды чисел и нехватка памяти) */
		/* обрезка строки (parse_int_array_user) превращает «-900--870» в «-900--8»: концы диапазона — только малые по модулю */
		int range = k && rnd() % 6 == 0 && prev > -100000 && prev < 100000;
		if (range) v = prev + (long)rnd_below(40) - 5;
		pos += (size_t)snprintf(buf + pos, sizeof(buf) - pos, "%s%ld", k ? (range ? "-" : (rnd() % 5 ? "," : " ")) : "", v);
		prev = v;
	}
	if (rnd() % 5 == 0 && pos < 190) buf[pos++] = (char)ALPHA[rnd_below(sizeof(ALPHA) - 1)];
	buf[pos] = '\0';
	size_t count = (rnd() % 4) ? pos : rnd_below(pos + 1);
	int user = rnd() % 2;
	int *aa = NULL, *ab = NULL;
	struct klog_snap la, lb;
	kalloc_log_reset();
	int ra = user ? O(parse_int_array_user)(buf, count, &aa) : O(parse_int_array)(buf, count, &aa);
	klog_take(&la);
	kalloc_log_reset();
	int rb = user ? parse_int_array_user(buf, count, &ab) : parse_int_array(buf, count, &ab);
	klog_take(&lb);
	int bad = ra != rb || !klog_equal(&la, &lb) || (!aa) != (!ab);
	if (!bad && ra == 0 && aa && ab && (aa[0] != ab[0] || memcmp(aa, ab, sizeof(int) * (size_t)(aa[0] + 1))))
		bad = 1;
	if (bad)
		DIFF_EX("parse_int_array%s(«%.40s», %zu): %d против %d", user ? "_user" : "", buf, count, ra, rb);
	return 0;
}

static int c_small(char *ex, size_t exn)
{
	char s[160], a[200], b[200];
	rand_str(s, 120);
	int which = (int)rnd_below(5);
	memset(a, 'Q', sizeof(a));
	memset(b, 'Q', sizeof(b));
	memcpy(a, s, strlen(s) + 1);
	memcpy(b, s, strlen(s) + 1);
	long ra = 0, rb = 0;
	switch (which) {
	case 0: ra = O(skip_spaces)(a) - a; rb = skip_spaces(b) - b; break;
	case 1: ra = O(strim)(a) - a; rb = strim(b) - b; break;
	case 2: { char o = a[0] ? a[rnd_below(strlen(a))] : 'x', nw = (char)rnd(); ra = O(strreplace)(a, o, nw) - a; rb = strreplace(b, o, nw) - b; break; }
	case 3: { char t[160]; memcpy(t, s, sizeof(t)); if (rnd() % 2) { size_t l = strlen(t); if (l + 1 < sizeof(t)) { t[l] = '\n'; t[l + 1] = 0; } }
		if (rnd() % 3 == 0) rand_str(t, 20);
		ra = O(sysfs_streq)(s, t); rb = sysfs_streq(s, t); break; }
	default: { char pad[100], da[120], db[120]; size_t dl = rnd_below(100), cnt = rnd_below(100); int pv = (int)rnd();
		rand_fill((u8 *)pad, sizeof(pad)); memset(da, 'Q', sizeof(da)); memset(db, 'Q', sizeof(db));
		O(memcpy_and_pad)(da, dl, pad, cnt, pv); memcpy_and_pad(db, dl, pad, cnt, pv);
		if (memcmp(da, db, sizeof(da))) DIFF_EX("memcpy_and_pad(%zu, %zu, %d): разные буферы", dl, cnt, pv); break; }
	}
	if (ra != rb || memcmp(a, b, sizeof(a)))
		DIFF_EX("функция %d на «%.40s»: %ld против %ld", which, s, ra, rb);
	return 0;
}

static int c_match(char *ex, size_t exn)
{
	char store[8][24];
	const char *arr[9];
	size_t n = rnd_below(8);
	for (size_t k = 0; k < n; k++) {
		rand_str(store[k], 6);
		arr[k] = (rnd() % 8 == 0) ? NULL : store[k];
	}
	arr[n] = NULL;
	char q[40];
	if (n && rnd() % 2) { const char *src = store[rnd_below(n)]; snprintf(q, sizeof(q), "%s%s", src, rnd() % 2 ? "\n" : ""); }
	else rand_str(q, 6);
	size_t nn = (rnd() % 3 == 0) ? (size_t)-1 : n;
	int sys = rnd() % 2;
	int ra = sys ? O(__sysfs_match_string)(arr, nn, q) : O(match_string)(arr, nn, q);
	int rb = sys ? __sysfs_match_string(arr, nn, q) : match_string(arr, nn, q);
	if (ra != rb)
		DIFF_EX("%s(n %zd, «%s»): %d против %d", sys ? "__sysfs_match_string" : "match_string", (ssize_t)nn, q, ra, rb);
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "string_get_size", c_get_size }, { "string_unescape", c_unescape }, { "string_escape_mem", c_escape },
				       { "kstrdup_quotable_and_co", c_quotable }, { "kasprintf_strarray", c_strarray },
				       { "parse_int_array", c_parse_int }, { "small_functions", c_small }, { "match_string", c_match } };
	return diff_main(L, 8, argc, argv);
}
