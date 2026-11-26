// SPDX-License-Identifier: GPL-2.0
//! An integer based power function
//!
//! Derived from drivers/video/backlight/pwm_bl.c

use core::ffi::c_uint;

/// int_pow - computes the exponentiation of the given base and exponent
/// @base: base which will be raised to the given power
/// @exp: power to be raised to
///
/// Computes: pow(base, exp), i.e. @base raised to the @exp power
#[no_mangle]
pub extern "C" fn int_pow(mut base: u64, mut exp: c_uint) -> u64 {
    let mut result: u64 = 1;

    while exp != 0 {
        if exp & 1 != 0 {
            result = result.wrapping_mul(base);
        }
        exp >>= 1;
        base = base.wrapping_mul(base);
    }

    result
}
