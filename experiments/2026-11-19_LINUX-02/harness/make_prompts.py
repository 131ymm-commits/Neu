#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: поручения переводчикам — prompts/<модуль>.md. Одинаковые для всех голов и всех повторов. Содержат только исходник
модуля, его заголовки (типы, структуры, константы, встроенные функции), условия сборки, смысл макросов ядра и список внешних функций.
Тестов, обвязки и путей к ним в поручении нет.
Отличие от LINUX-01: слова автора в поручение не кладутся. Голова могла бы принять их за указание (урок ERRORS № 31). Последнее
сообщение автора (о DISTILL-02, «…додестелировать до простой математики») к переводу не относится и могло бы подтолкнуть голову
«упростить» код.
Версии: pilot — как было (prompts/<модуль>.md; перед записью сверяется с хешами prompts/prompts.json, менять их нельзя);
test — то же плюс объяснения имён, пропущенных в пилоте (ERRORS № 216, DEVIATIONS п. 8), в prompts/test/. Поручение версии test
не пишется, пока harness/prompt_coverage.py находит в нём пропуск.
  python3 harness/make_prompts.py [--version pilot|test]"""
import hashlib
import json
import os

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTYPE = ('по таблице ядра (lib/ctype.c, Latin-1): `isprint(c)` истинно для байтов 32–126 и 160–255; `isspace(c)` — для 9–13, 32 и 160; '
         '`isascii(c)` — для 0–127; `isodigit(c)` — для «0»–«7»')
MODS = {
    'errseq': dict(
        path='lib/errseq.c', headers=['include/linux/errseq.h'],
        config='Функции могут вызываться из разных потоков одновременно: `READ_ONCE` и `cmpxchg` над `errseq_t` должны быть атомарными '
               '(в Rust — `core::sync::atomic::AtomicU32` над тем же адресом, например через `AtomicU32::from_ptr`).',
        macros='`READ_ONCE(*p)` — однократное атомарное чтение; `cmpxchg(p, old, new)` — атомарно: если `*p == old`, записать `new`; '
               'вернуть значение `*p` до операции; `ilog2(n)` — номер старшего установленного бита, считая с 0 (n > 0); `MAX_ERRNO` = 4095 '
               '(include/linux/err.h); `WARN(cond, fmt, ...)` — предупреждение в журнал, возвращает `cond` (на результат влияет только как '
               'условие); `likely(x)` и `unlikely(x)` — то же, что x.',
        externs='нет'),
    '842_decompress': dict(
        path='lib/842/842_decompress.c', headers=['lib/842/842.h', 'include/linux/sw842.h'],
        config='Параметр модуля `template_counts` выключен (false): счётчики отладки из `842_debugfs.h` (`template_count`, '
               '`template_repeat_count` и другие) наружу не видны, в переводе их можно опустить. `sw842_debugfs_create`, '
               '`sw842_debugfs_remove`, `module_init`, `module_exit` не нужны.',
        macros='`be16_to_cpu`, `be32_to_cpu`, `be64_to_cpu` — из big-endian в порядок машины (little-endian); `cpu_to_be16`, `cpu_to_be32`, '
               '`cpu_to_be64` — обратно; `get_unaligned(p)` и `put_unaligned(v, p)` — чтение и запись по невыровненному адресу; '
               '`round_down(x, y)` — x, округлённое вниз до кратного y (y — степень двойки); `pr_debug`, `pr_err` — сообщения в журнал, на '
               'результат не влияют; `WARN(cond, ...)` — то же, возвращает `cond`; `likely(x)` и `unlikely(x)` — то же, что x; `UINT_MAX`; '
               '`EINVAL` = 22, `ENOSPC` = 28 (функции возвращают коды со знаком минус).',
        externs='`u32 crc32_be(u32 crc, const u8 *p, size_t len)` — CRC32 big-endian ядра (lib/crc)'),
    'md5': dict(
        path='lib/crypto/md5.c', headers=['include/crypto/md5.h', 'include/crypto/hmac.h'],
        config='Архитектурной реализации MD5 нет: используется общая, код этого файла.',
        macros='`rol32(x, n)` — циклический сдвиг u32 влево на n; `le32_to_cpu_array(p, n)` и `cpu_to_le32_array(p, n)` — на little-endian '
               'ничего не делают; `cpu_to_le64(x)` — x; `memzero_explicit(p, n)` — обнулить n байт (запись не должна выбрасываться); '
               '`memcpy`, `memset` — как в C; `ARRAY_SIZE(a)` — число элементов массива; `likely(x)` и `unlikely(x)` — то же, что x; '
               '`static_assert` — проверка при сборке.',
        externs='нет'),
    'random32': dict(
        path='lib/random32.c', headers=['include/linux/prandom.h'],
        config='Один возможный процессор: `for_each_possible_cpu(i)` перебирает только i = 0, `per_cpu_ptr(p, 0)` — сам p (`__percpu` — '
               'обычный указатель). Тесты KUnit собраны (`CONFIG_KUNIT`), поэтому `VISIBLE_IF_KUNIT`-функция `prandom_warmup` нестатическая и '
               'экспортируется (`EXPORT_SYMBOL_IF_KUNIT` — как `EXPORT_SYMBOL`).',
        macros='`put_unaligned(v, p)` — запись по невыровненному адресу; `BITS_PER_BYTE` = 8; `likely(x)` и `unlikely(x)` — то же, что x.',
        externs='`void get_random_bytes(void *buf, size_t len)`'),
    'min_heap': dict(
        path='lib/min_heap.c', headers=['include/linux/min_heap.h'],
        config='Экспортируемые функции этого файла вызывают встроенные (`inline`) функции заголовка ниже — их тоже нужно перевести, по тексту '
               'заголовка. Экспортировать нужно только функции этого файла.',
        macros='`WARN_ONCE(cond, ...)` и `WARN_ON_ONCE(cond)` — предупреждение в журнал, возвращают `cond`; `likely(x)` и `unlikely(x)` — то '
               'же, что x; `typeof`, `sizeof` — по смыслу C; `IS_ENABLED(CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS)` — истинно (x86_64); '
               '`lower_32_bits(x)` — младшие 32 бита.',
        externs='нет'),
    'string_helpers': dict(
        path='lib/string_helpers.c', headers=['include/linux/string_helpers.h'],
        config='`CONFIG_FORTIFY_SOURCE` не задан: код под `#ifdef CONFIG_FORTIFY_SOURCE` не переводи. `gfp_t` — `c_uint`; `GFP_KERNEL` = '
               '0xcc0. Указатели `__user` — обычные указатели. `struct file`, `struct task_struct`, `struct device` — непрозрачные (только '
               'указатели).',
        macros=CTYPE + '; `do_div(n, base)` — n (u64) делится на base (u32) на месте, возвращается остаток (u32); `umin(a, b)` — меньшее '
               'из беззнаковых; `str_read_write(v)` — строка «read» при v, иначе «write»; `kzalloc_objs(p, n)` — то же, что '
               '`kcalloc(n, sizeof(*p), GFP_KERNEL)`; `devres_alloc(release, size, gfp)` — то же, что `__devres_alloc_node(release, size, '
               'gfp, -1, "<имя функции release>")`; `IS_ERR(p)` — истинно, если адрес p как беззнаковое число не меньше (unsigned long)-4095; '
               '`ERR_PTR(e)` — число e как указатель; `PTR_ERR(p)` — указатель как long; `WARN_ON(cond)` — предупреждение, возвращает cond; '
               '`BUG()` — остановка ядра (в Rust — panic); `ARRAY_SIZE(a)` — число элементов; `__counted_by_ptr(n)` — атрибут, ни на что не '
               'влияет; `EINVAL` = 22, `ENOMEM` = 12, `ENOENT` = 2.',
        externs='`void *kmalloc(size_t size, gfp_t flags)`, `void *kcalloc(size_t n, size_t size, gfp_t flags)`, `void kfree(const void *p)`, '
                '`char *kstrdup(const char *s, gfp_t gfp)`, `char *kasprintf(gfp_t gfp, const char *fmt, ...)`, '
                '`int snprintf(char *buf, size_t size, const char *fmt, ...)`, `char *get_options(const char *str, int nints, int *ints)` '
                '(lib/cmdline.c), `int hex_to_bin(unsigned char ch)` (0–15 или −1), `void *memdup_user_nul(const void __user *src, size_t len)`, '
                '`char *file_path(struct file *file, char *buf, int buflen)`, `int get_cmdline(struct task_struct *task, char *buffer, int buflen)`, '
                '`void *__devres_alloc_node(void (*release)(struct device *dev, void *res), size_t size, gfp_t gfp, int nid, const char *name)`, '
                '`void devres_add(struct device *dev, void *res)`, `void devres_free(void *res)`, `size_t strlen(const char *s)`, '
                '`int strcmp(const char *a, const char *b)`'),
}
# Объяснения для версии test (имена, которые нашёл prompt_coverage.py в поручениях пилота; смысл — по заглушкам обвязки,
# сверенным с ядром: harness/kernel_shim.h)
TEST_EXTRA = {
    'errseq': '',
    '842_decompress': '`DIV_ROUND_UP(n, d)` — (n + d − 1) / d, целочисленно; `EOVERFLOW` = 75; `GENMASK_ULL(h, l)` — u64, в котором '
                      'установлены биты с l по h включительно; `__be16`, `__be32`, `__be64` — u16, u32, u64 со значением в порядке big-endian '
                      '(тип, без преобразования); `atomic_inc(&v)` — атомарно увеличить счётчик на 1 (здесь только счётчики отладки, их можно '
                      'опустить); `MODULE_AUTHOR`, `MODULE_DESCRIPTION`, `MODULE_LICENSE`, `__init`, `__exit` — служебные, на поведение не влияют.',
    'md5': '`REPEAT_BYTE(x)` — `unsigned long`, в каждом из 8 байтов которого стоит x: `(~0UL / 0xff) * x`; `__aligned(n)` — выравнивание '
           'поля или переменной на n байт (`__alignof__(__le64)` = 8); `__le64` — u64 со значением в порядке little-endian (тип, без '
           'преобразования); `at_least` — пометка размера параметра-массива (в C — `static`), на поведение не влияет; '
           '`MODULE_DESCRIPTION`, `MODULE_LICENSE` — служебные.',
    'random32': '`IS_ENABLED(CONFIG_…)` — 1, если параметр задан, иначе 0 (здесь задан `CONFIG_KUNIT`); `__u32` — u32.',
    'min_heap': '`CONFIG_64BIT` задан (x86_64): ветви `#ifdef CONFIG_64BIT` действуют; `__always_inline` — пометка встраивания, на '
                'поведение не влияет; `container_of(ptr, type, member)` — указатель на структуру type, в которой ptr указывает на поле '
                'member: `(type *)((char *)ptr - offsetof(type, member))`.',
    'string_helpers': '`BIT(n)` — `1UL << n`; `GENMASK(h, l)` — `unsigned long`, в котором установлены биты с l по h включительно; '
                      '`PAGE_SIZE` = 4096; `PATH_MAX` = 4096; `WARN(cond, fmt, ...)` — предупреждение в журнал, возвращает cond; '
                      '`hex_asc_hi(x)` и `hex_asc_lo(x)` — символ строчной шестнадцатеричной цифры (`"0123456789abcdef"`) старшей и '
                      'младшей тетрады байта x; `tolower(c)` и `toupper(c)` — по таблице ядра (Latin-1): заглавные — «A»–«Z», 192–214 и '
                      '216–222, строчные — «a»–«z», 223–246 и 248–255; `tolower` прибавляет 32 к заглавной, `toupper` вычитает 32 из '
                      'строчной, остальные байты не меняет.',
}
TEMPLATE = """LINUX-02, переводчик.

Задача: переведи файл ядра Linux `{path}` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала: те же экспортируемые функции и то же поведение.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64, little-endian; `unsigned long` = `core::ffi::c_ulong` (64 бита), `long` = `c_long`, `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `size_t` = `usize`, `char` = `c_char`, `bool` = `bool`, `u8`/`u16`/`u32`/`u64` и `s8`…`s64` — соответствующие целые Rust. {config}
2. Каждую нестатическую функцию (с `EXPORT_SYMBOL`, `EXPORT_SYMBOL_GPL` или `EXPORT_SYMBOL_IF_KUNIT`) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Структуры, которые передаются в эти функции или из них, объяви `#[repr(C)]` с тем же порядком и типами полей, что в заголовках ниже: вызывающий код на C передаёт свои структуры.
4. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковой арифметики, используй `wrapping_*`.
5. Поведение должно совпадать с оригиналом на всех входах, включая крайние: те же возвращаемые значения, те же записи в выходные буферы и структуры, те же вызовы внешних функций.
6. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры и вызовы внешних функций.
7. Макросы и встроенные функции ядра переведи сами по их смыслу: {macros}
8. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): {externs}.
9. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

{headers}Файл `{path}`:
```c
{source}
```
"""


def read(p):
    return open(os.path.join(X, 'src', p), encoding='utf-8').read().rstrip('\n')


def build(m, d, version):
    macros = d['macros'] + (('; ' + TEST_EXTRA[m]) if version == 'test' and TEST_EXTRA[m] else '')
    hdr = ''.join(f"Заголовок `{h}` (типы, структуры, константы, встроенные функции):\n```c\n{read(h)}\n```\n\n" for h in d['headers'])
    return TEMPLATE.format(path=d['path'], config=d['config'], macros=macros, externs=d['externs'], headers=hdr, source=read(d['path']))


def main(a):
    version = a[a.index('--version') + 1] if '--version' in a else 'pilot'
    assert version in ('pilot', 'test'), version
    out_dir = os.path.join(X, 'prompts') if version == 'pilot' else os.path.join(X, 'prompts', 'test')
    os.makedirs(out_dir, exist_ok=True)
    committed = json.load(open(os.path.join(X, 'prompts', 'prompts.json'), encoding='utf-8')) if version == 'pilot' else {}
    texts, out = {}, {}
    for m, d in MODS.items():
        txt = build(m, d, version)
        sha = hashlib.sha256(txt.encode()).hexdigest()
        if version == 'pilot' and committed.get(m, {}).get('sha256') not in (None, sha):
            raise SystemExit(f'СТОП: поручение пилота {m} вышло не таким, как закоммиченное (хеш) — пилотные поручения не меняются')
        texts[m] = txt
        out[m] = dict(chars=len(txt), sha256=sha,
                      c_lines=sum(1 for l in read(d['path']).splitlines() if l.strip()),
                      header_lines=sum(1 for h in d['headers'] for l in read(h).splitlines() if l.strip()))
    if version == 'test':
        import prompt_coverage as PC                       # noqa: E402  (рядом в harness/)
        shim = PC.shim_names()
        bad = {m: PC.gaps(m, t, shim)[0] for m, t in texts.items()}
        bad = {m: g for m, g in bad.items() if g}
        if bad:
            raise SystemExit(f'СТОП: в поручениях версии test есть необъяснённые имена: {bad}')
    for m, txt in texts.items():
        open(os.path.join(out_dir, f'{m}.md'), 'w', encoding='utf-8').write(txt)
        print(version, m, out[m]['chars'], 'символов; строк C:', out[m]['c_lines'], '+ заголовки', out[m]['header_lines'])
    json.dump(out, open(os.path.join(out_dir, 'prompts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main(sys.argv[1:])
