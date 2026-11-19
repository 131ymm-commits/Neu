use core::ffi::{c_int, c_void};

#[repr(C)]
pub struct RndState {
    pub s1: u32,
    pub s2: u32,
    pub s3: u32,
    pub s4: u32,
}

extern "C" {
    fn get_random_bytes(buf: *mut c_void, len: usize);
}

const BITS_PER_BYTE: u32 = 8;
const POSSIBLE_CPUS: c_int = 1;

#[inline]
fn tausworthe(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c) << d) ^ (((s << a) ^ s) >> b)
}

#[inline]
fn __seed(x: u32, m: u32) -> u32 {
    if x < m {
        x.wrapping_add(m)
    } else {
        x
    }
}

#[inline]
fn per_cpu_ptr(p: *mut RndState, _cpu: c_int) -> *mut RndState {
    p
}

#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut RndState) -> u32 {
    unsafe {
        (*state).s1 = tausworthe((*state).s1, 6, 13, 4294967294, 18);
        (*state).s2 = tausworthe((*state).s2, 2, 27, 4294967288, 2);
        (*state).s3 = tausworthe((*state).s3, 13, 21, 4294967280, 7);
        (*state).s4 = tausworthe((*state).s4, 3, 12, 4294967168, 13);

        (*state).s1 ^ (*state).s2 ^ (*state).s3 ^ (*state).s4
    }
}

#[no_mangle]
pub extern "C" fn prandom_bytes_state(state: *mut RndState, buf: *mut c_void, mut bytes: usize) {
    let mut ptr = buf as *mut u8;

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
            rem >>= BITS_PER_BYTE;
            if bytes == 0 {
                break;
            }
        }
    }
}

#[no_mangle]
pub extern "C" fn prandom_warmup(state: *mut RndState) {
    /* Calling RNG ten times to satisfy recurrence condition */
    for _ in 0..10 {
        prandom_u32_state(state);
    }
}

#[no_mangle]
pub extern "C" fn prandom_seed_full_state(pcpu_state: *mut RndState) {
    for i in 0..POSSIBLE_CPUS {
        let state = per_cpu_ptr(pcpu_state, i);
        let mut seeds = [0u32; 4];

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
}
