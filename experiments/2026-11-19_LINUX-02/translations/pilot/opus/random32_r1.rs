#![allow(non_camel_case_types)]

use core::ffi::c_void;

#[repr(C)]
pub struct rnd_state {
    pub s1: u32,
    pub s2: u32,
    pub s3: u32,
    pub s4: u32,
}

extern "C" {
    fn get_random_bytes(buf: *mut c_void, len: usize);
}

/*
 * Handle minimum values for seeds
 */
#[inline(always)]
fn __seed(x: u32, m: u32) -> u32 {
    if x < m { x.wrapping_add(m) } else { x }
}

#[inline(always)]
fn tausworthe(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c).wrapping_shl(d)) ^ ((s.wrapping_shl(a) ^ s) >> b)
}

/// prandom_u32_state - seeded pseudo-random number generator.
#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut rnd_state) -> u32 {
    let st = unsafe { &mut *state };
    st.s1 = tausworthe(st.s1, 6, 13, 4294967294, 18);
    st.s2 = tausworthe(st.s2, 2, 27, 4294967288, 2);
    st.s3 = tausworthe(st.s3, 13, 21, 4294967280, 7);
    st.s4 = tausworthe(st.s4, 3, 12, 4294967168, 13);
    st.s1 ^ st.s2 ^ st.s3 ^ st.s4
}

/// prandom_bytes_state - get the requested number of pseudo-random bytes
#[no_mangle]
pub extern "C" fn prandom_bytes_state(state: *mut rnd_state, buf: *mut c_void, bytes: usize) {
    let mut ptr = buf as *mut u8;
    let mut bytes = bytes;

    while bytes >= core::mem::size_of::<u32>() {
        let v = prandom_u32_state(state);
        unsafe {
            core::ptr::write_unaligned(ptr as *mut u32, v);
            ptr = ptr.add(core::mem::size_of::<u32>());
        }
        bytes -= core::mem::size_of::<u32>();
    }

    if bytes > 0 {
        let mut rem = prandom_u32_state(state);
        loop {
            unsafe {
                *ptr = rem as u8;
                ptr = ptr.add(1);
            }
            bytes -= 1;
            rem >>= 8;
            if bytes == 0 {
                break;
            }
        }
    }
}

#[no_mangle]
pub extern "C" fn prandom_warmup(state: *mut rnd_state) {
    /* Calling RNG ten times to satisfy recurrence condition */
    for _ in 0..10 {
        prandom_u32_state(state);
    }
}

#[no_mangle]
pub extern "C" fn prandom_seed_full_state(pcpu_state: *mut rnd_state) {
    // for_each_possible_cpu: only CPU 0; per_cpu_ptr(p, 0) == p
    let state = pcpu_state;
    let mut seeds: [u32; 4] = [0; 4];

    unsafe {
        get_random_bytes(
            seeds.as_mut_ptr() as *mut c_void,
            core::mem::size_of::<[u32; 4]>(),
        );
    }
    {
        let st = unsafe { &mut *state };
        st.s1 = __seed(seeds[0], 2);
        st.s2 = __seed(seeds[1], 8);
        st.s3 = __seed(seeds[2], 16);
        st.s4 = __seed(seeds[3], 128);
    }

    prandom_warmup(state);
}
