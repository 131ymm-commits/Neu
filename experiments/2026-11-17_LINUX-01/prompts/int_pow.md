LINUX-01, переводчик. Последнее сообщение автора исследования (дословно): «делай пилот с модулем Линукса.»

Задача: переведи файл ядра Linux `lib/math/int_pow.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64; `unsigned long` = `core::ffi::c_ulong` (64 бита), `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `u32`/`u64` — `u32`/`u64`; `CONFIG_CPU_NO_EFFICIENT_FFS` не задан. Код под `#if`, который в этой конфигурации не собирается, не переводи и не экспортируй.
2. Каждую нестатическую функцию (с EXPORT_SYMBOL) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковых чисел, пиши `wrapping_*` явно; приведения типов и сдвиги повторяй так, как их выполняет C на x86_64 с GCC.
4. Поведение должно совпадать с оригиналом на всех входах, включая крайние (0, наибольшие значения, пустые строки): те же возвращаемые значения, те же записи по указателям, те же положения указателей на выходе, те же изменения в строках.
5. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры.
6. Макросы и встроенные функции ядра из этого файла переведи сами по их смыслу: нет особых
7. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): нет.
8. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Файл `lib/math/int_pow.c`:
```c
// SPDX-License-Identifier: GPL-2.0
/*
 * An integer based power function
 *
 * Derived from drivers/video/backlight/pwm_bl.c
 */

#include <linux/export.h>
#include <linux/math.h>
#include <linux/types.h>

/**
 * int_pow - computes the exponentiation of the given base and exponent
 * @base: base which will be raised to the given power
 * @exp: power to be raised to
 *
 * Computes: pow(base, exp), i.e. @base raised to the @exp power
 */
u64 int_pow(u64 base, unsigned int exp)
{
	u64 result = 1;

	while (exp) {
		if (exp & 1)
			result *= base;
		exp >>= 1;
		base *= base;
	}

	return result;
}
EXPORT_SYMBOL_GPL(int_pow);
```
