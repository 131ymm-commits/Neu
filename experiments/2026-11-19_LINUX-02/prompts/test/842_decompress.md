LINUX-02, переводчик.

Задача: переведи файл ядра Linux `lib/842/842_decompress.c` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала: те же экспортируемые функции и то же поведение.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64, little-endian; `unsigned long` = `core::ffi::c_ulong` (64 бита), `long` = `c_long`, `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `size_t` = `usize`, `char` = `u8` (ядро собирается с `-funsigned-char`: `char` беззнаковый; `core::ffi::c_char` на x86_64 знаковый и не подходит), `bool` = `bool`, `u8`/`u16`/`u32`/`u64` и `s8`…`s64` — соответствующие целые Rust. Параметр модуля `template_counts` выключен (false): счётчики отладки из `842_debugfs.h` (`template_count`, `template_repeat_count` и другие) наружу не видны, в переводе их можно опустить. `sw842_debugfs_create`, `sw842_debugfs_remove`, `module_init`, `module_exit` не нужны.
2. Каждую нестатическую функцию (с `EXPORT_SYMBOL`, `EXPORT_SYMBOL_GPL` или `EXPORT_SYMBOL_IF_KUNIT`) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Структуры, которые передаются в эти функции или из них, объяви `#[repr(C)]` с тем же порядком и типами полей, что в заголовках ниже: вызывающий код на C передаёт свои структуры.
4. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание арифметики, используй `wrapping_*` — и для беззнаковой, и для знаковой: ядро собирается с `-fno-strict-overflow`, и знаковое переполнение там заворачивается (как `-fwrapv`), например `-x` при `x == INT_MIN` даёт `INT_MIN`.
5. Поведение должно совпадать с оригиналом на всех входах, включая крайние: те же возвращаемые значения, те же записи в выходные буферы и структуры, те же вызовы внешних функций и переданных функций обратного вызова — в том же порядке и с теми же аргументами (указатели — на те же места в памяти, а не на временные копии).
6. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры и вызовы внешних функций.
7. Макросы и встроенные функции ядра переведи сами по их смыслу: `be16_to_cpu`, `be32_to_cpu`, `be64_to_cpu` — из big-endian в порядок машины (little-endian); `cpu_to_be16`, `cpu_to_be32`, `cpu_to_be64` — обратно; `get_unaligned(p)` и `put_unaligned(v, p)` — чтение и запись по невыровненному адресу; `round_down(x, y)` — x, округлённое вниз до кратного y (y — степень двойки); `pr_debug`, `pr_err` — сообщения в журнал, на результат не влияют; `WARN(cond, ...)` — то же, возвращает `cond`; `likely(x)` и `unlikely(x)` — то же, что x; `UINT_MAX`; `EINVAL` = 22, `ENOSPC` = 28 (функции возвращают коды со знаком минус).; `DIV_ROUND_UP(n, d)` — (n + d − 1) / d, целочисленно; `EOVERFLOW` = 75; `GENMASK_ULL(h, l)` — u64, в котором установлены биты с l по h включительно; `__be16`, `__be32`, `__be64` — u16, u32, u64 со значением в порядке big-endian (тип, без преобразования); `atomic_inc(&v)` — атомарно увеличить счётчик на 1 (здесь только счётчики отладки, их можно опустить); `MODULE_AUTHOR`, `MODULE_DESCRIPTION`, `MODULE_LICENSE`, `__init`, `__exit` — служебные, на поведение не влияют.
8. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): `u32 crc32_be(u32 crc, const u8 *p, size_t len)` — CRC32 big-endian ядра (lib/crc).
9. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Заголовок `lib/842/842.h` (типы, структуры, константы, встроенные функции):
```c
/* SPDX-License-Identifier: GPL-2.0 */

#ifndef __842_H__
#define __842_H__

/* The 842 compressed format is made up of multiple blocks, each of
 * which have the format:
 *
 * <template>[arg1][arg2][arg3][arg4]
 *
 * where there are between 0 and 4 template args, depending on the specific
 * template operation.  For normal operations, each arg is either a specific
 * number of data bytes to add to the output buffer, or an index pointing
 * to a previously-written number of data bytes to copy to the output buffer.
 *
 * The template code is a 5-bit value.  This code indicates what to do with
 * the following data.  Template codes from 0 to 0x19 should use the template
 * table, the static "decomp_ops" table used in decompress.  For each template
 * (table row), there are between 1 and 4 actions; each action corresponds to
 * an arg following the template code bits.  Each action is either a "data"
 * type action, or a "index" type action, and each action results in 2, 4, or 8
 * bytes being written to the output buffer.  Each template (i.e. all actions
 * in the table row) will add up to 8 bytes being written to the output buffer.
 * Any row with less than 4 actions is padded with noop actions, indicated by
 * N0 (for which there is no corresponding arg in the compressed data buffer).
 *
 * "Data" actions, indicated in the table by D2, D4, and D8, mean that the
 * corresponding arg is 2, 4, or 8 bytes, respectively, in the compressed data
 * buffer should be copied directly to the output buffer.
 *
 * "Index" actions, indicated in the table by I2, I4, and I8, mean the
 * corresponding arg is an index parameter that points to, respectively, a 2,
 * 4, or 8 byte value already in the output buffer, that should be copied to
 * the end of the output buffer.  Essentially, the index points to a position
 * in a ring buffer that contains the last N bytes of output buffer data.
 * The number of bits for each index's arg are: 8 bits for I2, 9 bits for I4,
 * and 8 bits for I8.  Since each index points to a 2, 4, or 8 byte section,
 * this means that I2 can reference 512 bytes ((2^8 bits = 256) * 2 bytes), I4
 * can reference 2048 bytes ((2^9 = 512) * 4 bytes), and I8 can reference 2048
 * bytes ((2^8 = 256) * 8 bytes).  Think of it as a kind-of ring buffer for
 * each of I2, I4, and I8 that are updated for each byte written to the output
 * buffer.  In this implementation, the output buffer is directly used for each
 * index; there is no additional memory required.  Note that the index is into
 * a ring buffer, not a sliding window; for example, if there have been 260
 * bytes written to the output buffer, an I2 index of 0 would index to byte 256
 * in the output buffer, while an I2 index of 16 would index to byte 16 in the
 * output buffer.
 *
 * There are also 3 special template codes; 0x1b for "repeat", 0x1c for
 * "zeros", and 0x1e for "end".  The "repeat" operation is followed by a 6 bit
 * arg N indicating how many times to repeat.  The last 8 bytes written to the
 * output buffer are written again to the output buffer, N + 1 times.  The
 * "zeros" operation, which has no arg bits, writes 8 zeros to the output
 * buffer.  The "end" operation, which also has no arg bits, signals the end
 * of the compressed data.  There may be some number of padding (don't care,
 * but usually 0) bits after the "end" operation bits, to fill the buffer
 * length to a specific byte multiple (usually a multiple of 8, 16, or 32
 * bytes).
 *
 * This software implementation also uses one of the undefined template values,
 * 0x1d as a special "short data" template code, to represent less than 8 bytes
 * of uncompressed data.  It is followed by a 3 bit arg N indicating how many
 * data bytes will follow, and then N bytes of data, which should be copied to
 * the output buffer.  This allows the software 842 compressor to accept input
 * buffers that are not an exact multiple of 8 bytes long.  However, those
 * compressed buffers containing this sw-only template will be rejected by
 * the 842 hardware decompressor, and must be decompressed with this software
 * library.  The 842 software compression module includes a parameter to
 * disable using this sw-only "short data" template, and instead simply
 * reject any input buffer that is not a multiple of 8 bytes long.
 *
 * After all actions for each operation code are processed, another template
 * code is in the next 5 bits.  The decompression ends once the "end" template
 * code is detected.
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/bitops.h>
#include <linux/crc32.h>
#include <linux/unaligned.h>

#include <linux/sw842.h>

/* special templates */
#define OP_REPEAT	(0x1B)
#define OP_ZEROS	(0x1C)
#define OP_END		(0x1E)

/* sw only template - this is not in the hw design; it's used only by this
 * software compressor and decompressor, to allow input buffers that aren't
 * a multiple of 8.
 */
#define OP_SHORT_DATA	(0x1D)

/* additional bits of each op param */
#define OP_BITS		(5)
#define REPEAT_BITS	(6)
#define SHORT_DATA_BITS	(3)
#define I2_BITS		(8)
#define I4_BITS		(9)
#define I8_BITS		(8)
#define CRC_BITS	(32)

#define REPEAT_BITS_MAX		(0x3f)
#define SHORT_DATA_BITS_MAX	(0x7)

/* Arbitrary values used to indicate action */
#define OP_ACTION	(0x70)
#define OP_ACTION_INDEX	(0x10)
#define OP_ACTION_DATA	(0x20)
#define OP_ACTION_NOOP	(0x40)
#define OP_AMOUNT	(0x0f)
#define OP_AMOUNT_0	(0x00)
#define OP_AMOUNT_2	(0x02)
#define OP_AMOUNT_4	(0x04)
#define OP_AMOUNT_8	(0x08)

#define D2		(OP_ACTION_DATA  | OP_AMOUNT_2)
#define D4		(OP_ACTION_DATA  | OP_AMOUNT_4)
#define D8		(OP_ACTION_DATA  | OP_AMOUNT_8)
#define I2		(OP_ACTION_INDEX | OP_AMOUNT_2)
#define I4		(OP_ACTION_INDEX | OP_AMOUNT_4)
#define I8		(OP_ACTION_INDEX | OP_AMOUNT_8)
#define N0		(OP_ACTION_NOOP  | OP_AMOUNT_0)

/* the max of the regular templates - not including the special templates */
#define OPS_MAX		(0x1a)

#endif
```

Заголовок `include/linux/sw842.h` (типы, структуры, константы, встроенные функции):
```c
/* SPDX-License-Identifier: GPL-2.0 */
#ifndef __SW842_H__
#define __SW842_H__

#define SW842_MEM_COMPRESS	(0xf000)

int sw842_compress(const u8 *src, unsigned int srclen,
		   u8 *dst, unsigned int *destlen, void *wmem);

int sw842_decompress(const u8 *src, unsigned int srclen,
		     u8 *dst, unsigned int *destlen);

#endif
```

Файл `lib/842/842_decompress.c`:
```c
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * 842 Software Decompression
 *
 * Copyright (C) 2015 Dan Streetman, IBM Corp
 *
 * See 842.h for details of the 842 compressed format.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
#define MODULE_NAME "842_decompress"

#include "842.h"
#include "842_debugfs.h"

/* rolling fifo sizes */
#define I2_FIFO_SIZE	(2 * (1 << I2_BITS))
#define I4_FIFO_SIZE	(4 * (1 << I4_BITS))
#define I8_FIFO_SIZE	(8 * (1 << I8_BITS))

static u8 decomp_ops[OPS_MAX][4] = {
	{ D8, N0, N0, N0 },
	{ D4, D2, I2, N0 },
	{ D4, I2, D2, N0 },
	{ D4, I2, I2, N0 },
	{ D4, I4, N0, N0 },
	{ D2, I2, D4, N0 },
	{ D2, I2, D2, I2 },
	{ D2, I2, I2, D2 },
	{ D2, I2, I2, I2 },
	{ D2, I2, I4, N0 },
	{ I2, D2, D4, N0 },
	{ I2, D4, I2, N0 },
	{ I2, D2, I2, D2 },
	{ I2, D2, I2, I2 },
	{ I2, D2, I4, N0 },
	{ I2, I2, D4, N0 },
	{ I2, I2, D2, I2 },
	{ I2, I2, I2, D2 },
	{ I2, I2, I2, I2 },
	{ I2, I2, I4, N0 },
	{ I4, D4, N0, N0 },
	{ I4, D2, I2, N0 },
	{ I4, I2, D2, N0 },
	{ I4, I2, I2, N0 },
	{ I4, I4, N0, N0 },
	{ I8, N0, N0, N0 }
};

struct sw842_param {
	u8 *in;
	u8 bit;
	u64 ilen;
	u8 *out;
	u8 *ostart;
	u64 olen;
};

#define beN_to_cpu(d, s)					\
	((s) == 2 ? be16_to_cpu(get_unaligned((__be16 *)d)) :	\
	 (s) == 4 ? be32_to_cpu(get_unaligned((__be32 *)d)) :	\
	 (s) == 8 ? be64_to_cpu(get_unaligned((__be64 *)d)) :	\
	 0)

static int next_bits(struct sw842_param *p, u64 *d, u8 n);

static int __split_next_bits(struct sw842_param *p, u64 *d, u8 n, u8 s)
{
	u64 tmp = 0;
	int ret;

	if (n <= s) {
		pr_debug("split_next_bits invalid n %u s %u\n", n, s);
		return -EINVAL;
	}

	ret = next_bits(p, &tmp, n - s);
	if (ret)
		return ret;
	ret = next_bits(p, d, s);
	if (ret)
		return ret;
	*d |= tmp << s;
	return 0;
}

static int next_bits(struct sw842_param *p, u64 *d, u8 n)
{
	u8 *in = p->in, b = p->bit, bits = b + n;

	if (n > 64) {
		pr_debug("next_bits invalid n %u\n", n);
		return -EINVAL;
	}

	/* split this up if reading > 8 bytes, or if we're at the end of
	 * the input buffer and would read past the end
	 */
	if (bits > 64)
		return __split_next_bits(p, d, n, 32);
	else if (p->ilen < 8 && bits > 32 && bits <= 56)
		return __split_next_bits(p, d, n, 16);
	else if (p->ilen < 4 && bits > 16 && bits <= 24)
		return __split_next_bits(p, d, n, 8);

	if (DIV_ROUND_UP(bits, 8) > p->ilen)
		return -EOVERFLOW;

	if (bits <= 8)
		*d = *in >> (8 - bits);
	else if (bits <= 16)
		*d = be16_to_cpu(get_unaligned((__be16 *)in)) >> (16 - bits);
	else if (bits <= 32)
		*d = be32_to_cpu(get_unaligned((__be32 *)in)) >> (32 - bits);
	else
		*d = be64_to_cpu(get_unaligned((__be64 *)in)) >> (64 - bits);

	*d &= GENMASK_ULL(n - 1, 0);

	p->bit += n;

	if (p->bit > 7) {
		p->in += p->bit / 8;
		p->ilen -= p->bit / 8;
		p->bit %= 8;
	}

	return 0;
}

static int do_data(struct sw842_param *p, u8 n)
{
	u64 v;
	int ret;

	if (n > p->olen)
		return -ENOSPC;

	ret = next_bits(p, &v, n * 8);
	if (ret)
		return ret;

	switch (n) {
	case 2:
		put_unaligned(cpu_to_be16((u16)v), (__be16 *)p->out);
		break;
	case 4:
		put_unaligned(cpu_to_be32((u32)v), (__be32 *)p->out);
		break;
	case 8:
		put_unaligned(cpu_to_be64((u64)v), (__be64 *)p->out);
		break;
	default:
		return -EINVAL;
	}

	p->out += n;
	p->olen -= n;

	return 0;
}

static int __do_index(struct sw842_param *p, u8 size, u8 bits, u64 fsize)
{
	u64 index, offset, total = round_down(p->out - p->ostart, 8);
	int ret;

	if (size > p->olen)
		return -ENOSPC;

	ret = next_bits(p, &index, bits);
	if (ret)
		return ret;

	offset = index * size;

	/* a ring buffer of fsize is used; correct the offset */
	if (total > fsize) {
		/* this is where the current fifo is */
		u64 section = round_down(total, fsize);
		/* the current pos in the fifo */
		u64 pos = total - section;

		/* if the offset is past/at the pos, we need to
		 * go back to the last fifo section
		 */
		if (offset >= pos)
			section -= fsize;

		offset += section;
	}

	if (offset + size > total) {
		pr_debug("index%x %lx points past end %lx\n", size,
			 (unsigned long)offset, (unsigned long)total);
		return -EINVAL;
	}

	if (size != 2 && size != 4 && size != 8)
		WARN(1, "__do_index invalid size %x\n", size);
	else
		pr_debug("index%x to %lx off %lx adjoff %lx tot %lx data %lx\n",
			 size, (unsigned long)index,
			 (unsigned long)(index * size), (unsigned long)offset,
			 (unsigned long)total,
			 (unsigned long)beN_to_cpu(&p->ostart[offset], size));

	memcpy(p->out, &p->ostart[offset], size);
	p->out += size;
	p->olen -= size;

	return 0;
}

static int do_index(struct sw842_param *p, u8 n)
{
	switch (n) {
	case 2:
		return __do_index(p, 2, I2_BITS, I2_FIFO_SIZE);
	case 4:
		return __do_index(p, 4, I4_BITS, I4_FIFO_SIZE);
	case 8:
		return __do_index(p, 8, I8_BITS, I8_FIFO_SIZE);
	default:
		return -EINVAL;
	}
}

static int do_op(struct sw842_param *p, u8 o)
{
	int i, ret = 0;

	if (o >= OPS_MAX)
		return -EINVAL;

	for (i = 0; i < 4; i++) {
		u8 op = decomp_ops[o][i];

		pr_debug("op is %x\n", op);

		switch (op & OP_ACTION) {
		case OP_ACTION_DATA:
			ret = do_data(p, op & OP_AMOUNT);
			break;
		case OP_ACTION_INDEX:
			ret = do_index(p, op & OP_AMOUNT);
			break;
		case OP_ACTION_NOOP:
			break;
		default:
			pr_err("Internal error, invalid op %x\n", op);
			return -EINVAL;
		}

		if (ret)
			return ret;
	}

	if (sw842_template_counts)
		atomic_inc(&template_count[o]);

	return 0;
}

/**
 * sw842_decompress
 *
 * Decompress the 842-compressed buffer of length @ilen at @in
 * to the output buffer @out, using no more than @olen bytes.
 *
 * The compressed buffer must be only a single 842-compressed buffer,
 * with the standard format described in the comments in 842.h
 * Processing will stop when the 842 "END" template is detected,
 * not the end of the buffer.
 *
 * Returns: 0 on success, error on failure.  The @olen parameter
 * will contain the number of output bytes written on success, or
 * 0 on error.
 */
int sw842_decompress(const u8 *in, unsigned int ilen,
		     u8 *out, unsigned int *olen)
{
	struct sw842_param p;
	int ret;
	u64 op, rep, tmp, bytes, total;
	u64 crc;

	p.in = (u8 *)in;
	p.bit = 0;
	p.ilen = ilen;
	p.out = out;
	p.ostart = out;
	p.olen = *olen;

	total = p.olen;

	*olen = 0;

	do {
		ret = next_bits(&p, &op, OP_BITS);
		if (ret)
			return ret;

		pr_debug("template is %lx\n", (unsigned long)op);

		switch (op) {
		case OP_REPEAT:
			ret = next_bits(&p, &rep, REPEAT_BITS);
			if (ret)
				return ret;

			if (p.out - p.ostart < 8) /* no complete previous block */
				return -EINVAL;

			/* copy rep + 1 */
			rep++;

			if (rep * 8 > p.olen)
				return -ENOSPC;

			while (rep-- > 0) {
				memcpy(p.out, p.out - 8, 8);
				p.out += 8;
				p.olen -= 8;
			}

			if (sw842_template_counts)
				atomic_inc(&template_repeat_count);

			break;
		case OP_ZEROS:
			if (8 > p.olen)
				return -ENOSPC;

			memset(p.out, 0, 8);
			p.out += 8;
			p.olen -= 8;

			if (sw842_template_counts)
				atomic_inc(&template_zeros_count);

			break;
		case OP_SHORT_DATA:
			ret = next_bits(&p, &bytes, SHORT_DATA_BITS);
			if (ret)
				return ret;

			if (!bytes || bytes > SHORT_DATA_BITS_MAX)
				return -EINVAL;
			if (bytes > p.olen)
				return -ENOSPC;

			while (bytes-- > 0) {
				ret = next_bits(&p, &tmp, 8);
				if (ret)
					return ret;
				*p.out = (u8)tmp;
				p.out++;
				p.olen--;
			}

			if (sw842_template_counts)
				atomic_inc(&template_short_data_count);

			break;
		case OP_END:
			if (sw842_template_counts)
				atomic_inc(&template_end_count);

			break;
		default: /* use template */
			ret = do_op(&p, op);
			if (ret)
				return ret;
			break;
		}
	} while (op != OP_END);

	/*
	 * crc(0:31) is saved in compressed data starting with the
	 * next bit after End of stream template.
	 */
	ret = next_bits(&p, &crc, CRC_BITS);
	if (ret)
		return ret;

	/*
	 * Validate CRC saved in compressed data.
	 */
	if (crc != (u64)crc32_be(0, out, total - p.olen)) {
		pr_debug("CRC mismatch for decompression\n");
		return -EINVAL;
	}

	if (unlikely((total - p.olen) > UINT_MAX))
		return -ENOSPC;

	*olen = total - p.olen;

	return 0;
}
EXPORT_SYMBOL_GPL(sw842_decompress);

static int __init sw842_init(void)
{
	if (sw842_template_counts)
		sw842_debugfs_create();

	return 0;
}
module_init(sw842_init);

static void __exit sw842_exit(void)
{
	if (sw842_template_counts)
		sw842_debugfs_remove();
}
module_exit(sw842_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Software 842 Decompressor");
MODULE_AUTHOR("Dan Streetman <ddstreet@ieee.org>");
```
