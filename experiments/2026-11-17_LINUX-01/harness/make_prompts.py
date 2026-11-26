#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01: поручения переводчикам — prompts/<модуль>.md. Одинаковые для всех голов; содержат только исходник модуля,
условия сборки, смысл макросов ядра и список внешних функций. Тестов, обвязки и путей к ним в поручении нет.
  python3 harness/make_prompts.py"""
import os

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTHOR = '«делай пилот с модулем Линукса.»'
MODS = {
    'int_pow': ('lib/math/int_pow.c', 'нет особых', 'нет'),
    'int_sqrt': ('lib/math/int_sqrt.c', '`__fls(x)` — номер старшего установленного бита, считая с 0 (x ≠ 0); `ULONG_MAX`.', 'нет'),
    'gcd': ('lib/math/gcd.c',
            '`__ffs(x)` — номер младшего установленного бита, считая с 0 (x ≠ 0); `swap(a, b)` — обмен значениями; '
            '`DEFINE_STATIC_KEY_TRUE(efficient_ffs_key)` и `static_branch_likely(&efficient_ffs_key)` — статический ключ ядра, в этой '
            'конфигурации включён (условие истинно); переменную ключа экспортировать не нужно.', 'нет'),
    'rational': ('lib/math/rational.c', '`min(a, b)` — меньшее; `ULONG_MAX`.', 'нет'),
    'int_log': ('lib/math/int_log.c',
                '`fls(x)` — номер старшего установленного бита, считая с 1; 0 для x = 0; `ARRAY_SIZE(a)` — число элементов массива; '
                '`WARN_ON(1)` — предупреждение в журнал ядра, на результат не влияет (в переводе можно опустить); `unlikely(x)` — то же, что x.',
                'нет'),
    'cmdline': ('lib/cmdline.c',
                '`isspace(c)` — в ядре истинно для байтов 9–13, 32 и 160; `INT_MAX`, `ULLONG_MAX`; `likely(x)`/`unlikely(x)` — то же, что x; '
                '`fallthrough` — проваливание в следующую ветку switch; `check_sub_overflow(a, b, &d)` — d = a − b для int, '
                'возвращает истину при переполнении (в d — результат с заворачиванием); `check_shl_overflow(a, s, &d)` — для unsigned long long: '
                'если s ≥ 64, сдвиг считается на 0, d = a << s, возвращает истину, если s ≥ 64 или (d >> s) ≠ a.',
                '`unsigned long long simple_strtoull(const char *cp, char **endp, unsigned int base)`, '
                '`long simple_strtol(const char *cp, char **endp, unsigned int base)`, `char *skip_spaces(const char *str)`, '
                '`size_t strlen(const char *s)`, `int strncmp(const char *a, const char *b, size_t n)`'),
}
TEMPLATE = """LINUX-01, переводчик. Последнее сообщение автора исследования (дословно): {author}

Задача: переведи файл ядра Linux `{path}` (ниже целиком) с C на Rust так, чтобы перевод можно было подставить вместо оригинала.

Условия:
1. Конфигурация: x86_64, BITS_PER_LONG = 64; `unsigned long` = `core::ffi::c_ulong` (64 бита), `int` = `c_int` (32 бита), `unsigned int` = `c_uint`, `u32`/`u64` — `u32`/`u64`; `CONFIG_CPU_NO_EFFICIENT_FFS` не задан. Код под `#if`, который в этой конфигурации не собирается, не переводи и не экспортируй.
2. Каждую нестатическую функцию (с EXPORT_SYMBOL) экспортируй с тем же именем и той же сигнатурой C: `#[no_mangle] pub extern "C" fn имя(...)`. Статические функции — обычные функции Rust.
3. Сборка: `rustc --edition 2021 --crate-type staticlib -C opt-level=2 -C overflow-checks=on -C panic=abort`. Проверки переполнения включены, как CONFIG_RUST_OVERFLOW_CHECKS в ядре. Где C полагается на заворачивание беззнаковых чисел, пиши `wrapping_*` явно; приведения типов и сдвиги повторяй так, как их выполняет C на x86_64 с GCC.
4. Поведение должно совпадать с оригиналом на всех входах, включая крайние (0, наибольшие значения, пустые строки): те же возвращаемые значения, те же записи по указателям, те же положения указателей на выходе, те же изменения в строках.
5. Только `core`: без `alloc`, без ввода-вывода. Не пиши `#![no_std]`. `unsafe` — только там, где этого требуют сырые указатели C-сигнатуры.
6. Макросы и встроенные функции ядра из этого файла переведи сами по их смыслу: {macros}
7. Внешние функции ядра, которые можно вызывать через `extern "C"` (они будут слинкованы): {externs}.
8. Ответ: один файл Rust целиком в одном блоке ```rust … ```. Пояснений вне блока не нужно.

Файл `{path}`:
```c
{source}
```
"""


def main():
    os.makedirs(os.path.join(X, 'prompts'), exist_ok=True)
    for m, (path, macros, externs) in MODS.items():
        src = open(os.path.join(X, 'src', path), encoding='utf-8').read().rstrip('\n')
        txt = TEMPLATE.format(author=AUTHOR, path=path, macros=macros, externs=externs, source=src)
        open(os.path.join(X, 'prompts', f'{m}.md'), 'w', encoding='utf-8').write(txt)
        print(m, len(txt), 'символов')


if __name__ == '__main__':
    main()
