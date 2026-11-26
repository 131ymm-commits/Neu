LINUX-01, переводчик. Последнее сообщение автора исследования (дословно): «делай пилот с модулем Линукса.»

Задача: переведи файл ядра Linux `lib/math/gcd.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64; `unsigned long` = `core::ffi::c_ulong` (64 бита), `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `u32`/`u64` — `u32`/`u64`; `CONFIG_CPU_NO_EFFICIENT_FFS` не задан. Код под `#if`, который в этой конфигурации не собирается, не переводи и не экспортируй.
2. Каждую нестатическую функцию (с EXPORT_SYMBOL) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковых чисел, пиши `wrapping_*` явно; приведения типов и сдвиги повторяй так, как их выполняет C на x86_64 с GCC.
4. Поведение должно совпадать с оригиналом на всех входах, включая крайние (0, наибольшие значения, пустые строки): те же возвращаемые значения, те же записи по указателям, те же положения указателей на выходе, те же изменения в строках.
5. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры.
6. Макросы и встроенные функции ядра из этого файла переведи сами по их смыслу: `__ffs(x)` — номер младшего установленного бита, считая с 0 (x ≠ 0); `swap(a, b)` — обмен значениями; `DEFINE_STATIC_KEY_TRUE(efficient_ffs_key)` и `static_branch_likely(&efficient_ffs_key)` — статический ключ ядра, в этой конфигурации включён (условие истинно); переменную ключа экспортировать не нужно.
7. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): нет.
8. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Файл `lib/math/gcd.c`:
```c
// SPDX-License-Identifier: GPL-2.0-only
#include <linux/kernel.h>
#include <linux/gcd.h>
#include <linux/export.h>

/*
 * This implements the binary GCD algorithm. (Often attributed to Stein,
 * but as Knuth has noted, appears in a first-century Chinese math text.)
 *
 * This is faster than the division-based algorithm even on x86, which
 * has decent hardware division.
 */

DEFINE_STATIC_KEY_TRUE(efficient_ffs_key);

#if !defined(CONFIG_CPU_NO_EFFICIENT_FFS)

/* If __ffs is available, the even/odd algorithm benchmarks slower. */

static unsigned long binary_gcd(unsigned long a, unsigned long b)
{
	unsigned long r = a | b;

	b >>= __ffs(b);
	if (b == 1)
		return r & -r;

	for (;;) {
		a >>= __ffs(a);
		if (a == 1)
			return r & -r;
		if (a == b)
			return a << __ffs(r);

		if (a < b)
			swap(a, b);
		a -= b;
	}
}

#endif

/* If normalization is done by loops, the even/odd algorithm is a win. */

/**
 * gcd - calculate and return the greatest common divisor of 2 unsigned longs
 * @a: first value
 * @b: second value
 */
unsigned long gcd(unsigned long a, unsigned long b)
{
	unsigned long r = a | b;

	if (!a || !b)
		return r;

#if !defined(CONFIG_CPU_NO_EFFICIENT_FFS)
	if (static_branch_likely(&efficient_ffs_key))
		return binary_gcd(a, b);
#endif

	/* Isolate lsbit of r */
	r &= -r;

	while (!(b & r))
		b >>= 1;
	if (b == r)
		return r;

	for (;;) {
		while (!(a & r))
			a >>= 1;
		if (a == r)
			return r;
		if (a == b)
			return a;

		if (a < b)
			swap(a, b);
		a -= b;
		a >>= 1;
		if (a & r)
			a += b;
		a >>= 1;
	}
}

EXPORT_SYMBOL_GPL(gcd);
```
