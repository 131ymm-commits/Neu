/* LINUX-02: сравнение перевода lib/842/842_decompress.c с оригиналом. Вход распаковщика:
 *   - данные (случайные, с повторами, с нулями, ступенькой; 0…4096 байт), сжатые оригинальным sw842_compress (lib/842/842_compress.c;
 *     он не переводится и одинаков для обеих сторон);
 *   - затем без порчи / с перевёрнутыми битами / с обрезкой / с дописанным хвостом / совсем случайные байты;
 *   - ёмкость выхода: ровно нужная, меньше, больше, 0.
 * Сравниваются код возврата, *olen, весь выходной буфер с запасом (запись за пределы ёмкости видна) и журнал вызовов crc32_be. */
#include <linux/sw842.h>
#include "diff_common.h"

int orig_sw842_decompress(const u8 *src, unsigned int srclen, u8 *dst, unsigned int *destlen);

#define MAXD 4096
#define PAD 64
static u8 wmem[SW842_MEM_COMPRESS];

static int c_decomp(char *ex, size_t exn)
{
	static u8 data[MAXD], comp[2 * MAXD + 64], oa[MAXD + 2 * PAD], ob[MAXD + 2 * PAD];
	size_t dlen = g_boundary ? pick_len(MAXD, 8) : (rnd() % 3 ? rnd_below(600) : rnd_below(MAXD + 1));
	rand_fill(data, dlen);
	unsigned int clen = sizeof(comp);
	int cr = sw842_compress(data, (unsigned int)dlen, comp, &clen, wmem);
	if (cr != 0)
		clen = 0;
	int kind = (int)rnd_below(6);
	switch (kind) {
	case 1: if (clen) for (int k = 0; k < 1 + (int)rnd_below(3); k++) comp[rnd_below(clen)] ^= (u8)(1u << rnd_below(8)); break;
	case 2: if (clen) clen = (unsigned int)rnd_below(clen); break;
	case 3: { unsigned int add = (unsigned int)rnd_below(17); for (unsigned int k = 0; k < add && clen < sizeof(comp); k++) comp[clen++] = (u8)rnd(); break; }
	case 4: clen = (unsigned int)rnd_below(200); rand_fill(comp, clen); break;
	default: break;
	}
	unsigned int cap;
	switch (rnd() % 4) {
	case 0: cap = (unsigned int)dlen; break;
	case 1: cap = dlen ? (unsigned int)rnd_below(dlen) : 0; break;
	case 2: cap = (unsigned int)(dlen + rnd_below(64)); break;
	default: cap = (unsigned int)rnd_below(MAXD + 1); break;
	}
	if (cap > MAXD)
		cap = MAXD;
	memset(oa, 0xEE, sizeof(oa));
	memset(ob, 0xEE, sizeof(ob));
	unsigned int la = cap, lb = cap;
	struct klog_snap ka, kb;
	kalloc_log_reset();
	int ra = orig_sw842_decompress(comp, clen, oa + PAD, &la);
	klog_take(&ka);
	kalloc_log_reset();
	int rb = sw842_decompress(comp, clen, ob + PAD, &lb);
	klog_take(&kb);
	if (ra != rb || la != lb)
		DIFF_EX("данные %zu, порча %d, сжато %u, ёмкость %u: возврат %d против %d, olen %u против %u", dlen, kind, clen, cap, ra, rb, la, lb);
	if (memcmp(oa, ob, sizeof(oa)))
		DIFF_EX("данные %zu, порча %d, сжато %u, ёмкость %u: выходной буфер разный (возврат %d)", dlen, kind, clen, cap, ra);
	if (!klog_equal(&ka, &kb))
		DIFF_EX("данные %zu, порча %d: crc32_be вызывается иначе (%d против %d вызовов)", dlen, kind, ka.n, kb.n);
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "sw842_decompress", c_decomp } };
	return diff_main(L, 1, argc, argv);
}
