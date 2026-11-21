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

#[inline(always)]
fn seed(x: u32, m: u32) -> u32 {
    if x < m {
        x + m
    } else {
        x
    }
}

#[inline(always)]
fn tauswothe(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c) << d) ^ (((s << a) ^ s) >> b)
}

#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut rnd_state) -> u32 {
    unsafe {
        let st = &mut *state;
        st.s1 = tauswothe(st.s1, 6, 13, 4294967294, 18);
        st.s2 = tauswothe(st.s2, 2, 27, 4294967288, 2);
        st.s3 = tauswothe(st.s3, 13, 21, 4294967280, 7);
        st.s4 = tauswothe(st.s4, 3, 12, 4294967168, 13);
        st.s1 ^ st.s2 ^ st.s3 ^ st.s4
    }
}

#[no_mangle]
pub extern "C" fn prandom_bytes_state(state: *mut rnd_state, buf: *mut c_void, bytes: usize) {
    let mut ptr = buf as *mut u8;
    let mut bytes = bytes;

    while bytes >= 4 {
        let v = prandom_u32_state(state);
        unsafe {
            core::ptr::write_unaligned(ptr as *mut u32, v);
            ptr = ptr.add(4);
        }
        bytes -= 4;
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
    for _ in 0..10 {
        prandom_u32_state(state);
    }
}

#[no_mangle]
pub extern "C" fn prandom_seed_full_state(pcpu_state: *mut rnd_state) {
    // Single possible CPU: per_cpu_ptr(pcpu_state, 0) == pcpu_state.
    let state = pcpu_state;
    let mut seeds = [0u32; 4];
    unsafe {
        get_random_bytes(
            seeds.as_mut_ptr() as *mut c_void,
            core::mem::size_of::<[u32; 4]>(),
        );
        (*state).s1 = seed(seeds[0], 2);
        (*state).s2 = seed(seeds[1], 8);
        (*state).s3 = seed(seeds[2], 16);
        (*state).s4 = seed(seeds[3], 128);
    }
    prandom_warmup(state);
}
