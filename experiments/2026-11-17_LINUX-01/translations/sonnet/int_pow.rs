use core::ffi::c_uint;

#[no_mangle]
pub extern "C" fn int_pow(base: u64, exp: c_uint) -> u64 {
    let mut base: u64 = base;
    let mut exp: c_uint = exp;
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
