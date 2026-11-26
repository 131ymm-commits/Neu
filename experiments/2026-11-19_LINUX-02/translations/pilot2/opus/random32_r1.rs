// Перевод lib/random32.c (x86_64, один возможный CPU, CONFIG_KUNIT включён).
// Примечание: на машине, где готовился перевод, rustc отсутствовал,
// поэтому сборка этого файла не проверялась.

use core::ffi::c_void;

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Copy)]
pub struct rnd_state {
    pub s1: u32,
    pub s2: u32,
    pub s3: u32,
    pub s4: u32,
}

extern "C" {
    fn get_random_bytes(buf: *mut c_void, len: usize);
}

/// Handle minimum values for seeds (static inline __seed из prandom.h).
#[inline]
fn __seed(x: u32, m: u32) -> u32 {
    if x < m {
        x.wrapping_add(m)
    } else {
        x
    }
}

/// TAUSWORTHE(s, a, b, c, d) ((s & c) << d) ^ (((s << a) ^ s) >> b)
/// Сдвиги u32 на величину < 32: выдвинутые биты отбрасываются, как в C.
#[inline]
fn tausworthe(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c) << d) ^ (((s << a) ^ s) >> b)
}

#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut rnd_state) -> u32 {
    unsafe {
        (*state).s1 = tausworthe((*state).s1, 6, 13, 4294967294, 18);
        (*state).s2 = tausworthe((*state).s2, 2, 27, 4294967288, 2);
        (*state).s3 = tausworthe((*state).s3, 13, 21, 4294967280, 7);
        (*state).s4 = tausworthe((*state).s4, 3, 12, 4294967168, 13);

        (*state).s1 ^ (*state).s2 ^ (*state).s3 ^ (*state).s4
    }
}

#[no_mangle]
pub extern "C" fn prandom_bytes_state(state: *mut rnd_state, buf: *mut c_void, bytes: usize) {
    const SZ: usize = core::mem::size_of::<u32>();
    let mut ptr = buf as *mut u8;
    let mut bytes = bytes;

    while bytes >= SZ {
        let v = prandom_u32_state(state);
        // put_unaligned: запись u32 в родном (little-endian) порядке по невыровненному адресу.
        unsafe {
            core::ptr::write_unaligned(ptr as *mut u32, v);
        }
        ptr = ptr.wrapping_add(SZ);
        bytes -= SZ;
    }

    if bytes > 0 {
        let mut rem = prandom_u32_state(state);
        loop {
            unsafe {
                *ptr = rem as u8;
            }
            ptr = ptr.wrapping_add(1);
            bytes -= 1;
            rem >>= 8; // BITS_PER_BYTE
            if bytes == 0 {
                break;
            }
        }
    }
}

#[no_mangle]
pub extern "C" fn prandom_warmup(state: *mut rnd_state) {
    /* Calling RNG ten times to satisfy recurrence condition */
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
    prandom_u32_state(state);
}

#[no_mangle]
pub extern "C" fn prandom_seed_full_state(pcpu_state: *mut rnd_state) {
    // for_each_possible_cpu(i): только i = 0; per_cpu_ptr(pcpu_state, 0) == pcpu_state.
    let state = pcpu_state;
    let mut seeds: [u32; 4] = [0; 4];

    unsafe {
        get_random_bytes(
            seeds.as_mut_ptr() as *mut c_void,
            core::mem::size_of::<[u32; 4]>(),
        );
        (*state).s1 = __seed(seeds[0], 2);
        (*state).s2 = __seed(seeds[1], 8);
        (*state).s3 = __seed(seeds[2], 16);
        (*state).s4 = __seed(seeds[3], 128);
    }

    prandom_warmup(state);
}
