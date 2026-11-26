// SPDX-License-Identifier: GPL-2.0
//! rational fractions
//!
//! Copyright (C) 2009 emlix GmbH, Oskar Schirmer <oskar@scara.com>
//! Copyright (C) 2019 Trent Piepho <tpiepho@gmail.com>
//!
//! helper functions when coping with rational numbers
//!
//! Rust translation of lib/math/rational.c (x86_64, BITS_PER_LONG = 64).

use core::ffi::c_ulong;

const ULONG_MAX: c_ulong = c_ulong::MAX;

#[inline(always)]
fn min(a: c_ulong, b: c_ulong) -> c_ulong {
    if a < b {
        a
    } else {
        b
    }
}

/// Calculate best rational approximation for a given fraction
/// taking into account restricted register size.
///
/// See https://en.wikipedia.org/wiki/Continued_fraction
#[no_mangle]
pub extern "C" fn rational_best_approximation(
    given_numerator: c_ulong,
    given_denominator: c_ulong,
    max_numerator: c_ulong,
    max_denominator: c_ulong,
    best_numerator: *mut c_ulong,
    best_denominator: *mut c_ulong,
) {
    // n/d is the starting rational, which is continually
    // decreased each iteration using the Euclidean algorithm.
    //
    // dp is the value of d from the prior iteration.
    //
    // n2/d2, n1/d1, and n0/d0 are our successively more accurate
    // approximations of the rational. They are, respectively,
    // the current, previous, and two prior iterations of it.
    //
    // a is current term of the continued fraction.
    let mut n: c_ulong = given_numerator;
    let mut d: c_ulong = given_denominator;
    let mut n0: c_ulong = 0;
    let mut d1: c_ulong = 0;
    let mut n1: c_ulong = 1;
    let mut d0: c_ulong = 1;
    let mut n2: c_ulong;
    let mut d2: c_ulong;

    loop {
        if d == 0 {
            break;
        }
        // Find next term in continued fraction, 'a', via
        // Euclidean algorithm.
        let dp: c_ulong = d;
        let a: c_ulong = n / d;
        d = n % d;
        n = dp;

        // Calculate the current rational approximation (aka
        // convergent), n2/d2, using the term just found and
        // the two prior approximations.
        n2 = n0.wrapping_add(a.wrapping_mul(n1));
        d2 = d0.wrapping_add(a.wrapping_mul(d1));

        // If the current convergent exceeds the maxes, then
        // return either the previous convergent or the
        // largest semi-convergent, the final term of which is
        // found below as 't'.
        if n2 > max_numerator || d2 > max_denominator {
            let mut t: c_ulong = ULONG_MAX;

            if d1 != 0 {
                t = max_denominator.wrapping_sub(d0) / d1;
            }
            if n1 != 0 {
                t = min(t, max_numerator.wrapping_sub(n0) / n1);
            }

            // This tests if the semi-convergent is closer than the previous
            // convergent. If d1 is zero there is no previous convergent as this
            // is the 1st iteration, so always choose the semi-convergent.
            //
            // `2u * t`: 2u (unsigned int) is converted to unsigned long.
            let two_t: c_ulong = (2 as c_ulong).wrapping_mul(t);
            if d1 == 0
                || two_t > a
                || (two_t == a && d0.wrapping_mul(dp) > d1.wrapping_mul(d))
            {
                n1 = n0.wrapping_add(t.wrapping_mul(n1));
                d1 = d0.wrapping_add(t.wrapping_mul(d1));
            }
            break;
        }
        n0 = n1;
        n1 = n2;
        d0 = d1;
        d1 = d2;
    }

    // SAFETY: the caller (as in the C original) must pass valid,
    // writable pointers to unsigned long.
    unsafe {
        *best_numerator = n1;
        *best_denominator = d1;
    }
}

// MODULE_DESCRIPTION("Rational fraction support library");
// MODULE_LICENSE("GPL v2");
