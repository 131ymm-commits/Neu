LINUX-01, переводчик. Последнее сообщение автора исследования (дословно): «делай пилот с модулем Линукса.»

Задача: переведи файл ядра Linux `lib/math/rational.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64; `unsigned long` = `core::ffi::c_ulong` (64 бита), `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `u32`/`u64` — `u32`/`u64`; `CONFIG_CPU_NO_EFFICIENT_FFS` не задан. Код под `#if`, который в этой конфигурации не собирается, не переводи и не экспортируй.
2. Каждую нестатическую функцию (с EXPORT_SYMBOL) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковых чисел, пиши `wrapping_*` явно; приведения типов и сдвиги повторяй так, как их выполняет C на x86_64 с GCC.
4. Поведение должно совпадать с оригиналом на всех входах, включая крайние (0, наибольшие значения, пустые строки): те же возвращаемые значения, те же записи по указателям, те же положения указателей на выходе, те же изменения в строках.
5. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры.
6. Макросы и встроенные функции ядра из этого файла переведи сами по их смыслу: `min(a, b)` — меньшее; `ULONG_MAX`.
7. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): нет.
8. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Файл `lib/math/rational.c`:
```c
// SPDX-License-Identifier: GPL-2.0
/*
 * rational fractions
 *
 * Copyright (C) 2009 emlix GmbH, Oskar Schirmer <oskar@scara.com>
 * Copyright (C) 2019 Trent Piepho <tpiepho@gmail.com>
 *
 * helper functions when coping with rational numbers
 */

#include <linux/rational.h>
#include <linux/compiler.h>
#include <linux/export.h>
#include <linux/minmax.h>
#include <linux/limits.h>
#include <linux/module.h>

/*
 * calculate best rational approximation for a given fraction
 * taking into account restricted register size, e.g. to find
 * appropriate values for a pll with 5 bit denominator and
 * 8 bit numerator register fields, trying to set up with a
 * frequency ratio of 3.1415, one would say:
 *
 * rational_best_approximation(31415, 10000,
 *		(1 << 8) - 1, (1 << 5) - 1, &n, &d);
 *
 * you may look at given_numerator as a fixed point number,
 * with the fractional part size described in given_denominator.
 *
 * for theoretical background, see:
 * https://en.wikipedia.org/wiki/Continued_fraction
 */

void rational_best_approximation(
	unsigned long given_numerator, unsigned long given_denominator,
	unsigned long max_numerator, unsigned long max_denominator,
	unsigned long *best_numerator, unsigned long *best_denominator)
{
	/* n/d is the starting rational, which is continually
	 * decreased each iteration using the Euclidean algorithm.
	 *
	 * dp is the value of d from the prior iteration.
	 *
	 * n2/d2, n1/d1, and n0/d0 are our successively more accurate
	 * approximations of the rational.  They are, respectively,
	 * the current, previous, and two prior iterations of it.
	 *
	 * a is current term of the continued fraction.
	 */
	unsigned long n, d, n0, d0, n1, d1, n2, d2;
	n = given_numerator;
	d = given_denominator;
	n0 = d1 = 0;
	n1 = d0 = 1;

	for (;;) {
		unsigned long dp, a;

		if (d == 0)
			break;
		/* Find next term in continued fraction, 'a', via
		 * Euclidean algorithm.
		 */
		dp = d;
		a = n / d;
		d = n % d;
		n = dp;

		/* Calculate the current rational approximation (aka
		 * convergent), n2/d2, using the term just found and
		 * the two prior approximations.
		 */
		n2 = n0 + a * n1;
		d2 = d0 + a * d1;

		/* If the current convergent exceeds the maxes, then
		 * return either the previous convergent or the
		 * largest semi-convergent, the final term of which is
		 * found below as 't'.
		 */
		if ((n2 > max_numerator) || (d2 > max_denominator)) {
			unsigned long t = ULONG_MAX;

			if (d1)
				t = (max_denominator - d0) / d1;
			if (n1)
				t = min(t, (max_numerator - n0) / n1);

			/* This tests if the semi-convergent is closer than the previous
			 * convergent.  If d1 is zero there is no previous convergent as this
			 * is the 1st iteration, so always choose the semi-convergent.
			 */
			if (!d1 || 2u * t > a || (2u * t == a && d0 * dp > d1 * d)) {
				n1 = n0 + t * n1;
				d1 = d0 + t * d1;
			}
			break;
		}
		n0 = n1;
		n1 = n2;
		d0 = d1;
		d1 = d2;
	}
	*best_numerator = n1;
	*best_denominator = d1;
}

EXPORT_SYMBOL(rational_best_approximation);

MODULE_DESCRIPTION("Rational fraction support library");
MODULE_LICENSE("GPL v2");
```
