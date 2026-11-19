/* LINUX-02: сравнение перевода lib/min_heap.c (+ встроенные функции include/linux/min_heap.h) с оригиналом. Куча с внешним
 * массивом или с запасным (data == NULL → heap->preallocated сразу за заголовком): размер элемента 1…32 байт (в том числе 3, 5,
 * 12 — не кратные словам), смещение массива 0…4 байта, ёмкость 0…40; less — порядок по первым байтам элемента (с равными ключами:
 * порядок сравнений виден в результате), по возрастанию или убыванию; swp — NULL (выбор встроенного обмена по размеру), свой обмен,
 * явные SWAP_WORDS_32 (размер кратен 4) и SWAP_BYTES. Последовательность до 40 операций: push / pop / pop_push (в том числе при
 * пустой куче: в C это запись data[0]) / del / peek / full / heapify_all (после случайного заполнения) / sift_down (позиция и за
 * концом кучи: в C это пустой ход) / sift_up (в том числе при пустой куче) — del только с позицией внутри кучи: за её пределами
 * оригинал выходит за массив (поведение не определено).
 * После каждой операции сравниваются результат, nr, size, где лежат данные (свой массив или запасной, смещение), весь массив и
 * запасная область, а также журнал обратных вызовов less и swp: вид вызова и адреса аргументов как смещения от начала данных своей
 * стороны (обратные вызовы ядра могут опираться на адреса — разбор, Н7, Н3). */
#include <linux/min_heap.h>
#include "diff_common.h"

void orig___min_heap_init(min_heap_char *heap, void *data, size_t size);
void *orig___min_heap_peek(struct min_heap_char *heap);
bool orig___min_heap_full(min_heap_char *heap);
void orig___min_heap_sift_down(min_heap_char *heap, size_t pos, size_t elem_size, const struct min_heap_callbacks *func, void *args);
void orig___min_heap_sift_up(min_heap_char *heap, size_t elem_size, size_t idx, const struct min_heap_callbacks *func, void *args);
void orig___min_heapify_all(min_heap_char *heap, size_t elem_size, const struct min_heap_callbacks *func, void *args);
bool orig___min_heap_pop(min_heap_char *heap, size_t elem_size, const struct min_heap_callbacks *func, void *args);
void orig___min_heap_pop_push(min_heap_char *heap, const void *element, size_t elem_size, const struct min_heap_callbacks *func, void *args);
bool orig___min_heap_push(min_heap_char *heap, const void *element, size_t elem_size, const struct min_heap_callbacks *func, void *args);
bool orig___min_heap_del(min_heap_char *heap, size_t elem_size, size_t idx, const struct min_heap_callbacks *func, void *args);

#define CAPMAX 40
#define ESMAX 32
struct side {
	u8 raw[CAPMAX * ESMAX + 16];
	u64 heapbuf[(sizeof(min_heap_char) + CAPMAX * ESMAX + 16 + 7) / 8];   /* заголовок кучи и запасной массив за ним */
};

/* журнал обратных вызовов стороны: свёртка FNV-1a по (вид, адрес левого, адрес правого) и счёт */
struct cb_args {
	size_t size, keylen;
	int desc;
	const u8 *base, *el;              /* начало данных своей стороны; элемент, который передаёт драйвер */
	u64 h, n;
};
static long addr_code(const struct cb_args *c, const void *p)
{
	const u8 *q = p;
	if (q == c->el)
		return -1;
	if (q >= c->base && q < c->base + CAPMAX * ESMAX + ESMAX)
		return (long)(q - c->base);
	return -2;                        /* чужой адрес: временная копия и т. п. */
}
static void trace(struct cb_args *c, u64 kind, const void *l, const void *r)
{
	u64 v[3] = { kind, (u64)addr_code(c, l), (u64)addr_code(c, r) };
	for (int i = 0; i < 3; i++)
		for (int k = 0; k < 8; k++)
			c->h = (c->h ^ ((v[i] >> (8 * k)) & 0xff)) * 0x100000001b3ULL;
	c->n++;
}
static struct cb_args *g_args_a, *g_args_b;   /* какие args у какой стороны: чужие args в обратном вызове — тоже след */
static bool less_fn(const void *l, const void *r, void *a)
{
	struct cb_args *c = a;
	if (c != g_args_a && c != g_args_b)
		abort();                      /* обратный вызов получил не те args — падение порции */
	trace(c, 1, l, r);
	int d = memcmp(l, r, c->keylen);
	return c->desc ? d > 0 : d < 0;
}
static void swap_fn(void *l, void *r, void *a)
{
	struct cb_args *c = a;
	if (c != g_args_a && c != g_args_b)
		abort();
	trace(c, 2, l, r);
	u8 t[64];
	memcpy(t, l, c->size);
	memcpy(l, r, c->size);
	memcpy(r, t, c->size);
}

/* где лежат данные кучи: 0 + смещение — свой массив raw; 1 + смещение — запасная область за заголовком; 2 — иначе */
static long where(const min_heap_char *h, const struct side *s)
{
	const u8 *d = (const u8 *)h->data, *raw = s->raw, *hb = (const u8 *)s->heapbuf;
	if (d >= raw && d <= raw + sizeof(s->raw))
		return d - raw;
	if (d >= hb && d <= hb + sizeof(s->heapbuf))
		return 100000 + (d - hb);
	return -1;
}
static int same(const min_heap_char *ha, const struct side *A, const min_heap_char *hb, const struct side *B)
{
	return ha->nr == hb->nr && ha->size == hb->size && where(ha, A) == where(hb, B) && memcmp(A->raw, B->raw, sizeof(A->raw)) == 0 &&
	       memcmp((const u8 *)A->heapbuf + sizeof(min_heap_char), (const u8 *)B->heapbuf + sizeof(min_heap_char),
		      sizeof(A->heapbuf) - sizeof(min_heap_char)) == 0;
}

static int c_seq(char *ex, size_t exn)
{
	static const size_t SZ[] = { 1, 2, 3, 4, 5, 8, 12, 16, 24, 32 };
	static struct side A, B;
	size_t es = SZ[rnd_below(ARRAY_SIZE(SZ))], off = rnd_below(5), cap = g_boundary ? pick_len(CAPMAX, 1) : rnd_below(CAPMAX + 1);
	int prealloc = rnd() % 4 == 0;                                  /* data == NULL → heap->preallocated */
	struct min_heap_callbacks cb = { less_fn, NULL };
	int sw = (int)rnd_below(4);
	const char *swname = "NULL";
	if (sw == 1) { cb.swp = swap_fn; swname = "свой"; }
	else if (sw == 2 && es % 4 == 0) { cb.swp = SWAP_WORDS_32; swname = "SWAP_WORDS_32"; }
	else if (sw == 3) { cb.swp = SWAP_BYTES; swname = "SWAP_BYTES"; }
	memset(&A, 0, sizeof(A));
	rand_fill(A.raw, sizeof(A.raw));
	rand_fill((u8 *)A.heapbuf + sizeof(min_heap_char), sizeof(A.heapbuf) - sizeof(min_heap_char));
	memcpy(&B, &A, sizeof(A));
	min_heap_char *ha = (min_heap_char *)A.heapbuf, *hb = (min_heap_char *)B.heapbuf;
	u8 *da = A.raw + off, *db = B.raw + off;
	orig___min_heap_init(ha, prealloc ? NULL : da, cap);
	__min_heap_init(hb, prealloc ? NULL : db, cap);
	if (!same(ha, &A, hb, &B))
		DIFF_EX("init: размер элемента %zu, ёмкость %zu, %s — разные кучи", es, cap, prealloc ? "запасной массив" : "свой массив");
	if (where(ha, &A) < 0)
		return 0;                                               /* оригинал положил данные не туда — дальше сравнивать нечего */
	u8 el[ESMAX];
	struct cb_args aa = { es, 1 + rnd_below(es < 4 ? es : 4), (int)(rnd() % 2), (const u8 *)ha->data, el, 0xcbf29ce484222325ULL, 0 };
	struct cb_args ab = aa;
	ab.base = (const u8 *)hb->data;
	g_args_a = &aa;
	g_args_b = &ab;
	u8 *dda = (u8 *)ha->data, *ddb = (u8 *)hb->data;
	int ops = 1 + (int)rnd_below(40);
	for (int i = 0; i < ops; i++) {
		rand_fill(el, es);
		if (rnd() % 3 == 0)
			el[0] = (u8)rnd_below(3);                       /* равные ключи */
		int op = (int)rnd_below(9);
		long ra = 0, rb = 0;
		switch (op) {
		case 0: ra = orig___min_heap_push(ha, el, es, &cb, &aa); rb = __min_heap_push(hb, el, es, &cb, &ab); break;
		case 1: ra = orig___min_heap_pop(ha, es, &cb, &aa); rb = __min_heap_pop(hb, es, &cb, &ab); break;
		case 2: if (ha->nr || (cap && rnd() % 4 == 0)) {         /* при пустой куче — запись data[0], если есть место */
				orig___min_heap_pop_push(ha, el, es, &cb, &aa); __min_heap_pop_push(hb, el, es, &cb, &ab); } break;
		/* __min_heap_del не проверяет idx: idx ≥ nr — выход за массив уже у оригинала; пустая куча — путь с WARN */
		case 3: { size_t idx = ha->nr ? rnd_below(ha->nr) : 0; ra = orig___min_heap_del(ha, es, idx, &cb, &aa); rb = __min_heap_del(hb, es, idx, &cb, &ab); break; }
		case 4: { void *pa = orig___min_heap_peek(ha), *pb = __min_heap_peek(hb);
			ra = pa ? (long)((u8 *)pa - dda) : -1; rb = pb ? (long)((u8 *)pb - ddb) : -1; break; }
		case 5: ra = orig___min_heap_full(ha); rb = __min_heap_full(hb); break;
		case 6: { size_t nr = rnd_below(cap + 1); rand_fill(dda, nr * es); memcpy(ddb, dda, nr * es); ha->nr = nr; hb->nr = nr;
			orig___min_heapify_all(ha, es, &cb, &aa); __min_heapify_all(hb, es, &cb, &ab); break; }
		case 7: { size_t pos = rnd_below(ha->nr + 3);            /* за концом кучи — в C пустой ход */
			if (pos > cap) pos = cap;
			orig___min_heap_sift_down(ha, pos, es, &cb, &aa); __min_heap_sift_down(hb, pos, es, &cb, &ab); break; }
		default: { size_t idx = ha->nr ? rnd_below(ha->nr) : 0;   /* при пустой куче idx = 0 — в C пустой ход */
			orig___min_heap_sift_up(ha, es, idx, &cb, &aa); __min_heap_sift_up(hb, es, idx, &cb, &ab); break; }
		}
		if (ra != rb || !same(ha, &A, hb, &B))
			DIFF_EX("операция %d (вид %d): элемент %zu байт, смещение %zu, ёмкость %zu, swp %s%s: результат %ld против %ld, nr %zu против %zu",
				i, op, es, off, cap, swname, prealloc ? ", запасной массив" : "", ra, rb, ha->nr, hb->nr);
		if (aa.n != ab.n || aa.h != ab.h)
			DIFF_EX("операция %d (вид %d): элемент %zu байт, swp %s: обратные вызовы less/swp иначе (%llu против %llu вызовов)",
				i, op, es, swname, (unsigned long long)aa.n, (unsigned long long)ab.n);
	}
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "min_heap_sequence", c_seq } };
	return diff_main(L, 1, argc, argv);
}
