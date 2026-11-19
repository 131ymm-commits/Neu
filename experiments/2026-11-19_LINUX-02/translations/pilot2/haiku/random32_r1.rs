use core::ffi::{c_int, c_void};
use core::mem;
use core::ptr;

/// struct rnd_state из include/linux/prandom.h
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

/// Количество возможных процессоров: в этой конфигурации один.
const NR_POSSIBLE_CPUS: c_int = 1;

/// per_cpu_ptr(p, 0) == p: __percpu-указатель — обычный указатель.
#[inline(always)]
fn per_cpu_ptr(p: *mut RndState, _cpu: c_int) -> *mut RndState {
    p
}

/// Минимальные значения для затравок.
#[inline(always)]
fn __seed(x: u32, m: u32) -> u32 {
    if x < m {
        x + m
    } else {
        x
    }
}

/// TAUSWORTHE(s, a, b, c, d) из оригинала.
#[inline(always)]
fn tausworthe(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c) << d) ^ (((s << a) ^ s) >> b)
}

/// u32 prandom_u32_state(struct rnd_state *state)
#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut RndState) -> u32 {
    unsafe {
        let st = &mut *state;
        st.s1 = tausworthe(st.s1, 6, 13, 4294967294, 18);
        st.s2 = tausworthe(st.s2, 2, 27, 4294967288, 2);
        st.s3 = tausworthe(st.s3, 13, 21, 4294967280, 7);
        st.s4 = tausworthe(st.s4, 3, 12, 4294967168, 13);

        st.s1 ^ st.s2 ^ st.s3 ^ st.s4
    }
}

/// void prandom_bytes_state(struct rnd_state *state, void *buf, size_t bytes)
#[no_mangle]
pub extern "C" fn prandom_bytes_state(state: *mut RndState, buf: *mut c_void, bytes: usize) {
    let mut ptr = buf as *mut u8;
    let mut bytes = bytes;

    while bytes >= mem::size_of::<u32>() {
        let v = prandom_u32_state(state);
        unsafe {
            ptr::write_unaligned(ptr as *mut u32, v);
            ptr = ptr.add(mem::size_of::<u32>());
        }
        bytes -= mem::size_of::<u32>();
    }

    if bytes > 0 {
        let mut rem = prandom_u32_state(state);
        loop {
            unsafe {
                *ptr = rem as u8;
                ptr = ptr.add(1);
            }
            bytes -= 1;
            rem >>= 8; // BITS_PER_BYTE
            if !(bytes > 0) {
                break;
            }
        }
    }
}

/// void prandom_warmup(struct rnd_state *state)
/// CONFIG_KUNIT задан: функция нестатическая и экспортируется.
#[no_mangle]
pub extern "C" fn prandom_warmup(state: *mut RndState) {
    // Calling RNG ten times to satisfy recurrence condition
    for _ in 0..10 {
        prandom_u32_state(state);
    }
}

/// void prandom_seed_full_state(struct rnd_state __percpu *pcpu_state)
#[no_mangle]
pub extern "C" fn prandom_seed_full_state(pcpu_state: *mut RndState) {
    let mut i: c_int = 0;
    while i < NR_POSSIBLE_CPUS {
        let state = per_cpu_ptr(pcpu_state, i);
        let mut seeds = [0u32; 4];

        unsafe {
            get_random_bytes(
                seeds.as_mut_ptr() as *mut c_void,
                mem::size_of::<[u32; 4]>(),
            );
        }

        unsafe {
            let st = &mut *state;
            st.s1 = __seed(seeds[0], 2);
            st.s2 = __seed(seeds[1], 8);
            st.s3 = __seed(seeds[2], 16);
            st.s4 = __seed(seeds[3], 128);
        }

        prandom_warmup(state);

        i += 1;
    }
}
