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
fn tauswor(s: u32, a: u32, b: u32, c: u32, d: u32) -> u32 {
    ((s & c) << d) ^ (((s << a) ^ s) >> b)
}

#[inline(always)]
fn seed_min(x: u32, m: u32) -> u32 {
    if x < m {
        x.wrapping_add(m)
    } else {
        x
    }
}

#[no_mangle]
pub extern "C" fn prandom_u32_state(state: *mut rnd_state) -> u32 {
    unsafe {
        (*state).s1 = tauswor((*state).s1, 6, 13, 4294967294, 18);
        (*state).s2 = tauswor((*state).s2, 2, 27, 4294967288, 2);
        (*state).s3 = tauswor((*state).s3, 13, 21, 4294967280, 7);
        (*state).s4 = tauswor((*state).s4, 3, 12, 4294967168, 13);

        (*state).s1 ^ (*state).s2 ^ (*state).s3 ^ (*state).s4
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
    // for_each_possible_cpu: only CPU 0; per_cpu_ptr(p, 0) == p
    let state = pcpu_state;
    let mut seeds: [u32; 4] = [0; 4];

    unsafe {
        get_random_bytes(
            seeds.as_mut_ptr() as *mut c_void,
            core::mem::size_of::<[u32; 4]>(),
        );
        (*state).s1 = seed_min(seeds[0], 2);
        (*state).s2 = seed_min(seeds[1], 8);
        (*state).s3 = seed_min(seeds[2], 16);
        (*state).s4 = seed_min(seeds[3], 128);
    }

    prandom_warmup(state);
}
