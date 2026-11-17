// SPDX-License-Identifier: GPL-2.0-only
//! Перевод lib/math/gcd.c (x86_64, BITS_PER_LONG = 64,
//! CONFIG_CPU_NO_EFFICIENT_FFS не задан).
//!
//! Двоичный алгоритм НОД (часто приписывается Стейну; как заметил Кнут,
//! встречается в китайском математическом тексте I века).

use core::ffi::c_ulong;

/// DEFINE_STATIC_KEY_TRUE(efficient_ffs_key): в этой конфигурации ключ включён.
/// Переменная ключа не экспортируется.
struct StaticKeyTrue {
    enabled: bool,
}

static EFFICIENT_FFS_KEY: StaticKeyTrue = StaticKeyTrue { enabled: true };

/// static_branch_likely(&key): условие истинно, пока ключ включён.
#[inline(always)]
fn static_branch_likely(key: &StaticKeyTrue) -> bool {
    key.enabled
}

/// __ffs(x): номер младшего установленного бита, считая с 0 (x != 0).
#[inline(always)]
fn __ffs(x: c_ulong) -> u32 {
    x.trailing_zeros()
}

/* If __ffs is available, the even/odd algorithm benchmarks slower. */

fn binary_gcd(mut a: c_ulong, mut b: c_ulong) -> c_ulong {
    let r: c_ulong = a | b;

    b >>= __ffs(b);
    if b == 1 {
        return r & r.wrapping_neg();
    }

    loop {
        a >>= __ffs(a);
        if a == 1 {
            return r & r.wrapping_neg();
        }
        if a == b {
            return a << __ffs(r);
        }

        if a < b {
            core::mem::swap(&mut a, &mut b);
        }
        a = a.wrapping_sub(b);
    }
}

/* If normalization is done by loops, the even/odd algorithm is a win. */

/// gcd - calculate and return the greatest common divisor of 2 unsigned longs
/// @a: first value
/// @b: second value
#[no_mangle]
pub extern "C" fn gcd(mut a: c_ulong, mut b: c_ulong) -> c_ulong {
    let mut r: c_ulong = a | b;

    if a == 0 || b == 0 {
        return r;
    }

    if static_branch_likely(&EFFICIENT_FFS_KEY) {
        return binary_gcd(a, b);
    }

    /* Isolate lsbit of r */
    r &= r.wrapping_neg();

    while b & r == 0 {
        b >>= 1;
    }
    if b == r {
        return r;
    }

    loop {
        while a & r == 0 {
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
        if a & r != 0 {
            a = a.wrapping_add(b);
        }
        a >>= 1;
    }
}
