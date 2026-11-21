LINUX-01, переводчик. Последнее сообщение автора исследования (дословно): «делай пилот с модулем Линукса.»

Задача: переведи файл ядра Linux `lib/math/int_sqrt.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64; `unsigned long` = `core::ffi::c_ulong` (64 бита), `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `u32`/`u64` — `u32`/`u64`; `CONFIG_CPU_NO_EFFICIENT_FFS` не задан. Код под `#if`, который в этой конфигурации не собирается, не переводи и не экспортируй.
2. Каждую нестатическую функцию (с EXPORT_SYMBOL) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковых чисел, пиши `wrapping_*` явно; приведения типов и сдвиги повторяй так, как их выполняет C на x86_64 с GCC.
4. Поведение должно совпадать с оригиналом на всех входах, включая крайние (0, наибольшие значения, пустые строки): те же возвращаемые значения, те же записи по указателям, те же положения указателей на выходе, те же изменения в строках.
5. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры.
6. Макросы и встроенные функции ядра из этого файла переведи сами по их смыслу: `__fls(x)` — номер старшего установленного бита, считая с 0 (x ≠ 0); `ULONG_MAX`.
7. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): нет.
8. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Файл `lib/math/int_sqrt.c`:
```c
// SPDX-License-Identifier: GPL-2.0
/*
 * Copyright (C) 2013 Davidlohr Bueso <davidlohr.bueso@hp.com>
 *
 *  Based on the shift-and-subtract algorithm for computing integer
 *  square root from Guy L. Steele.
 */

#include <linux/export.h>
#include <linux/bitops.h>
#include <linux/limits.h>
#include <linux/math.h>

/**
 * int_sqrt - computes the integer square root
 * @x: integer of which to calculate the sqrt
 *
 * Computes: floor(sqrt(x))
 */
unsigned long int_sqrt(unsigned long x)
{
	unsigned long b, m, y = 0;

	if (x <= 1)
		return x;

	m = 1UL << (__fls(x) & ~1UL);
	while (m != 0) {
		b = y + m;
		y >>= 1;

		if (x >= b) {
			x -= b;
			y += m;
		}
		m >>= 2;
	}

	return y;
}
EXPORT_SYMBOL(int_sqrt);

#if BITS_PER_LONG < 64
/**
 * int_sqrt64 - strongly typed int_sqrt function when minimum 64 bit input
 * is expected.
 * @x: 64bit integer of which to calculate the sqrt
 */
u32 int_sqrt64(u64 x)
{
	u64 b, m, y = 0;

	if (x <= ULONG_MAX)
		return int_sqrt((unsigned long) x);

	m = 1ULL << ((fls64(x) - 1) & ~1ULL);
	while (m != 0) {
		b = y + m;
		y >>= 1;

		if (x >= b) {
			x -= b;
			y += m;
		}
		m >>= 2;
	}

	return y;
}
EXPORT_SYMBOL(int_sqrt64);
#endif
```
