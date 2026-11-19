/* LINUX-02: сравнение перевода lib/errseq.c с оригиналом. Одна проверка — случайная последовательность до 40 операций
 * set / sample / check / check_and_advance над одним errseq_t и тремя курсорами; у оригинала и у перевода — свои копии.
 * Начальное значение errseq_t — любое (в том числе у верхней границы счётчика: заворачивание u32). После каждой операции
 * сравниваются возвращаемое значение, errseq_t и курсоры. */
#include <linux/errseq.h>
#include "diff_common.h"

errseq_t orig_errseq_set(errseq_t *eseq, int err);
errseq_t orig_errseq_sample(errseq_t *eseq);
int orig_errseq_check(errseq_t *eseq, errseq_t since);
int orig_errseq_check_and_advance(errseq_t *eseq, errseq_t *since);

static int pick_err(void)
{
	if (g_boundary) {
		static const int B[] = { 0, -1, -2, -4095, -4096, 1, 4095, INT_MIN, INT_MAX, -EIO, -ENOSPC };
		return B[rnd_below(ARRAY_SIZE(B))];
	}
	switch (rnd() % 6) {
	case 0: return -(int)(1 + rnd_below(4095));
	case 1: return -EIO;
	case 2: return -ENOSPC;
	case 3: return 0;
	case 4: return (int)rnd();
	default: return -(int)(1 + rnd_below(5000));
	}
}

static u32 pick_state(void)
{
	switch (rnd() % 4) {
	case 0: return 0;
	case 1: return (u32)rnd();
	case 2: return 0xffffffffu - (u32)rnd_below(1u << 14);   /* у верхней границы счётчика */
	default: return (u32)rnd_below(1u << 14);
	}
}

static int c_seq(char *ex, size_t exn)
{
	errseq_t a = pick_state(), b = a;
	errseq_t ca[3], cb[3];
	for (int k = 0; k < 3; k++)
		ca[k] = cb[k] = (rnd() % 2) ? pick_state() : 0;
	int ops = 1 + (int)rnd_below(40);
	for (int i = 0; i < ops; i++) {
		int op = (int)rnd_below(4), k = (int)rnd_below(3);
		long ra = 0, rb = 0;
		switch (op) {
		case 0: { int e = pick_err(); ra = orig_errseq_set(&a, e); rb = errseq_set(&b, e); break; }
		case 1: ra = orig_errseq_sample(&a); rb = errseq_sample(&b); ca[k] = (errseq_t)ra; cb[k] = (errseq_t)rb; break;
		case 2: ra = orig_errseq_check(&a, ca[k]); rb = errseq_check(&b, cb[k]); break;
		default: ra = orig_errseq_check_and_advance(&a, &ca[k]); rb = errseq_check_and_advance(&b, &cb[k]); break;
		}
		if (ra != rb || a != b || memcmp(ca, cb, sizeof(ca)))
			DIFF_EX("операция %d (вид %d, курсор %d): результат %ld против %ld, errseq %08x против %08x", i, op, k, ra, rb, a, b);
	}
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "errseq_sequence", c_seq } };
	return diff_main(L, 1, argc, argv);
}
