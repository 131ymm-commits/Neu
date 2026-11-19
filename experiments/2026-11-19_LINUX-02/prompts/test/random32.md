LINUX-02, переводчик.

Задача: переведи файл ядра Linux `lib/random32.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала: те же экспортируемые функции и то же поведение.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64, little-endian; `unsigned long` = `core::ffi::c_ulong` (64 бита), `long` = `c_long`, `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `size_t` = `usize`, `char` = `c_char`, `bool` = `bool`, `u8`/`u16`/`u32`/`u64` и `s8`…`s64` — соответствующие целые Rust. Один возможный процессор: `for_each_possible_cpu(i)` перебирает только i = 0, `per_cpu_ptr(p, 0)` — сам p (`__percpu` — обычный указатель). Тесты KUnit собраны (`CONFIG_KUNIT`), поэтому `VISIBLE_IF_KUNIT`-функция `prandom_warmup` нестатическая и экспортируется (`EXPORT_SYMBOL_IF_KUNIT` — как `EXPORT_SYMBOL`).
2. Каждую нестатическую функцию (с `EXPORT_SYMBOL`, `EXPORT_SYMBOL_GPL` или `EXPORT_SYMBOL_IF_KUNIT`) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Структуры, которые передаются в эти функции или из них, объяви `#[repr(C)]` с тем же порядком и типами полей, что в заголовках ниже: вызывающий код на C передаёт свои структуры.
4. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковой арифметики, используй `wrapping_*`.
5. Поведение должно совпадать с оригиналом на всех входах, включая крайние: те же возвращаемые значения, те же записи в выходные буферы и структуры, те же вызовы внешних функций.
6. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры и вызовы внешних функций.
7. Макросы и встроенные функции ядра переведи сами по их смыслу: `put_unaligned(v, p)` — запись по невыровненному адресу; `BITS_PER_BYTE` = 8; `likely(x)` и `unlikely(x)` — то же, что x.; `IS_ENABLED(CONFIG_…)` — 1, если параметр задан, иначе 0 (здесь задан `CONFIG_KUNIT`); `__u32` — u32.
8. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): `void get_random_bytes(void *buf, size_t len)`.
9. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Заголовок `include/linux/prandom.h` (типы, структуры, константы, встроенные функции):
```c
/* SPDX-License-Identifier: GPL-2.0 */
/*
 * include/linux/prandom.h
 *
 * Include file for the fast pseudo-random 32-bit
 * generation.
 */
#ifndef _LINUX_PRANDOM_H
#define _LINUX_PRANDOM_H

#include <linux/types.h>
#include <linux/once.h>
#include <linux/percpu.h>
#include <linux/random.h>

struct rnd_state {
	__u32 s1, s2, s3, s4;
};

u32 prandom_u32_state(struct rnd_state *state);
void prandom_bytes_state(struct rnd_state *state, void *buf, size_t nbytes);
void prandom_seed_full_state(struct rnd_state __percpu *pcpu_state);

#define prandom_init_once(pcpu_state)			\
	DO_ONCE(prandom_seed_full_state, (pcpu_state))

/*
 * Handle minimum values for seeds
 */
static inline u32 __seed(u32 x, u32 m)
{
	return (x < m) ? x + m : x;
}

/**
 * prandom_seed_state - set seed for prandom_u32_state().
 * @state: pointer to state structure to receive the seed.
 * @seed: arbitrary 64-bit value to use as a seed.
 */
static inline void prandom_seed_state(struct rnd_state *state, u64 seed)
{
	u32 i = ((seed >> 32) ^ (seed << 10) ^ seed) & 0xffffffffUL;

	state->s1 = __seed(i,   2U);
	state->s2 = __seed(i,   8U);
	state->s3 = __seed(i,  16U);
	state->s4 = __seed(i, 128U);
}

#endif
```

Файл `lib/random32.c`:
```c
// SPDX-License-Identifier: GPL-2.0
/*
 * This is a maximally equidistributed combined Tausworthe generator
 * based on code from GNU Scientific Library 1.5 (30 Jun 2004)
 *
 * lfsr113 version:
 *
 * x_n = (s1_n ^ s2_n ^ s3_n ^ s4_n)
 *
 * s1_{n+1} = (((s1_n & 4294967294) << 18) ^ (((s1_n <<  6) ^ s1_n) >> 13))
 * s2_{n+1} = (((s2_n & 4294967288) <<  2) ^ (((s2_n <<  2) ^ s2_n) >> 27))
 * s3_{n+1} = (((s3_n & 4294967280) <<  7) ^ (((s3_n << 13) ^ s3_n) >> 21))
 * s4_{n+1} = (((s4_n & 4294967168) << 13) ^ (((s4_n <<  3) ^ s4_n) >> 12))
 *
 * The period of this generator is about 2^113 (see erratum paper).
 *
 * From: P. L'Ecuyer, "Maximally Equidistributed Combined Tausworthe
 * Generators", Mathematics of Computation, 65, 213 (1996), 203--213:
 * http://www.iro.umontreal.ca/~lecuyer/myftp/papers/tausme.ps
 * ftp://ftp.iro.umontreal.ca/pub/simulation/lecuyer/papers/tausme.ps
 *
 * There is an erratum in the paper "Tables of Maximally Equidistributed
 * Combined LFSR Generators", Mathematics of Computation, 68, 225 (1999),
 * 261--269: http://www.iro.umontreal.ca/~lecuyer/myftp/papers/tausme2.ps
 *
 *      ... the k_j most significant bits of z_j must be non-zero,
 *      for each j. (Note: this restriction also applies to the
 *      computer code given in [4], but was mistakenly not mentioned
 *      in that paper.)
 *
 * This affects the seeding procedure by imposing the requirement
 * s1 > 1, s2 > 7, s3 > 15, s4 > 127.
 */

#include <linux/types.h>
#include <linux/percpu.h>
#include <linux/export.h>
#include <linux/jiffies.h>
#include <linux/prandom.h>
#include <linux/sched.h>
#include <linux/bitops.h>
#include <linux/slab.h>
#include <linux/unaligned.h>
#include <kunit/visibility.h>

/**
 *	prandom_u32_state - seeded pseudo-random number generator.
 *	@state: pointer to state structure holding seeded state.
 *
 *	This is used for pseudo-randomness with no outside seeding.
 *	For more random results, use get_random_u32().
 */
u32 prandom_u32_state(struct rnd_state *state)
{
#define TAUSWORTHE(s, a, b, c, d) ((s & c) << d) ^ (((s << a) ^ s) >> b)
	state->s1 = TAUSWORTHE(state->s1,  6U, 13U, 4294967294U, 18U);
	state->s2 = TAUSWORTHE(state->s2,  2U, 27U, 4294967288U,  2U);
	state->s3 = TAUSWORTHE(state->s3, 13U, 21U, 4294967280U,  7U);
	state->s4 = TAUSWORTHE(state->s4,  3U, 12U, 4294967168U, 13U);

	return (state->s1 ^ state->s2 ^ state->s3 ^ state->s4);
}
EXPORT_SYMBOL(prandom_u32_state);

/**
 *	prandom_bytes_state - get the requested number of pseudo-random bytes
 *
 *	@state: pointer to state structure holding seeded state.
 *	@buf: where to copy the pseudo-random bytes to
 *	@bytes: the requested number of bytes
 *
 *	This is used for pseudo-randomness with no outside seeding.
 *	For more random results, use get_random_bytes().
 */
void prandom_bytes_state(struct rnd_state *state, void *buf, size_t bytes)
{
	u8 *ptr = buf;

	while (bytes >= sizeof(u32)) {
		put_unaligned(prandom_u32_state(state), (u32 *) ptr);
		ptr += sizeof(u32);
		bytes -= sizeof(u32);
	}

	if (bytes > 0) {
		u32 rem = prandom_u32_state(state);
		do {
			*ptr++ = (u8) rem;
			bytes--;
			rem >>= BITS_PER_BYTE;
		} while (bytes > 0);
	}
}
EXPORT_SYMBOL(prandom_bytes_state);

/*
 * Only declared here so that it has a prototype when made
 * non-static for KUnit testing (avoids -Wmissing-prototypes).
 */
#if IS_ENABLED(CONFIG_KUNIT)
void prandom_warmup(struct rnd_state *state);
#endif
VISIBLE_IF_KUNIT void prandom_warmup(struct rnd_state *state)
{
	/* Calling RNG ten times to satisfy recurrence condition */
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
	prandom_u32_state(state);
}
EXPORT_SYMBOL_IF_KUNIT(prandom_warmup);

void prandom_seed_full_state(struct rnd_state __percpu *pcpu_state)
{
	int i;

	for_each_possible_cpu(i) {
		struct rnd_state *state = per_cpu_ptr(pcpu_state, i);
		u32 seeds[4];

		get_random_bytes(&seeds, sizeof(seeds));
		state->s1 = __seed(seeds[0],   2U);
		state->s2 = __seed(seeds[1],   8U);
		state->s3 = __seed(seeds[2],  16U);
		state->s4 = __seed(seeds[3], 128U);

		prandom_warmup(state);
	}
}
EXPORT_SYMBOL(prandom_seed_full_state);
```
