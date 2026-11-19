/* LINUX-02: сравнение перевода lib/random32.c с оригиналом. Состояние rnd_state — любое (в том числе s1…s4 меньше
 * минимумов __seed: генератор тогда вырожден, но поведение должно совпадать). Последовательность до 20 вызовов
 * prandom_u32_state / prandom_bytes_state (длины 0…67, буфер с любым смещением) / prandom_warmup / prandom_seed_full_state
 * (get_random_bytes — один и тот же поток для обеих сторон). После каждого вызова сравниваются результат, буфер и состояние. */
#include <linux/prandom.h>
#include "diff_common.h"

u32 orig_prandom_u32_state(struct rnd_state *state);
void orig_prandom_bytes_state(struct rnd_state *state, void *buf, size_t nbytes);
void orig_prandom_seed_full_state(struct rnd_state *pcpu_state);
void orig_prandom_warmup(struct rnd_state *state);
void prandom_warmup(struct rnd_state *state);

static u32 pick_s(void) { return (rnd() % 3) ? (u32)rnd() : (u32)rnd_below(256); }

static int c_seq(char *ex, size_t exn)
{
	struct rnd_state a = { pick_s(), pick_s(), pick_s(), pick_s() }, b = a;
	int ops = 1 + (int)rnd_below(20);
	for (int i = 0; i < ops; i++) {
		int op = (int)rnd_below(4);
		u8 ba[80], bb[80];
		memset(ba, 0xAB, sizeof(ba));
		memset(bb, 0xAB, sizeof(bb));
		u32 ra = 0, rb = 0;
		size_t off = rnd_below(8), len = pick_len(67, 4);
		struct klog_snap la, lb;
		switch (op) {
		case 0: ra = orig_prandom_u32_state(&a); rb = prandom_u32_state(&b); break;
		case 1: orig_prandom_bytes_state(&a, ba + off, len); prandom_bytes_state(&b, bb + off, len); break;
		case 2: orig_prandom_warmup(&a); prandom_warmup(&b); break;
		default: {
			u64 sd = rnd();
			harness_random_reset(sd); kalloc_log_reset(); orig_prandom_seed_full_state(&a); klog_take(&la);
			harness_random_reset(sd); kalloc_log_reset(); prandom_seed_full_state(&b); klog_take(&lb);
			if (!klog_equal(&la, &lb))
				DIFF_EX("операция %d: prandom_seed_full_state вызывает get_random_bytes иначе", i);
		}
		}
		if (ra != rb || memcmp(&a, &b, sizeof(a)) || memcmp(ba, bb, sizeof(ba)))
			DIFF_EX("операция %d (вид %d, длина %zu, смещение %zu): %08x против %08x; s1 %08x против %08x", i, op, len, off, ra, rb, a.s1, b.s1);
	}
	return 0;
}

int main(int argc, char **argv)
{
	static const struct fn L[] = { { "prandom_sequence", c_seq } };
	return diff_main(L, 1, argc, argv);
}
