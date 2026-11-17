// SPDX-License-Identifier: GPL-2.0-only
// Перевод lib/math/gcd.c (конфигурация: x86_64, CONFIG_CPU_NO_EFFICIENT_FFS не задан).

use core::ffi::c_ulong;

// Аналог DEFINE_STATIC_KEY_TRUE(efficient_ffs_key): ключ включён, условие истинно.
// Сам ключ не экспортируется.
const EFFICIENT_FFS_KEY: bool = true;

// Двоичный алгоритм НОД (Штейн). Используется, когда ключ включён.
fn binary_gcd(mut a: c_ulong, mut b: c_ulong) -> c_ulong {
    let r = a | b;

    // __ffs(b): b != 0 по контракту gcd()
    b >>= b.trailing_zeros();
    if b == 1 {
        return r & r.wrapping_neg();
    }

    loop {
        a >>= a.trailing_zeros();
        if a == 1 {
            return r & r.wrapping_neg();
        }
        if a == b {
            return a << r.trailing_zeros();
        }

        if a < b {
            core::mem::swap(&mut a, &mut b);
        }
        a = a.wrapping_sub(b);
    }
}

/// Возвращает наибольший общий делитель двух беззнаковых long.
#[no_mangle]
pub extern "C" fn gcd(mut a: c_ulong, mut b: c_ulong) -> c_ulong {
    let mut r = a | b;

    if a == 0 || b == 0 {
        return r;
    }

    if EFFICIENT_FFS_KEY {
        return binary_gcd(a, b);
    }

    // Выделить младший установленный бит r
    r &= r.wrapping_neg();

    while (b & r) == 0 {
        b >>= 1;
    }
    if b == r {
        return r;
    }

    loop {
        while (a & r) == 0 {
            a >>= 1;
        }
        if a == r {
            return r;
        }
        if a == b {
            return a;
        }

        if a < b {
            core::mem::swap(&mut a, &mut b);
        }
        a = a.wrapping_sub(b);
        a >>= 1;
        if (a & r) != 0 {
            a = a.wrapping_add(b);
        }
        a >>= 1;
    }
}
