/* LINUX-02: сравнение перевода lib/min_heap.c (+ встроенные функции include/linux/min_heap.h) с оригиналом. Куча с внешним
 * массивом: размер элемента 1…32 байт (в том числе 3, 5, 12 — не кратные словам), смещение массива 0…4 байта, ёмкость
 * 0…40; less — порядок по первым байтам элемента (с равными ключами: порядок сравнений виден в результате), по возрастанию
 * или убыванию; swp — NULL (выбор встроенного обмена по размеру) или свой обмен. Последовательность до 40 операций:
 * push / pop / pop_push / del / peek / full / heapify_all (после случайного заполнения) / sift_down / sift_up / del — с позицией
 * внутри кучи: за её пределами оригинал выходит за массив (поведение не определено). После каждой операции сравниваются результат,
 * nr, size, смещение data и весь массив. */
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

struct cb_args { size_t size; size_t keylen; int desc; };
static bool less_fn(const void *l, const void *r, void *a)
{
	const struct cb_args *c = a;
	int d = memcmp(l, r, c->keylen);
	return c->desc ? d > 0 : d < 0;
}
static void swap_fn(void *l, void *r, void *a)
{
	const struct cb_args *c = a;
	u8 t[64];
	memcpy(t, l, c->size);
	memcpy(l, r, c->size);
	memcpy(r, t, c->size);
}

#define CAPMAX 40
#define ESMAX 32
struct side { u8 raw[CAPMAX * ESMAX + 16]; u8 heapbuf[sizeof(min_heap_char) + 16]; };

static int same(const min_heap_char *ha, const u8 *ba, const min_heap_char *hb, const u8 *bb, size_t bytes)
{
	return ha->nr == hb->nr && ha->size == hb->size && (ha->data - (char *)ba) == (hb->data - (char *)bb) && memcmp(ba, bb, bytes) == 0;
}

static int c_seq(char *ex, size_t exn)
{
	static const size_t SZ[] = { 1, 2, 3, 4, 5, 8, 12, 16, 24, 32 };
	static struct side A, B;
	size_t es = SZ[rnd_below(ARRAY_SIZE(SZ))], off = rnd_below(5), cap = g_boundary ? pick_len(CAPMAX, 1) : rnd_below(CAPMAX + 1);
	struct cb_args args = { es, 1 + rnd_below(es < 4 ? es : 4), (int)(rnd() % 2) };
	struct min_heap_callbacks cb = { less_fn, (rnd() % 2) ? swap_fn : NULL };
	memset(&A, 0, sizeof(A));
	rand_fill(A.raw, sizeof(A.raw));
	memcpy(&B, &A, sizeof(A));
	min_heap_char *ha = (min_heap_char *)A.heapbuf, *hb = (min_heap_char *)B.heapbuf;
	u8 *da = A.raw + off, *db = B.raw + off;
	size_t bytes = sizeof(A.raw) - off;
	orig___min_heap_init(ha, da, cap);
	__min_heap_init(hb, db, cap);
	if (!same(ha, A.raw, hb, B.raw, sizeof(A.raw)))
		DIFF_EX("init: размер элемента %zu, ёмкость %zu — разные кучи", es, cap);
	int ops = 1 + (int)rnd_below(40);
	for (int i = 0; i < ops; i++) {
		u8 el[ESMAX];
		rand_fill(el, es);
		if (rnd() % 3 == 0)
			el[0] = (u8)rnd_below(3);                       /* равные ключи */
		int op = (int)rnd_below(9);
		long ra = 0, rb = 0;
		switch (op) {
		case 0: ra = orig___min_heap_push(ha, el, es, &cb, &args); rb = __min_heap_push(hb, el, es, &cb, &args); break;
		case 1: ra = orig___min_heap_pop(ha, es, &cb, &args); rb = __min_heap_pop(hb, es, &cb, &args); break;
		case 2: if (ha->nr) { orig___min_heap_pop_push(ha, el, es, &cb, &args); __min_heap_pop_push(hb, el, es, &cb, &args); } break;
		/* __min_heap_del не проверяет idx: idx ≥ nr — выход за массив уже у оригинала; пустая куча — путь с WARN */
		case 3: { size_t idx = ha->nr ? rnd_below(ha->nr) : 0; ra = orig___min_heap_del(ha, es, idx, &cb, &args); rb = __min_heap_del(hb, es, idx, &cb, &args); break; }
		case 4: { void *pa = orig___min_heap_peek(ha), *pb = __min_heap_peek(hb);
			ra = pa ? (long)((u8 *)pa - A.raw) : -1; rb = pb ? (long)((u8 *)pb - B.raw) : -1; break; }
		case 5: ra = orig___min_heap_full(ha); rb = __min_heap_full(hb); break;
		case 6: { size_t nr = rnd_below(cap + 1); rand_fill(da, nr * es); memcpy(db, da, nr * es); ha->nr = nr; hb->nr = nr;
			orig___min_heapify_all(ha, es, &cb, &args); __min_heapify_all(hb, es, &cb, &args); break; }
		case 7: if (ha->nr) { size_t pos = rnd_below(ha->nr); orig___min_heap_sift_down(ha, pos, es, &cb, &args); __min_heap_sift_down(hb, pos, es, &cb, &args); } break;
		default: if (ha->nr) { size_t idx = rnd_below(ha->nr); orig___min_heap_sift_up(ha, es, idx, &cb, &args); __min_heap_sift_up(hb, es, idx, &cb, &args); } break;
		}
		if (ra != rb || !same(ha, A.raw, hb, B.raw, sizeof(A.raw)))
			DIFF_EX("операция %d (вид %d): элемент %zu байт, смещение %zu, ёмкость %zu, swp %s: результат %ld против %ld, nr %zu против %zu",
				i, op, es, off, cap, cb.swp ? "свой" : "NULL", ra, rb, ha->nr, hb->nr);
		(void)bytes;
	}
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "min_heap_sequence", c_seq } };
	return diff_main(L, 1, argc, argv);
}
