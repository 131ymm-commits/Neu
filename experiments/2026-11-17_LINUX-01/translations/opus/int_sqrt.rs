// SPDX-License-Identifier: GPL-2.0
//
// Copyright (C) 2013 Davidlohr Bueso <davidlohr.bueso@hp.com>
//
//  Based on the shift-and-subtract algorithm for computing integer
//  square root from Guy L. Steele.
//
// Rust translation of lib/math/int_sqrt.c for x86_64 (BITS_PER_LONG == 64).
// int_sqrt64 is compiled only when BITS_PER_LONG < 64, so it is omitted here.

use core::ffi::c_ulong;

/// __fls - index of the most significant set bit, counting from 0.
/// The caller guarantees `x != 0`.
#[inline(always)]
fn __fls(x: c_ulong) -> c_ulong {
    ((c_ulong::BITS - 1) - x.leading_zeros()) as c_ulong
}

/// int_sqrt - computes the integer square root
/// @x: integer of which to calculate the sqrt
///
/// Computes: floor(sqrt(x))
#[no_mangle]
pub extern "C" fn int_sqrt(x: c_ulong) -> c_ulong {
    let mut x = x;
    let mut b: c_ulong;
    let mut m: c_ulong;
    let mut y: c_ulong = 0;

    if x <= 1 {
        return x;
    }

    m = (1 as c_ulong) << (__fls(x) & !(1 as c_ulong));
    while m != 0 {
        b = y.wrapping_add(m);
        y >>= 1;

        if x >= b {
            x = x.wrapping_sub(b);
            y = y.wrapping_add(m);
        }
        m >>= 2;
    }

    y
}
