/* LINUX-02: сравнение перевода lib/string_helpers.c с оригиналом — каждая экспортируемая функция своей проверкой.
 * Строки — случайные байты с перекосом к экранированиям, пробелам (в том числе 160), кавычкам, \n, NUL; флаги — любые
 * подмножества ESCAPE_ALL_MASK и UNESCAPE_ALL_MASK; размеры выходных буферов — 0…, буферы с запасом и заливкой (запись
 * за пределы видна). Функции, которые выделяют память, сравниваются ещё и по журналу вызовов kmalloc / kfree / devres.
 * Указатели в возврате сравниваются как смещения от начала своего буфера.
 * После разбора кода (19.11, до оценки пилота):
 *   - каждый вход у каждой стороны — своя копия вплотную к недоступной странице (gbuf): чтение за концом входа роняет порцию;
 *     вход, который функция не должна менять, сверяется после вызова (Н10);
 *   - get_cmdline отдаёт заданные драйвером байты: пустые, с NUL внутри и в хвосте, длиннее буфера (Н2);
 *   - file_path отдаёт заданный путь (в том числе длиннее буфера) или ошибку (Н2);
 *   - отказ kmalloc по заказу: k-й вызов выделения возвращает NULL у обеих сторон (Н2);
 *   - kfree_strarray(NULL, n) и массивы с NULL внутри (Н2);
 *   - devm_kasprintf_strarray: после вызова обе стороны зовут свой release у ресурса devres, журналы сверяются (Н11). */
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

/* охранные копии входов: сторона 0 — оригинал, 1 — перевод; место — номер аргумента */
#define GSLOTS 12
static struct gbuf GS[2][GSLOTS];
static void *gput(int side, int slot, const void *src, size_t n)
{
	gbuf_init(&GS[side][slot], 8192);
	return gbuf_put(&GS[side][slot], src, n);
}
static char *gstr(int side, int slot, const char *s) { return s ? gput(side, slot, s, strlen(s) + 1) : NULL; }

/* отказ kmalloc по заказу: в четверти проверок k-й вызов выделения (k < kmax) у обеих сторон возвращает NULL */
static int pick_fail(int kmax) { return (rnd() % 4 == 0) ? (int)rnd_below((u64)kmax) : -1; }

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
	char src[260], da[600], db[600];
	size_t n = rand_str(src, 250);
	unsigned int flags = (unsigned int)rnd_below(16);
	int inplace = rnd() % 3 == 0;
	size_t size = (rnd() % 3) ? rnd_below(300) : 0;
	char *sa = gput(0, 0, src, n + 1), *sb = gput(1, 0, src, n + 1);
	memset(da, 'Q', sizeof(da));
	memset(db, 'Q', sizeof(db));
	int ra, rb;
	if (inplace) { ra = O(string_unescape)(sa, sa, 0, flags); rb = string_unescape(sb, sb, 0, flags); }
	else { ra = O(string_unescape)(sa, da, size, flags); rb = string_unescape(sb, db, size, flags); }
	if (ra != rb || memcmp(da, db, sizeof(da)) || memcmp(sa, sb, n + 1))
		DIFF_EX("string_unescape(%s, size %zu, flags %#x, длина входа %zu): %d против %d", inplace ? "на месте" : "в буфер", size, flags, n, ra, rb);
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
	char *sa = gput(0, 0, src, isz), *sb = gput(1, 0, src, isz);
	char *oa = with_only ? gstr(0, 1, only) : NULL, *ob = with_only ? gstr(1, 1, only) : NULL;
	int ra = O(string_escape_mem)(sa, isz, nulldst ? NULL : da, osz, flags, oa);
	int rb = string_escape_mem(sb, isz, nulldst ? NULL : db, osz, flags, ob);
	if (ra != rb || memcmp(da, db, sizeof(da)))
		DIFF_EX("string_escape_mem(isz %zu, osz %zu, flags %#x, only %s): %d против %d", isz, osz, flags, with_only ? "есть" : "NULL", ra, rb);
	if (memcmp(sb, src, isz) || (with_only && strcmp(ob, only)))
		DIFF_EX("string_escape_mem(isz %zu, flags %#x): перевод изменил входной буфер", isz, flags);
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

/* содержимое для get_cmdline: пустое, обычное, с NUL внутри и в хвосте, у границы буфера PAGE_SIZE − 1 и длиннее */
static void set_cmdline(void)
{
	static char buf[5200];
	static const int L[] = { 0, 1, 2, 4093, 4094, 4095, 4096, 4097, 5000 };
	int n = (rnd() % 3 == 0) ? L[rnd_below(ARRAY_SIZE(L))] : (int)rnd_below(200);
	for (int i = 0; i < n; i++)
		buf[i] = (rnd() % 5 == 0) ? '\0' : (rnd() % 4) ? ALPHA[rnd_below(sizeof(ALPHA) - 1)] : (char)(1 + rnd_below(255));
	if (n && rnd() % 3 == 0)
		for (int t = (int)rnd_below(4); t >= 0 && n - 1 - t >= 0; t--)
			buf[n - 1 - t] = '\0';                          /* несколько NUL в хвосте */
	harness_set_cmdline(buf, n);
}
/* путь для file_path: обычный, длиной у границы буфера PATH_MAX + 11, или ошибка */
static void set_file_path(void)
{
	static char p[4200];
	int kind = (int)rnd_below(6);
	size_t n = kind == 4 ? (size_t)(4100 + rnd_below(10)) : rnd_below(120);   /* буфер — PATH_MAX + 11 = 4107 байт с NUL */
	for (size_t i = 0; i < n; i++) {
		char c = (rnd() % 4) ? ALPHA[rnd_below(sizeof(ALPHA) - 1)] : (char)(1 + rnd_below(255));
		p[i] = c ? c : 'x';
	}
	p[n] = '\0';
	harness_set_file_path(p, kind == 5 ? (rnd() % 2 ? ENAMETOOLONG_K : ENOENT) : 0);
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
	if (which == 1) set_cmdline();
	if (which == 2) set_file_path();
	int fail = pick_fail(3);
	char *sa = nullsrc ? NULL : gstr(0, 0, src), *sb = nullsrc ? NULL : gstr(1, 0, src);
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	switch (which) {
	case 0: a = O(kstrdup_quotable)(sa, GFP_KERNEL); break;
	case 1: a = O(kstrdup_quotable_cmdline)(NULL, GFP_KERNEL); break;
	case 2: a = O(kstrdup_quotable_file)(fakefile, GFP_KERNEL); break;
	default: a = O(kstrdup_and_replace)(gstr(0, 0, src), oldc, newc, GFP_KERNEL); break;
	}
	klog_take(&la);
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	switch (which) {
	case 0: b = kstrdup_quotable(sb, GFP_KERNEL); break;
	case 1: b = kstrdup_quotable_cmdline(NULL, GFP_KERNEL); break;
	case 2: b = kstrdup_quotable_file(fakefile, GFP_KERNEL); break;
	default: b = kstrdup_and_replace(gstr(1, 0, src), oldc, newc, GFP_KERNEL); break;
	}
	klog_take(&lb);
	harness_kmalloc_fail_at = -1;
	return cmp_alloc_str(ex, exn, NAMES[which], a, b, &la, &lb);
}

/* массив строк, как у kasprintf_strarray, но с NULL внутри: у каждой стороны свой (освобождает kfree_strarray) */
static char **make_strarray(size_t n, u64 pattern)
{
	char **arr = malloc((n ? n : 1) * sizeof(char *));
	for (size_t k = 0; k < n; k++)
		arr[k] = ((pattern >> (k % 64)) & 1) ? NULL : strdup("x");
	return arr;
}

static int c_strarray(char *ex, size_t exn)
{
	char prefix[20];
	rand_str(prefix, 10);
	for (char *q = prefix; *q; q++)
		if (*q == '%') *q = 'p';
	size_t n = g_boundary ? pick_len(40, 8) : rnd_below(41);
	int mode = (int)rnd_below(6);              /* 0–2 kasprintf_strarray, 3 devm_kasprintf_strarray, 4 kfree_strarray(NULL), 5 массив с NULL */
	struct klog_snap la, lb;
	if (mode >= 4) {
		u64 pat = rnd();
		char **xa = mode == 5 ? make_strarray(n, pat) : NULL, **xb = mode == 5 ? make_strarray(n, pat) : NULL;
		kalloc_log_reset();
		O(kfree_strarray)(xa, n);
		klog_take(&la);
		kalloc_log_reset();
		kfree_strarray(xb, n);
		klog_take(&lb);
		if (!klog_equal(&la, &lb))
			DIFF_EX("kfree_strarray(%s, %zu): разные вызовы kfree (%d против %d)", mode == 5 ? "массив с NULL" : "NULL", n, la.n, lb.n);
		return 0;
	}
	int devm = mode == 3;
	int fail = pick_fail((int)n + 2);
	char *pa = gstr(0, 0, prefix), *pb = gstr(1, 0, prefix);
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	harness_devres_res = NULL;
	harness_devres_release = NULL;
	char **a = devm ? O(devm_kasprintf_strarray)(NULL, pa, n) : O(kasprintf_strarray)(GFP_KERNEL, pa, n);
	klog_take(&la);
	void *res_a = harness_devres_res;
	void (*rel_a)(struct device *, void *) = harness_devres_release;
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	harness_devres_res = NULL;
	harness_devres_release = NULL;
	char **b = devm ? devm_kasprintf_strarray(NULL, pb, n) : kasprintf_strarray(GFP_KERNEL, pb, n);
	klog_take(&lb);
	void *res_b = harness_devres_res;
	void (*rel_b)(struct device *, void *) = harness_devres_release;
	harness_kmalloc_fail_at = -1;
	int bad = IS_ERR_OR_NULL(a) != IS_ERR_OR_NULL(b) || (IS_ERR(a) && a != b) || !klog_equal(&la, &lb);
	if (!bad && !IS_ERR_OR_NULL(a))
		for (size_t k = 0; k < n; k++)
			if ((!a[k]) != (!b[k]) || (a[k] && strcmp(a[k], b[k]))) { bad = 1; break; }
	if (bad)
		DIFF_EX("%s(«%s», %zu, отказ kmalloc %d): разные массивы или вызовы (%d против %d)", devm ? "devm_kasprintf_strarray" : "kasprintf_strarray",
			prefix, n, fail, la.n, lb.n);
	if (devm) {
		/* ядро позовёт release при отключении устройства: зовём сами, у обеих сторон, и сверяем освобождения */
		if ((!res_a) != (!res_b) || (!rel_a) != (!rel_b))
			DIFF_EX("devm_kasprintf_strarray(%zu): ресурс devres %s у оригинала и %s у перевода", n, res_a ? "добавлен" : "не добавлен",
				res_b ? "добавлен" : "не добавлен");
		if (res_a && rel_a) {
			kalloc_log_reset();
			rel_a(NULL, res_a);
			klog_take(&la);
			kalloc_log_reset();
			rel_b(NULL, res_b);
			klog_take(&lb);
			if (!klog_equal(&la, &lb))
				DIFF_EX("devm_kasprintf_strarray(%zu): release освобождает иначе (%d против %d вызовов)", n, la.n, lb.n);
		}
	}
	if (!devm && !IS_ERR_OR_NULL(a) && !IS_ERR_OR_NULL(b)) {
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
	int fail = pick_fail(2);
	/* _user читает ровно count байт (memdup_user_nul); без _user строка читается до NUL */
	const char *ba = user ? gput(0, 0, buf, count) : gstr(0, 0, buf), *bb = user ? gput(1, 0, buf, count) : gstr(1, 0, buf);
	int *aa = NULL, *ab = NULL;
	struct klog_snap la, lb;
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	int ra = user ? O(parse_int_array_user)(ba, count, &aa) : O(parse_int_array)(ba, count, &aa);
	klog_take(&la);
	kalloc_log_reset();
	harness_kmalloc_fail_at = fail;
	int rb = user ? parse_int_array_user(bb, count, &ab) : parse_int_array(bb, count, &ab);
	klog_take(&lb);
	harness_kmalloc_fail_at = -1;
	int bad = ra != rb || !klog_equal(&la, &lb) || (!aa) != (!ab);
	if (!bad && ra == 0 && aa && ab && (aa[0] != ab[0] || memcmp(aa, ab, sizeof(int) * (size_t)(aa[0] + 1))))
		bad = 1;
	if (bad)
		DIFF_EX("parse_int_array%s(«%.40s», %zu, отказ kmalloc %d): %d против %d", user ? "_user" : "", buf, count, fail, ra, rb);
	return 0;
}

static int c_small(char *ex, size_t exn)
{
	char s[160];
	size_t n = rand_str(s, 120);
	int which = (int)rnd_below(5);
	char *a = gput(0, 0, s, n + 1), *b = gput(1, 0, s, n + 1);
	long ra = 0, rb = 0;
	switch (which) {
	case 0: ra = O(skip_spaces)(a) - a; rb = skip_spaces(b) - b; break;
	case 1: ra = O(strim)(a) - a; rb = strim(b) - b; break;
	case 2: { char o = a[0] ? a[rnd_below(strlen(a))] : 'x', nw = (char)rnd(); ra = O(strreplace)(a, o, nw) - a; rb = strreplace(b, o, nw) - b; break; }
	case 3: { char t[160]; memcpy(t, s, sizeof(t)); if (rnd() % 2) { size_t l = strlen(t); if (l + 1 < sizeof(t)) { t[l] = '\n'; t[l + 1] = 0; } }
		if (rnd() % 3 == 0) rand_str(t, 20);
		ra = O(sysfs_streq)(a, gstr(0, 1, t)); rb = sysfs_streq(b, gstr(1, 1, t)); break; }
	default: { char pad[100], da[120], db[120]; size_t dl = rnd_below(100), cnt = rnd_below(100); int pv = (int)rnd();
		rand_fill((u8 *)pad, sizeof(pad)); memset(da, 'Q', sizeof(da)); memset(db, 'Q', sizeof(db));
		O(memcpy_and_pad)(da, dl, gput(0, 1, pad, cnt), cnt, pv); memcpy_and_pad(db, dl, gput(1, 1, pad, cnt), cnt, pv);
		if (memcmp(da, db, sizeof(da))) DIFF_EX("memcpy_and_pad(%zu, %zu, %d): разные буферы", dl, cnt, pv); break; }
	}
	if (ra != rb || memcmp(a, b, n + 1))
		DIFF_EX("функция %d на «%.40s»: %ld против %ld", which, s, ra, rb);
	return 0;
}

static int c_match(char *ex, size_t exn)
{
	char store[8][24];
	const char *arr[9];
	size_t n = rnd_below(8);
	int isnull[8] = { 0 };
	for (size_t k = 0; k < n; k++) {
		rand_str(store[k], 6);
		isnull[k] = rnd() % 8 == 0;
	}
	char q[40];
	if (n && rnd() % 2) { const char *src = store[rnd_below(n)]; snprintf(q, sizeof(q), "%s%s", src, rnd() % 2 ? "\n" : ""); }
	else rand_str(q, 6);
	size_t nn = (rnd() % 3 == 0) ? (size_t)-1 : n;
	int sys = rnd() % 2;
	int r[2];
	for (int side = 0; side < 2; side++) {
		for (size_t k = 0; k < n; k++)
			arr[k] = isnull[k] ? NULL : gstr(side, (int)k, store[k]);
		arr[n] = NULL;
		const char *const *ga = gput(side, 8, arr, (n + 1) * sizeof(arr[0]));   /* массив указателей — тоже вплотную к странице */
		const char *gq = gstr(side, 9, q);
		r[side] = side == 0 ? (sys ? O(__sysfs_match_string)(ga, nn, gq) : O(match_string)(ga, nn, gq))
				    : (sys ? __sysfs_match_string(ga, nn, gq) : match_string(ga, nn, gq));
	}
	if (r[0] != r[1])
		DIFF_EX("%s(n %zd, «%s»): %d против %d", sys ? "__sysfs_match_string" : "match_string", (ssize_t)nn, q, r[0], r[1]);
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "string_get_size", c_get_size }, { "string_unescape", c_unescape }, { "string_escape_mem", c_escape },
				       { "kstrdup_quotable_and_co", c_quotable }, { "kasprintf_strarray", c_strarray },
				       { "parse_int_array", c_parse_int }, { "small_functions", c_small }, { "match_string", c_match } };
	return diff_main(L, 8, argc, argv);
}
